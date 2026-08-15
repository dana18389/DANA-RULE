from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json

from .governance import GovernanceError, GovernanceRuntime


class ContractRegistryError(GovernanceError):
    pass


class BindingNotFoundError(ContractRegistryError):
    pass


class BindingBlockedError(ContractRegistryError):
    pass


@dataclass(frozen=True)
class DocumentBinding:
    binding_id: str
    document_type_id: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    schema_id: str
    schema_version: str
    schema_hash: str
    extraction_profile_id: str
    binding_status: str
    blocking_errors: tuple[str, ...]

    @property
    def executable(self) -> bool:
        return not self.blocking_errors and self.extraction_profile_id not in {
            "NOT_DEFINED_IN_SOURCE", "UNRESOLVED", "UNKNOWN"
        }


@dataclass(frozen=True)
class RegistryValidationReport:
    prompt_count: int
    schema_count: int
    operator_count: int
    binding_count: int
    referential_errors: tuple[str, ...] = ()
    unresolved_profile_bindings: int = 0

    @property
    def structurally_valid(self) -> bool:
        return not self.referential_errors


class GovernanceContractRegistry:
    EXPECTED_COUNTS = {"prompts": 215, "schemas": 226, "operators": 19, "bindings": 226}

    def __init__(self, governance: Mapping[str, Any]) -> None:
        self._governance = governance
        self.prompts = {x["prompt_id"]: x for x in governance.get("08_prompt_registry", [])}
        self.schemas = {x["schema_id"]: x for x in governance.get("09_schema_registry", [])}
        self.operators = {x["operator_id"]: x for x in governance.get("14_operator_registry", [])}
        self.bindings = tuple(governance.get("15_prompt_schema_profile_bindings", []))
        self._bindings_by_document_type: dict[str, list[Mapping[str, Any]]] = {}
        for binding in self.bindings:
            self._bindings_by_document_type.setdefault(binding["document_type_id"], []).append(binding)

    @classmethod
    def from_file(cls, path: str | Path, *, expected_sha256: str | None = None) -> "GovernanceContractRegistry":
        p = Path(path)
        payload = p.read_bytes()
        if expected_sha256 is not None:
            actual = sha256(payload).hexdigest()
            if actual != expected_sha256:
                raise ContractRegistryError(
                    f"governance contract hash mismatch: expected {expected_sha256}, got {actual}"
                )
        return cls(json.loads(payload))

    def validate(self, *, enforce_expected_counts: bool = True) -> RegistryValidationReport:
        errors: list[str] = []
        counts = {
            "prompts": len(self.prompts),
            "schemas": len(self.schemas),
            "operators": len(self.operators),
            "bindings": len(self.bindings),
        }
        if enforce_expected_counts:
            for key, expected in self.EXPECTED_COUNTS.items():
                if counts[key] != expected:
                    errors.append(f"{key}: expected {expected}, got {counts[key]}")

        unresolved = 0
        for binding in self.bindings:
            prompt = self.prompts.get(binding["prompt_id"])
            schema = self.schemas.get(binding["schema_id"])
            if prompt is None:
                errors.append(f"{binding['binding_id']}: missing prompt {binding['prompt_id']}")
            elif prompt.get("prompt_hash") != binding.get("prompt_hash"):
                errors.append(f"{binding['binding_id']}: prompt hash mismatch")
            if schema is None:
                errors.append(f"{binding['binding_id']}: missing schema {binding['schema_id']}")
            elif schema.get("schema_hash") != binding.get("schema_hash"):
                errors.append(f"{binding['binding_id']}: schema hash mismatch")
            if binding.get("extraction_profile_id") in {
                None, "NOT_DEFINED_IN_SOURCE", "UNRESOLVED", "UNKNOWN"
            }:
                unresolved += 1

        return RegistryValidationReport(
            prompt_count=counts["prompts"],
            schema_count=counts["schemas"],
            operator_count=counts["operators"],
            binding_count=counts["bindings"],
            referential_errors=tuple(errors),
            unresolved_profile_bindings=unresolved,
        )

    def resolve_document_binding(
        self, document_type_id: str, *, require_executable: bool = False
    ) -> DocumentBinding:
        matches = self._bindings_by_document_type.get(document_type_id, [])
        if len(matches) != 1:
            raise BindingNotFoundError(
                f"expected exactly one binding for {document_type_id}, got {len(matches)}"
            )
        raw = matches[0]
        binding = DocumentBinding(
            binding_id=raw["binding_id"],
            document_type_id=raw["document_type_id"],
            prompt_id=raw["prompt_id"],
            prompt_version=raw["prompt_version"],
            prompt_hash=raw["prompt_hash"],
            schema_id=raw["schema_id"],
            schema_version=raw["schema_version"],
            schema_hash=raw["schema_hash"],
            extraction_profile_id=raw.get("extraction_profile_id", "NOT_DEFINED_IN_SOURCE"),
            binding_status=raw.get("binding_status", "UNKNOWN"),
            blocking_errors=tuple(raw.get("blocking_errors", [])),
        )
        if require_executable and not binding.executable:
            raise BindingBlockedError(
                f"{binding.binding_id} is not executable: "
                f"{binding.blocking_errors or (binding.extraction_profile_id,)}"
            )
        return binding


@dataclass(frozen=True)
class CandidateEnvelope:
    case_id: str
    index_id: str
    candidate_id: str
    payload: Mapping[str, Any]
    status: str = "CANDIDATE_ONLY"
    canonical_persistence_allowed: bool = False
    human_review_required: bool = True
    blockers: tuple[str, ...] = field(default_factory=tuple)
    binding_id: str | None = None


class SandboxCandidatePipeline:
    ALLOWED_INDEXES = {"DOCUMENT", "PARTY", "REQUEST"}

    def __init__(self, runtime: GovernanceRuntime, contracts: GovernanceContractRegistry) -> None:
        self.runtime = runtime
        self.contracts = contracts

    def emit_candidate(
        self,
        *,
        case_id: str,
        index_id: str,
        payload: Mapping[str, Any],
        document_type_id: str | None = None,
    ) -> CandidateEnvelope:
        if index_id not in self.ALLOWED_INDEXES:
            raise GovernanceError(f"index is not active in phase-1 sandbox: {index_id}")

        self.runtime.snapshot(environment="sandbox_shadow_mode")
        blockers: list[str] = []
        binding_id = None

        if index_id == "DOCUMENT":
            if not document_type_id:
                blockers.append("DOCUMENT_TYPE_REQUIRED_FOR_BINDING")
            else:
                binding = self.contracts.resolve_document_binding(document_type_id)
                binding_id = binding.binding_id
                blockers.extend(binding.blocking_errors)
                if binding.extraction_profile_id in {
                    "NOT_DEFINED_IN_SOURCE", "UNRESOLVED", "UNKNOWN"
                }:
                    blockers.append("UNKNOWN_EXTRACTION_PROFILE")

        canonical = json.dumps(
            {"case_id": case_id, "index_id": index_id, "payload": payload},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        candidate_id = f"cand_{sha256(canonical).hexdigest()[:24]}"

        return CandidateEnvelope(
            case_id=case_id,
            index_id=index_id,
            candidate_id=candidate_id,
            payload=dict(payload),
            blockers=tuple(sorted(set(blockers))),
            binding_id=binding_id,
        )

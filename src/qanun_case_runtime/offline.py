from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Protocol
import copy
import json

from jsonschema import Draft202012Validator

from .bundle import LoadedGovernanceBundle
from .contracts import BindingBlockedError, GovernanceContractRegistry
from .governance import GovernanceError, GovernanceRuntime


class OfflineExecutionError(GovernanceError):
    pass


class OutputValidationError(OfflineExecutionError):
    pass


@dataclass(frozen=True)
class ExecutionContract:
    contract_id: str
    case_id: str
    document_id: str
    document_type_id: str
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    schema_id: str
    schema_version: str
    schema_hash: str
    extraction_profile_id: str
    mode: str
    unresolved_profile_override: bool
    snapshot_id: str


@dataclass(frozen=True)
class ExtractionResult:
    payload: Mapping[str, Any]
    extractor_id: str
    deterministic: bool = True


class ExtractorAdapter(Protocol):
    extractor_id: str

    def extract(self, *, raw_text: str, contract: ExecutionContract) -> ExtractionResult:
        ...


class FixtureExtractor:
    """Deterministic replacement for an LLM in contract/integration tests."""

    extractor_id = "FIXTURE_EXTRACTOR_V1"

    def __init__(self, fixtures: Mapping[str, Mapping[str, Any]]) -> None:
        self._fixtures = {k: copy.deepcopy(v) for k, v in fixtures.items()}

    def extract(self, *, raw_text: str, contract: ExecutionContract) -> ExtractionResult:
        if contract.document_type_id not in self._fixtures:
            raise OfflineExecutionError(
                f"no fixture for document type {contract.document_type_id}"
            )
        return ExtractionResult(
            payload=copy.deepcopy(self._fixtures[contract.document_type_id]),
            extractor_id=self.extractor_id,
        )


@dataclass(frozen=True)
class OfflineRunResult:
    execution_contract: ExecutionContract
    extracted_payload: Mapping[str, Any]
    audit_trace: tuple[Mapping[str, Any], ...]
    document_candidate_id: str
    party_candidate_count: int
    request_candidate_count: int
    canonical_persistence_allowed: bool = False


class DocumentSchemaResolver:
    def __init__(self, document_package: Mapping[str, Any]) -> None:
        self.package = document_package
        registry = document_package["schema_registry"]
        self._type_contracts = registry["type_specific_contracts"]
        self._model_common = document_package["llm_output_ownership_projection_contract"][
            "model_output_common_schema"
        ]
        self._model_hashes = {
            row["document_type_id"]: row["schema_hash"]
            for row in document_package["model_runtime_schema_hash_manifest"]
        }

    def resolve_model_schema(self, document_type_id: str) -> Mapping[str, Any]:
        if document_type_id not in self._type_contracts:
            raise OfflineExecutionError(f"unknown document type schema: {document_type_id}")
        common = copy.deepcopy(self._model_common)
        typed = copy.deepcopy(self._type_contracts[document_type_id])
        common.setdefault("properties", {})["type_specific"] = typed
        return common

    def expected_schema_hash(self, document_type_id: str) -> str:
        return self._model_hashes[document_type_id]

    @staticmethod
    def validate(schema: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
        if errors:
            rendered = []
            for error in errors[:10]:
                path = "/".join(str(x) for x in error.absolute_path) or "$"
                rendered.append(f"{path}: {error.message}")
            raise OutputValidationError("; ".join(rendered))


class OfflineCaseEngine:
    MODE = "OFFLINE_FIXTURE_TEST"

    def __init__(self, *, runtime: GovernanceRuntime, bundle: LoadedGovernanceBundle) -> None:
        self.runtime = runtime
        self.bundle = bundle
        self.contracts: GovernanceContractRegistry = bundle.contracts
        self.schemas = DocumentSchemaResolver(bundle.source_packages["DOCUMENT"])

    def build_execution_contract(
        self,
        *,
        case_id: str,
        document_id: str,
        document_type_id: str,
        allow_unresolved_profile_for_fixture: bool = False,
    ) -> ExecutionContract:
        binding = self.contracts.resolve_document_binding(document_type_id)
        unresolved = not binding.executable
        if unresolved and not allow_unresolved_profile_for_fixture:
            raise BindingBlockedError(
                f"{binding.binding_id} requires resolved extraction profile"
            )
        if unresolved and set(binding.blocking_errors) - {"UNKNOWN_EXTRACTION_PROFILE"}:
            raise BindingBlockedError(
                f"offline override is limited to UNKNOWN_EXTRACTION_PROFILE: {binding.blocking_errors}"
            )

        snapshot = self.runtime.snapshot(environment="sandbox_shadow_mode")
        canonical = json.dumps(
            {
                "case_id": case_id,
                "document_id": document_id,
                "document_type_id": document_type_id,
                "binding_id": binding.binding_id,
                "snapshot_id": snapshot.snapshot_id,
                "mode": self.MODE,
                "override": unresolved,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return ExecutionContract(
            contract_id=f"exec_{sha256(canonical).hexdigest()[:24]}",
            case_id=case_id,
            document_id=document_id,
            document_type_id=document_type_id,
            prompt_id=binding.prompt_id,
            prompt_version=binding.prompt_version,
            prompt_hash=binding.prompt_hash,
            schema_id=binding.schema_id,
            schema_version=binding.schema_version,
            schema_hash=binding.schema_hash,
            extraction_profile_id=binding.extraction_profile_id,
            mode=self.MODE,
            unresolved_profile_override=unresolved,
            snapshot_id=snapshot.snapshot_id,
        )

    def run(
        self,
        *,
        case_id: str,
        document_id: str,
        document_type_id: str,
        raw_text: str,
        extractor: ExtractorAdapter,
        allow_unresolved_profile_for_fixture: bool = False,
    ) -> OfflineRunResult:
        contract = self.build_execution_contract(
            case_id=case_id,
            document_id=document_id,
            document_type_id=document_type_id,
            allow_unresolved_profile_for_fixture=allow_unresolved_profile_for_fixture,
        )
        audit: list[Mapping[str, Any]] = [
            {
                "event": "EXECUTION_CONTRACT_CREATED",
                "contract_id": contract.contract_id,
                "mode": contract.mode,
                "snapshot_id": contract.snapshot_id,
            }
        ]
        if contract.unresolved_profile_override:
            audit.append(
                {
                    "event": "SANDBOX_BLOCKER_OVERRIDE",
                    "reason_code": "UNKNOWN_EXTRACTION_PROFILE",
                    "scope": "OFFLINE_FIXTURE_TEST_ONLY",
                    "production_eligible": False,
                }
            )

        result = extractor.extract(raw_text=raw_text, contract=contract)
        audit.append({"event": "EXTRACTOR_COMPLETED", "extractor_id": result.extractor_id})

        schema = self.schemas.resolve_model_schema(document_type_id)
        self.schemas.validate(schema, result.payload)
        audit.append(
            {
                "event": "STRUCTURED_OUTPUT_VALIDATED",
                "schema_id": contract.schema_id,
                "schema_hash": contract.schema_hash,
            }
        )

        digest_seed = json.dumps(
            {"case_id": case_id, "document_id": document_id, "payload": result.payload},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        document_candidate_id = f"doccand_{sha256(digest_seed).hexdigest()[:24]}"
        parties = result.payload.get("parties_and_persons", [])
        requests = result.payload.get("requests", [])
        audit.extend(
            [
                {
                    "event": "DOCUMENT_CANDIDATE_CREATED",
                    "candidate_id": document_candidate_id,
                    "canonical_persistence_allowed": False,
                },
                {
                    "event": "CROSS_INDEX_HANDOFF_PREPARED",
                    "target_index": "PARTY",
                    "candidate_count": len(parties),
                    "canonical_persistence_allowed": False,
                },
                {
                    "event": "CROSS_INDEX_HANDOFF_PREPARED",
                    "target_index": "REQUEST",
                    "candidate_count": len(requests),
                    "canonical_persistence_allowed": False,
                },
            ]
        )
        return OfflineRunResult(
            execution_contract=contract,
            extracted_payload=copy.deepcopy(result.payload),
            audit_trace=tuple(audit),
            document_candidate_id=document_candidate_id,
            party_candidate_count=len(parties),
            request_candidate_count=len(requests),
        )

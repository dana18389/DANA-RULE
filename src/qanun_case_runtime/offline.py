from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
    matter_id: str | None = None
    proceeding_id: str | None = None
    litigation_stage: str | None = None


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
class IndexCandidate:
    candidate_id: str
    index_id: str
    payload: Mapping[str, Any]
    provenance: Mapping[str, Any]
    status: str = "CANDIDATE_ONLY"
    canonical_persistence_allowed: bool = False
    stable_id_issued: bool = False


@dataclass(frozen=True)
class OfflineRunResult:
    execution_contract: ExecutionContract
    extracted_payload: Mapping[str, Any]
    audit_trace: tuple[Mapping[str, Any], ...]
    document_candidate_id: str
    party_candidates: tuple[IndexCandidate, ...]
    request_candidates: tuple[IndexCandidate, ...]
    party_resolution_request: Mapping[str, Any] | None
    canonical_persistence_allowed: bool = False

    @property
    def party_candidate_count(self) -> int:
        return len(self.party_candidates)

    @property
    def request_candidate_count(self) -> int:
        return len(self.request_candidates)


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


class CrossIndexAdapter:
    """Build candidate-only DOCUMENT→PARTY and DOCUMENT→REQUEST handoffs."""

    def __init__(self, source_packages: Mapping[str, Mapping[str, Any]]) -> None:
        self.document_party = source_packages["DOCUMENT_PARTY"]
        self.request_cross_index = source_packages["REQUEST_CROSS_INDEX"]
        self.party_request_schema = self.document_party[
            "document_party_resolution_request_schema"
        ]
        self.request_provenance = self.request_cross_index["source_provenance_contract"]

    @staticmethod
    def _id(prefix: str, payload: Mapping[str, Any]) -> str:
        canonical = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return f"{prefix}_{sha256(canonical).hexdigest()[:24]}"

    def build_party_candidates(
        self, *, contract: ExecutionContract, parties: list[Mapping[str, Any]]
    ) -> tuple[tuple[IndexCandidate, ...], Mapping[str, Any] | None]:
        if not parties:
            return (), None
        candidates: list[IndexCandidate] = []
        envelopes: list[Mapping[str, Any]] = []
        for row in parties:
            provenance = {
                "source_document_id": contract.document_id,
                "source_page": row["source_page"],
                "source_quote": row["source_quote"],
                "certainty": row["certainty"],
            }
            candidate_payload = {
                "name_raw": row["name_raw"],
                "name_normalized_candidate": row["normalized_name_suggestion"],
                "person_type": row["person_type"],
                "role_raw": row["role_raw"],
                "role_category": row["role_category"],
                "procedural_role_suggestion": row["procedural_role_suggestion"],
                "original_proceeding_role_raw": row["original_proceeding_role_raw"],
                "represented_by_raw": row["represented_by_raw"],
                "represents_raw": list(row["represents_raw"]),
                "identifiers": list(row["identifiers_raw"]),
                "attributes": {
                    "address_raw": row["address_raw"],
                    "is_existing_case_party_candidate": row[
                        "is_existing_case_party_candidate"
                    ],
                },
            }
            correlation_seed = {
                "case_id": contract.case_id,
                "document_id": contract.document_id,
                "candidate": candidate_payload,
                "provenance": provenance,
            }
            candidate_id = self._id("partycand", correlation_seed)
            candidates.append(
                IndexCandidate(
                    candidate_id=candidate_id,
                    index_id="PARTY",
                    payload=candidate_payload,
                    provenance=provenance,
                )
            )
            envelopes.append(
                {
                    "candidate_id": candidate_id,
                    "candidate": candidate_payload,
                    "provenance": provenance,
                }
            )

        request_payload = {
            "contract_id": "DOCUMENT_PARTY_RESOLUTION_REQUEST_V1",
            "request_id": self._id(
                "partyres",
                {
                    "case_id": contract.case_id,
                    "document_id": contract.document_id,
                    "candidates": envelopes,
                },
            ),
            "context": {
                "document_id": contract.document_id,
                "internal_case_id": contract.case_id,
                "internal_matter_id": contract.matter_id,
                "internal_proceeding_id": contract.proceeding_id,
                "litigation_stage": contract.litigation_stage,
                "context_correlation_id": contract.contract_id,
                "context_source": "BACKEND_PLATFORM",
                "immutable": True,
            },
            "candidates": envelopes,
            "requested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        DocumentSchemaResolver.validate(self.party_request_schema, request_payload)
        return tuple(candidates), request_payload

    def build_request_candidates(
        self, *, contract: ExecutionContract, requests: list[Mapping[str, Any]]
    ) -> tuple[IndexCandidate, ...]:
        required_provenance = set(self.request_provenance["required"])
        candidates: list[IndexCandidate] = []
        for row in requests:
            source_location = (
                f"PAGE:{row['source_page']}"
                if row["source_page"] is not None
                else "VIRTUAL_SOURCE_LOCATION"
            )
            provenance = {
                "source_document_id": contract.document_id,
                "source_location": source_location,
                "source_quote": row["source_quote"],
                "litigation_stage": contract.litigation_stage or row["procedural_stage"],
                "certainty": row["certainty"],
            }
            if not required_provenance.issubset(provenance):
                raise OutputValidationError("request candidate provenance is incomplete")
            if not provenance["source_quote"]:
                raise OutputValidationError("request candidate source_quote is empty")
            payload = {
                "raw_text": row["request_text_raw"],
                "summary": row["request_summary"],
                "requested_by_raw": row["requested_by_raw"],
                "against_party_raw": row["against_party_raw"],
                "request_nature_candidate": row["request_nature_raw"],
                "procedural_position_candidate": row["primary_or_incidental_raw"],
                "object_description_raw": row["object_raw"],
                "amount_raw": row["amount_raw"],
                "currency_candidate": row["currency_raw"],
                "related_request_raw": row["related_request_raw"],
                "explicit_status_event_candidate": row["explicit_status_raw"],
                "certainty": row["certainty"],
                "case_id": contract.case_id,
                "matter_id": contract.matter_id,
                "proceeding_id": contract.proceeding_id,
                "litigation_stage": provenance["litigation_stage"],
            }
            candidate_id = self._id(
                "requestcand",
                {
                    "case_id": contract.case_id,
                    "document_id": contract.document_id,
                    "candidate": payload,
                    "provenance": provenance,
                },
            )
            candidates.append(
                IndexCandidate(
                    candidate_id=candidate_id,
                    index_id="REQUEST",
                    payload=payload,
                    provenance=provenance,
                )
            )
        return tuple(candidates)


class OfflineCaseEngine:
    MODE = "OFFLINE_FIXTURE_TEST"

    def __init__(self, *, runtime: GovernanceRuntime, bundle: LoadedGovernanceBundle) -> None:
        self.runtime = runtime
        self.bundle = bundle
        self.contracts: GovernanceContractRegistry = bundle.contracts
        self.schemas = DocumentSchemaResolver(bundle.source_packages["DOCUMENT"])
        self.cross_index = CrossIndexAdapter(bundle.source_packages)

    def build_execution_contract(
        self,
        *,
        case_id: str,
        document_id: str,
        document_type_id: str,
        matter_id: str | None = None,
        proceeding_id: str | None = None,
        litigation_stage: str | None = None,
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
                "matter_id": matter_id,
                "proceeding_id": proceeding_id,
                "litigation_stage": litigation_stage,
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
            matter_id=matter_id,
            proceeding_id=proceeding_id,
            litigation_stage=litigation_stage,
        )

    def run(
        self,
        *,
        case_id: str,
        document_id: str,
        document_type_id: str,
        raw_text: str,
        extractor: ExtractorAdapter,
        matter_id: str | None = None,
        proceeding_id: str | None = None,
        litigation_stage: str | None = None,
        allow_unresolved_profile_for_fixture: bool = False,
    ) -> OfflineRunResult:
        contract = self.build_execution_contract(
            case_id=case_id,
            document_id=document_id,
            document_type_id=document_type_id,
            matter_id=matter_id,
            proceeding_id=proceeding_id,
            litigation_stage=litigation_stage,
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
        party_candidates, party_resolution_request = self.cross_index.build_party_candidates(
            contract=contract,
            parties=list(result.payload.get("parties_and_persons", [])),
        )
        request_candidates = self.cross_index.build_request_candidates(
            contract=contract,
            requests=list(result.payload.get("requests", [])),
        )
        audit.extend(
            [
                {
                    "event": "DOCUMENT_CANDIDATE_CREATED",
                    "candidate_id": document_candidate_id,
                    "canonical_persistence_allowed": False,
                },
                {
                    "event": "CROSS_INDEX_HANDOFF_VALIDATED",
                    "target_index": "PARTY",
                    "candidate_count": len(party_candidates),
                    "contract_id": "DOCUMENT_PARTY_RESOLUTION_REQUEST_V1",
                    "canonical_persistence_allowed": False,
                },
                {
                    "event": "CROSS_INDEX_HANDOFF_VALIDATED",
                    "target_index": "REQUEST",
                    "candidate_count": len(request_candidates),
                    "contract_id": self.cross_index.request_provenance["contract_id"],
                    "canonical_persistence_allowed": False,
                },
            ]
        )
        return OfflineRunResult(
            execution_contract=contract,
            extracted_payload=copy.deepcopy(result.payload),
            audit_trace=tuple(audit),
            document_candidate_id=document_candidate_id,
            party_candidates=party_candidates,
            request_candidates=request_candidates,
            party_resolution_request=party_resolution_request,
        )

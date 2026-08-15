from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import zipfile

from .governance import ExecutionSnapshot, GovernanceError, GovernanceRuntime, HashMismatchError


class EvidencePackageError(GovernanceError):
    pass


@dataclass(frozen=True)
class EvidenceValidationReport:
    evidence_family_count: int
    evidence_type_count: int
    dictionary_entry_count: int
    evidence_function_count: int
    challenge_type_count: int
    authenticity_status_count: int
    admissibility_status_count: int
    relation_count: int
    transition_count: int
    custody_event_count: int
    validation_check_count: int
    entity_schema_count: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


class EvidenceRegistry:
    EXPECTED = {
        "evidence_families": 10,
        "evidence_types": 166,
        "dictionary_entries": 166,
        "evidence_functions": 28,
        "challenge_types": 16,
        "authenticity_statuses": 17,
        "admissibility_statuses": 11,
        "relations": 96,
        "transitions": 65,
        "custody_events": 21,
        "validation_checks": 40,
        "entity_schemas": 8,
    }

    REQUIRED_ONTOLOGY_RULES = {
        "EVIDENCE_METHOD != EVIDENCE_ITEM",
        "EVIDENCE_ITEM != EVIDENCE_REFERENCE",
        "FACT != EVIDENCE",
        "SUPPORTING_EVIDENCE != FACT_TRUTH",
        "AUTHENTICITY != INTEGRITY",
        "INTEGRITY != LAWFUL_ACQUISITION_OR_PRIVACY",
        "LAWFUL_ACQUISITION_OR_PRIVACY != ADMISSIBILITY",
        "ADMISSIBILITY != PROBATIVE_VALUE",
        "COURT_ADMISSION != COURT_RELIANCE",
        "COURT_RELIANCE != COURT_FACT_FINDING",
        "DIGITAL_FORMAT != AUTHENTIC",
        "UNLAWFUL_COLLECTION != AUTOMATIC_EXCLUSION",
        "NO_LLM_STABLE_IDS",
    }

    REQUIRED_DIGITAL_AXES = {
        "AUTHENTICITY_ATTRIBUTION",
        "INTEGRITY_PRESERVATION",
        "LAWFUL_ACQUISITION_PRIVACY",
        "ADMISSIBILITY",
        "PROBATIVE_VALUE",
        "HANDLING_CHAIN",
    }

    def __init__(self, package: Mapping[str, Any]) -> None:
        self.package = package
        taxonomy = package["evidence_taxonomy"]
        self.families = tuple(taxonomy.get("evidence_method_families", []))
        self.evidence_types: dict[str, Mapping[str, Any]] = {}
        self.family_for_type: dict[str, str] = {}
        for family in self.families:
            family_id = str(family["family_id"])
            for row in family.get("evidence_types", []):
                type_id = str(row["evidence_type_id"])
                if type_id in self.evidence_types:
                    raise EvidencePackageError(f"duplicate evidence type ID: {type_id}")
                self.evidence_types[type_id] = row
                self.family_for_type[type_id] = family_id

        self.evidence_functions = tuple(taxonomy.get("evidence_functions", []))
        self.challenge_types = tuple(taxonomy.get("challenge_types", []))
        self.authenticity_statuses = tuple(taxonomy.get("authenticity_statuses", []))
        self.admissibility_statuses = tuple(taxonomy.get("admissibility_statuses", []))

        dictionary = package["evidence_dictionary"].get("evidence_dictionary", [])
        self.dictionary_entries = {str(row["evidence_type_id"]): row for row in dictionary}

        relations = package["evidence_relations"]
        self.relationship_types = tuple(relations.get("relationship_types", []))
        self.transition_rules = tuple(relations.get("evidence_status_transition_rules", []))
        self.custody_event_types = tuple(relations.get("chain_of_custody_event_types", []))
        self.relation_ids = {str(row["relation_id"]) for row in self.relationship_types}

        self.entity_schemas = tuple(package["runtime_contracts"].get("entity_schemas", []))

    def validate(self) -> EvidenceValidationReport:
        errors: list[str] = []
        actual = {
            "evidence_families": len(self.families),
            "evidence_types": len(self.evidence_types),
            "dictionary_entries": len(self.dictionary_entries),
            "evidence_functions": len(self.evidence_functions),
            "challenge_types": len(self.challenge_types),
            "authenticity_statuses": len(self.authenticity_statuses),
            "admissibility_statuses": len(self.admissibility_statuses),
            "relations": len(self.relationship_types),
            "transitions": len(self.transition_rules),
            "custody_events": len(self.custody_event_types),
            "validation_checks": len(self.package.get("validation_report", {}).get("checks", [])),
            "entity_schemas": len(self.entity_schemas),
        }
        for key, expected in self.EXPECTED.items():
            if actual[key] != expected:
                errors.append(f"{key}: expected {expected}, got {actual[key]}")

        if set(self.dictionary_entries) != set(self.evidence_types):
            errors.append("evidence dictionary is not in exact taxonomy parity")

        for type_id, row in self.dictionary_entries.items():
            if row.get("evidence_family_id") != self.family_for_type[type_id]:
                errors.append(f"dictionary family mismatch: {type_id}")
                break

        relation_ids = [row.get("relation_id") for row in self.relationship_types]
        if len(relation_ids) != len(set(relation_ids)):
            errors.append("duplicate EVIDENCE relation IDs")

        transition_ids = [row.get("transition_id") for row in self.transition_rules]
        if len(transition_ids) != len(set(transition_ids)):
            errors.append("duplicate EVIDENCE transition IDs")

        custody_ids = [row.get("event_type_id") for row in self.custody_event_types]
        if len(custody_ids) != len(set(custody_ids)):
            errors.append("duplicate EVIDENCE custody event IDs")

        preservation = self.package.get("preservation_report", {})
        if preservation.get("stable_ids_added") not in (0, False):
            errors.append("source added stable IDs")
        if preservation.get("stable_ids_deleted") not in (0, False):
            errors.append("source deleted stable IDs")
        if preservation.get("deleted_valid_baseline_records") not in (0, False):
            errors.append("source deleted valid baseline records")

        governance = self.package.get("governance", {})
        if governance.get("runtime_activation") != "NOT_RUNTIME_ACTIVATED":
            errors.append("unexpected source runtime activation state")
        if governance.get("sandbox_activation") != "BLOCKED_PENDING_RUNTIME_VALIDATION":
            errors.append("unexpected source sandbox activation state")
        if governance.get("automatic_legal_effect") is not False:
            errors.append("automatic legal effect unexpectedly enabled")
        if governance.get("automatic_admissibility_decision") is not False:
            errors.append("automatic admissibility unexpectedly enabled")
        if governance.get("automatic_probative_value_decision") is not False:
            errors.append("automatic probative value unexpectedly enabled")
        if governance.get("llm_stable_id_generation_allowed") is not False:
            errors.append("LLM stable ID generation unexpectedly enabled")

        alignment = self.package.get("legal_rebuild_alignment", {})
        ontology = set(alignment.get("immutable_ontology_rules", []))
        if not self.REQUIRED_ONTOLOGY_RULES.issubset(ontology):
            errors.append("required evidence ontology guards are missing")
        axes = {row.get("axis") for row in alignment.get("digital_evidence_axes", [])}
        if axes != self.REQUIRED_DIGITAL_AXES:
            errors.append("digital evidence axes changed")

        validation = self.package.get("validation_report", {})
        if validation.get("validation_status") != "PASS_WITH_GOVERNANCE_GUARDS":
            errors.append("source validation status is not guarded PASS")
        if validation.get("failures"):
            errors.append("source validation reports failures")

        gates = {row.get("gate_id"): row for row in self.package.get("deployment_gates", [])}
        if gates.get("GATE_STRUCTURAL_VALIDATION", {}).get("status") != "PASS":
            errors.append("structural gate is not PASS")
        if gates.get("GATE_CROSS_INDEX_LEGAL_ALIGNMENT", {}).get("status") != "PASS":
            errors.append("cross-index legal alignment gate is not PASS")
        if gates.get("GATE_RUNTIME_LIVE_VALIDATION", {}).get("status") != "NOT_RUN_RUNTIME_UNAVAILABLE":
            errors.append("unexpected source runtime-live-validation state")

        required_relations = {
            "EVIDENCE_REFERENCE_MENTIONED_IN_DOCUMENT",
            "EVIDENCE_EXTRACTED_FROM_DOCUMENT",
            "EVIDENCE_SUPPORTS_FACT",
            "COURT_ADMITTED_EVIDENCE",
            "COURT_RELIED_ON_EVIDENCE",
            "COURT_EXCLUDED_EVIDENCE",
        }
        if not required_relations.issubset(self.relation_ids):
            errors.append("required EVIDENCE cross-index relations missing")

        return EvidenceValidationReport(
            evidence_family_count=actual["evidence_families"],
            evidence_type_count=actual["evidence_types"],
            dictionary_entry_count=actual["dictionary_entries"],
            evidence_function_count=actual["evidence_functions"],
            challenge_type_count=actual["challenge_types"],
            authenticity_status_count=actual["authenticity_statuses"],
            admissibility_status_count=actual["admissibility_statuses"],
            relation_count=actual["relations"],
            transition_count=actual["transitions"],
            custody_event_count=actual["custody_events"],
            validation_check_count=actual["validation_checks"],
            entity_schema_count=actual["entity_schemas"],
            errors=tuple(errors),
        )

    def type(self, type_id: str) -> Mapping[str, Any]:
        try:
            return self.evidence_types[type_id]
        except KeyError as exc:
            raise EvidencePackageError(f"unknown EVIDENCE canonical type: {type_id}") from exc

    def family_id_for(self, type_id: str) -> str:
        try:
            return self.family_for_type[type_id]
        except KeyError as exc:
            raise EvidencePackageError(f"unknown EVIDENCE canonical type: {type_id}") from exc

    def dictionary_for(self, type_id: str) -> Mapping[str, Any]:
        try:
            return self.dictionary_entries[type_id]
        except KeyError as exc:
            raise EvidencePackageError(f"missing EVIDENCE dictionary entry: {type_id}") from exc


@dataclass(frozen=True)
class LoadedEvidencePackage:
    delivery_zip_sha256: str
    package_sha256: str
    validation_report_sha256: str
    changeset_sha256: str
    registry: EvidenceRegistry
    registry_report: EvidenceValidationReport
    snapshot: ExecutionSnapshot
    runtime_status: str
    activation_blockers: tuple[str, ...]


class EvidencePackageLoader:
    PACKAGE_NAME = "QANUN_AI_SY_EVIDENCE_BACKEND_COMPLETE_V1.1.0_LEGAL_REBUILT_GOVERNANCE_CANDIDATE.json"
    VALIDATION_NAME = "QANUN_AI_EVIDENCE_REBUILD_VALIDATION_REPORT_V1.1.0.json"
    CHANGESET_NAME = "QANUN_AI_EVIDENCE_REBUILD_CHANGESET_V1.1.0.json"
    MANIFEST_NAME = "DELIVERY_MANIFEST_V1.1.0.json"

    def __init__(self, runtime: GovernanceRuntime) -> None:
        self.runtime = runtime

    @staticmethod
    def _digest(payload: bytes) -> str:
        return sha256(payload).hexdigest()

    def load(self, zip_path: str | Path) -> LoadedEvidencePackage:
        path = Path(zip_path)
        zip_bytes = path.read_bytes()
        delivery_zip_sha256 = self._digest(zip_bytes)

        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required = {self.PACKAGE_NAME, self.VALIDATION_NAME, self.CHANGESET_NAME, self.MANIFEST_NAME}
            if not required.issubset(names):
                raise EvidencePackageError(f"EVIDENCE delivery missing files: {sorted(required - names)}")

            manifest = json.loads(archive.read(self.MANIFEST_NAME))
            rows = {row["file_name"]: row for row in manifest.get("files", [])}
            for name in (self.PACKAGE_NAME, self.VALIDATION_NAME, self.CHANGESET_NAME):
                if name not in rows:
                    raise EvidencePackageError(f"manifest missing {name}")
                payload = archive.read(name)
                row = rows[name]
                if len(payload) != row["size_bytes"]:
                    raise EvidencePackageError(f"size mismatch: {name}")
                actual = self._digest(payload)
                if actual != row["sha256"]:
                    raise HashMismatchError(f"{name}: expected {row['sha256']}, got {actual}")

            package_bytes = archive.read(self.PACKAGE_NAME)
            validation_bytes = archive.read(self.VALIDATION_NAME)
            changeset_bytes = archive.read(self.CHANGESET_NAME)
            package = json.loads(package_bytes)
            validation = json.loads(validation_bytes)

        if validation.get("validation_status") != "PASS_WITH_GOVERNANCE_GUARDS":
            raise EvidencePackageError("EVIDENCE validation report status is not guarded PASS")
        if validation.get("failures"):
            raise EvidencePackageError("EVIDENCE delivery reports validation failures")
        summary = validation.get("summary", {})
        if summary.get("validation_failure_count") != 0:
            raise EvidencePackageError("EVIDENCE validation failure count is non-zero")
        if summary.get("validation_check_count") != 40 or summary.get("validation_pass_count") != 40:
            raise EvidencePackageError("EVIDENCE source validation is not 40/40 PASS")
        if validation.get("runtime_validation", {}).get("status") != "NOT_RUN_RUNTIME_UNAVAILABLE":
            raise EvidencePackageError("unexpected source runtime validation status")

        registry = EvidenceRegistry(package)
        report = registry.validate()
        if not report.valid:
            raise EvidencePackageError("EVIDENCE registry validation failed: " + "; ".join(report.errors[:10]))

        package_sha256 = self._digest(package_bytes)
        if package_sha256 != validation.get("rebuilt_package_sha256"):
            raise HashMismatchError("rebuilt EVIDENCE package hash differs from validation report")

        self.runtime.register_bytes(
            artifact_id="EVIDENCE",
            version="1.1.0",
            expected_sha256=package_sha256,
            payload=package_bytes,
        )
        snapshot = self.runtime.snapshot(environment="registry_import")
        blockers = (
            "EVIDENCE_SOURCE_RUNTIME_NOT_ACTIVATED",
            "SOURCE_RUNTIME_LIVE_VALIDATION_NOT_RUN",
            "LEGAL_ARTICLE_MAPPING_PENDING",
            "SYRIAN_CORPUS_REGRESSION_PENDING",
            "NO_AUTOMATIC_ADMISSIBILITY_DECISION",
            "NO_AUTOMATIC_PROBATIVE_VALUE_DECISION",
            "NO_AUTOMATIC_LEGAL_EFFECT",
            "NO_STABLE_INSTANCE_ID_SERVICE",
            "NO_CANONICAL_RELATION_PERSISTENCE",
            "ENTITY_RESOLUTION_REQUIRED",
            "LIVE_LLM_SCHEMA_BINDING_NOT_RUN",
        )
        return LoadedEvidencePackage(
            delivery_zip_sha256=delivery_zip_sha256,
            package_sha256=package_sha256,
            validation_report_sha256=self._digest(validation_bytes),
            changeset_sha256=self._digest(changeset_bytes),
            registry=registry,
            registry_report=report,
            snapshot=snapshot,
            runtime_status="LOADED_NOT_ACTIVATED",
            activation_blockers=blockers,
        )

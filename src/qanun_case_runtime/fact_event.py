from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import zipfile

from .governance import ExecutionSnapshot, GovernanceError, GovernanceRuntime, HashMismatchError


class FactEventPackageError(GovernanceError):
    pass


@dataclass(frozen=True)
class FactEventValidationReport:
    fact_family_count: int
    fact_type_count: int
    event_family_count: int
    event_type_count: int
    state_family_count: int
    state_type_count: int
    assertion_type_count: int
    fact_status_count: int
    date_role_count: int
    relation_count: int
    transition_count: int
    validation_check_count: int
    unresolved_extension_count: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


class FactEventRegistry:
    EXPECTED = {
        "fact_families": 13,
        "fact_types": 69,
        "event_families": 18,
        "event_types": 93,
        "state_families": 11,
        "state_types": 38,
        "assertion_types": 31,
        "fact_statuses": 24,
        "date_roles": 71,
        "relations": 100,
        "transitions": 28,
        "validation_checks": 40,
        "unresolved_extensions": 2,
    }

    def __init__(self, package: Mapping[str, Any]) -> None:
        self.package = package
        taxonomy = package["taxonomy"]
        self.fact_families = tuple(taxonomy.get("fact_families", []))
        self.event_families = tuple(taxonomy.get("event_families", []))
        self.state_families = tuple(taxonomy.get("state_families", []))
        self.fact_types = {
            row["fact_type_id"]: {**row, "_family_id": family["family_id"]}
            for family in self.fact_families
            for row in family.get("fact_types", [])
        }
        self.event_types = {
            row["event_type_id"]: {**row, "_family_id": family["family_id"]}
            for family in self.event_families
            for row in family.get("event_types", [])
        }
        self.state_types = {
            row["state_type_id"]: row for row in taxonomy.get("state_types", [])
        }
        self.assertion_types = tuple(taxonomy.get("assertion_types", []))
        self.fact_statuses = tuple(taxonomy.get("fact_statuses", []))
        self.date_roles = tuple(taxonomy.get("date_roles", []))
        relations = package["relations"]
        self.relationship_types = tuple(relations.get("relationship_types", []))
        self.transition_rules = tuple(relations.get("status_transition_rules", []))
        self.relation_ids = {row["relation_id"] for row in self.relationship_types}
        self.dictionary_entries: dict[str, Mapping[str, Any]] = {}
        for family in package["enrichment"].get("family_dictionaries", []):
            for row in family["content"].get("dictionary_entries", []):
                self.dictionary_entries[row["type_id"]] = row
        self.unresolved_extensions = tuple(
            package.get("rebuild_legal_alignment", {}).get(
                "unresolved_canonical_extensions", []
            )
        )

    def validate(self) -> FactEventValidationReport:
        errors: list[str] = []
        actual = {
            "fact_families": len(self.fact_families),
            "fact_types": len(self.fact_types),
            "event_families": len(self.event_families),
            "event_types": len(self.event_types),
            "state_families": len(self.state_families),
            "state_types": len(self.state_types),
            "assertion_types": len(self.assertion_types),
            "fact_statuses": len(self.fact_statuses),
            "date_roles": len(self.date_roles),
            "relations": len(self.relationship_types),
            "transitions": len(self.transition_rules),
            "validation_checks": len(
                self.package.get("taxonomy_validation", {}).get("checks", [])
            ),
            "unresolved_extensions": len(self.unresolved_extensions),
        }
        for key, expected in self.EXPECTED.items():
            if actual[key] != expected:
                errors.append(f"{key}: expected {expected}, got {actual[key]}")

        expected_dictionary_ids = set(self.fact_types) | set(self.event_types)
        if set(self.dictionary_entries) != expected_dictionary_ids:
            errors.append("FACT/EVENT enrichment dictionary is not in taxonomy parity")

        relation_ids = [row.get("relation_id") for row in self.relationship_types]
        if len(relation_ids) != len(set(relation_ids)):
            errors.append("duplicate FACT_EVENT relation IDs")

        source_release = self.package.get("release", {})
        delivery = self.package.get("delivery", {})
        if source_release.get("runtime_activation_state") != "NOT_RUNTIME_ACTIVATED":
            errors.append("unexpected source runtime activation state")
        if delivery.get("sandbox_status") != "BLOCKED_PENDING_RUNTIME_VALIDATION":
            errors.append("unexpected source sandbox status")
        if source_release.get("stable_id_policy") != "NO_NEW_STABLE_IDS_GENERATED":
            errors.append("source stable-ID policy changed")

        stable_id_report = self.package.get("rebuild_legal_alignment", {}).get(
            "stable_id_preservation", {}
        )
        if stable_id_report.get("new_stable_ids_generated") not in (0, False):
            errors.append("FACT_EVENT source generated new stable IDs")

        for extension in self.unresolved_extensions:
            if extension.get("new_stable_id") not in (None, "", False):
                errors.append("unresolved extension unexpectedly contains stable ID")

        principles = set(
            self.package.get("legal_governance", {}).get(
                "non_negotiable_principles", []
            )
        )
        required_principles = {
            "PARTY_ASSERTION_IS_NOT_FACT_TRUTH",
            "FACT_IS_NOT_EVIDENCE",
            "FACT_IS_NOT_DEFENSE_OR_REQUEST",
            "EVENT_IS_NOT_DATE_MENTION",
            "LEGAL_CHARACTERIZATION_IS_NOT_RAW_FACT",
            "POSSESSION_IS_NOT_OWNERSHIP",
            "SUPPORTING_EVIDENCE_IS_NOT_TRUTH",
            "COURT_FINDING_REQUIRES_EXPLICIT_COURT_SOURCE",
            "QUOTED_OR_HISTORICAL_MENTION_IS_NOT_CURRENT_ACT",
            "TEMPORAL_SEQUENCE_IS_NOT_CAUSATION",
            "NO_LLM_STABLE_IDS",
        }
        if not required_principles.issubset(principles):
            errors.append("required FACT_EVENT legal-governance principles are missing")

        return FactEventValidationReport(
            fact_family_count=actual["fact_families"],
            fact_type_count=actual["fact_types"],
            event_family_count=actual["event_families"],
            event_type_count=actual["event_types"],
            state_family_count=actual["state_families"],
            state_type_count=actual["state_types"],
            assertion_type_count=actual["assertion_types"],
            fact_status_count=actual["fact_statuses"],
            date_role_count=actual["date_roles"],
            relation_count=actual["relations"],
            transition_count=actual["transitions"],
            validation_check_count=actual["validation_checks"],
            unresolved_extension_count=actual["unresolved_extensions"],
            errors=tuple(errors),
        )

    def kind_for(self, type_id: str) -> str:
        if type_id in self.fact_types:
            return "FACT"
        if type_id in self.event_types:
            return "EVENT"
        if type_id in self.state_types:
            return "STATE"
        raise FactEventPackageError(f"unknown FACT_EVENT canonical type: {type_id}")

    def family_id_for(self, type_id: str) -> str:
        if type_id in self.fact_types:
            return str(self.fact_types[type_id]["_family_id"])
        if type_id in self.event_types:
            return str(self.event_types[type_id]["_family_id"])
        if type_id in self.state_types:
            return str(self.state_types[type_id]["state_family_id"])
        raise FactEventPackageError(f"unknown FACT_EVENT canonical type: {type_id}")


@dataclass(frozen=True)
class LoadedFactEventPackage:
    delivery_zip_sha256: str
    package_sha256: str
    validation_report_sha256: str
    changeset_sha256: str
    registry: FactEventRegistry
    registry_report: FactEventValidationReport
    snapshot: ExecutionSnapshot
    runtime_status: str
    activation_blockers: tuple[str, ...]


class FactEventPackageLoader:
    PACKAGE_NAME = (
        "QANUN_AI_FACT_EVENT_BACKEND_SINGLE_FILE_V0.3.0_"
        "LEGAL_REBUILT_GOVERNANCE_CANDIDATE.json"
    )
    VALIDATION_NAME = "QANUN_AI_FACT_EVENT_REBUILD_VALIDATION_REPORT_V0.3.0.json"
    CHANGESET_NAME = "QANUN_AI_FACT_EVENT_REBUILD_CHANGESET_V0.3.0.json"
    MANIFEST_NAME = "DELIVERY_MANIFEST_V0.3.0.json"

    def __init__(self, runtime: GovernanceRuntime) -> None:
        self.runtime = runtime

    @staticmethod
    def _digest(payload: bytes) -> str:
        return sha256(payload).hexdigest()

    def load(self, zip_path: str | Path) -> LoadedFactEventPackage:
        path = Path(zip_path)
        zip_bytes = path.read_bytes()
        delivery_zip_sha256 = self._digest(zip_bytes)
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required = {
                self.PACKAGE_NAME,
                self.VALIDATION_NAME,
                self.CHANGESET_NAME,
                self.MANIFEST_NAME,
            }
            if not required.issubset(names):
                raise FactEventPackageError(
                    f"FACT_EVENT delivery missing files: {sorted(required - names)}"
                )
            manifest = json.loads(archive.read(self.MANIFEST_NAME))
            rows = {row["file_name"]: row for row in manifest.get("files", [])}
            for name in (self.PACKAGE_NAME, self.VALIDATION_NAME, self.CHANGESET_NAME):
                if name not in rows:
                    raise FactEventPackageError(f"manifest missing {name}")
                payload = archive.read(name)
                row = rows[name]
                if len(payload) != row["size_bytes"]:
                    raise FactEventPackageError(f"size mismatch: {name}")
                actual = self._digest(payload)
                if actual != row["sha256"]:
                    raise HashMismatchError(
                        f"{name}: expected {row['sha256']}, got {actual}"
                    )
            package_bytes = archive.read(self.PACKAGE_NAME)
            validation_bytes = archive.read(self.VALIDATION_NAME)
            changeset_bytes = archive.read(self.CHANGESET_NAME)
            package = json.loads(package_bytes)
            validation = json.loads(validation_bytes)

        if validation.get("validation_status") != "PASS_WITH_GOVERNANCE_GUARDS":
            raise FactEventPackageError("FACT_EVENT validation report status is not guarded PASS")
        if validation.get("failures"):
            raise FactEventPackageError("FACT_EVENT delivery reports validation failures")
        if validation.get("summary", {}).get("validation_failure_count") != 0:
            raise FactEventPackageError("FACT_EVENT validation failure count is non-zero")
        if validation.get("summary", {}).get("validation_check_count") != 40:
            raise FactEventPackageError("FACT_EVENT validation check count is not 40")
        if validation.get("summary", {}).get("validation_pass_count") != 40:
            raise FactEventPackageError("FACT_EVENT validation pass count is not 40")
        if validation.get("runtime_tests", {}).get("status") != "NOT_RUN_RUNTIME_UNAVAILABLE":
            raise FactEventPackageError("unexpected source runtime-test status")

        registry = FactEventRegistry(package)
        report = registry.validate()
        if not report.valid:
            raise FactEventPackageError(
                "FACT_EVENT registry validation failed: " + "; ".join(report.errors[:10])
            )

        package_sha256 = self._digest(package_bytes)
        if package_sha256 != validation.get("rebuilt_package_sha256"):
            raise HashMismatchError("rebuilt package hash differs from validation report")

        self.runtime.register_bytes(
            artifact_id="FACT_EVENT",
            version="0.3.0",
            expected_sha256=package_sha256,
            payload=package_bytes,
        )
        snapshot = self.runtime.snapshot(environment="registry_import")
        blockers = (
            "FACT_EVENT_SOURCE_RUNTIME_NOT_ACTIVATED",
            "FACT_EVENT_SANDBOX_BLOCKED_PENDING_RUNTIME_VALIDATION",
            "CANONICAL_REQUEST_REGISTRY_MAPPING_REQUIRED",
            "CANONICAL_DEFENSE_REGISTRY_MAPPING_REQUIRED",
            "DECISION_POSITION_ARBITRAL_AWARD_MODEL_REQUIRED",
            "LEGAL_REFERENCE_CURRENT_LAW_RESOLVER_REQUIRED",
            "DEADLINE_RULE_REGISTRY_REQUIRED",
            "ENTITY_RESOLUTION_REQUIRED",
            "STABLE_INSTANCE_ID_SERVICE_REQUIRED",
            "RELATION_PERSISTENCE_IDEMPOTENCY_REQUIRED",
            "LIVE_LLM_SCHEMA_BINDING_NOT_RUN",
        )
        return LoadedFactEventPackage(
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

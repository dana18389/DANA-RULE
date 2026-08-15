from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import zipfile

from .governance import GovernanceError, GovernanceRuntime, HashMismatchError, ExecutionSnapshot


class DefensePackageError(GovernanceError):
    pass


@dataclass(frozen=True)
class DefenseRegistryValidationReport:
    registry_count: int
    canonical_count: int
    validated_count: int
    scope_guarded_count: int
    merge_count: int
    reclassify_count: int
    family_count: int
    relation_count: int
    transition_count: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class DefenseRoutingDecision:
    source_defense_type_id: str
    route_kind: str
    target: str | tuple[str, ...] | None
    effective_record_class: str | None
    final_validation_decision: str
    is_canonical_defense_candidate: bool
    requires_current_law_validity_check: bool
    automatic_legal_effect_allowed: bool


class DefenseRegistry:
    EXPECTED = {
        "registry": 260,
        "canonical": 207,
        "validated": 98,
        "scope_guarded": 109,
        "merge": 26,
        "reclassify": 27,
        "families": 13,
        "relations": 74,
        "transitions": 21,
    }

    def __init__(self, package: Mapping[str, Any]) -> None:
        self.package = package
        self.records = {
            row["defense_type_id"]: row for row in package.get("defense_dictionary", [])
        }
        self.taxonomy_ids = {
            row["defense_type_id"]
            for family in package.get("taxonomy", {}).get("defense_families", [])
            for row in family.get("defense_types", [])
        }
        relations = package.get("defense_relations", {})
        self.relationship_types = tuple(relations.get("relationship_types", []))
        self.transition_rules = tuple(relations.get("defense_transition_rules", []))
        self.instance_model_required_fields = tuple(
            relations.get("instance_model_required_fields", [])
        )

    def validate(self) -> DefenseRegistryValidationReport:
        errors: list[str] = []
        statuses: dict[str, int] = {}
        for row in self.records.values():
            status = row.get("final_validation_decision", "UNKNOWN")
            statuses[status] = statuses.get(status, 0) + 1

        canonical = [
            row for row in self.records.values()
            if row.get("effective_index_membership") == "DEFENSE_CANONICAL"
        ]
        families = self.package.get("taxonomy", {}).get("defense_families", [])

        actual = {
            "registry": len(self.records),
            "canonical": len(canonical),
            "validated": statuses.get("VALIDATED", 0),
            "scope_guarded": statuses.get("VALIDATED_WITH_SCOPE_LIMIT", 0),
            "merge": statuses.get("MERGE_ENRICH_EXISTING", 0),
            "reclassify": statuses.get("RECLASSIFY_NOT_DEFENSE", 0),
            "families": len(families),
            "relations": len(self.relationship_types),
            "transitions": len(self.transition_rules),
        }
        for key, expected in self.EXPECTED.items():
            if actual[key] != expected:
                errors.append(f"{key}: expected {expected}, got {actual[key]}")

        if self.taxonomy_ids != set(self.records):
            errors.append("taxonomy and dictionary defense IDs are not in parity")

        relation_ids = [row.get("relation_id") for row in self.relationship_types]
        if len(relation_ids) != len(set(relation_ids)):
            errors.append("duplicate defense relation IDs")
        relation_id_set = set(relation_ids)
        for row in self.relationship_types:
            inverse = row.get("inverse_relation_id")
            if inverse and inverse not in relation_id_set:
                errors.append(f"missing inverse relation {inverse}")

        required_record_fields = (
            "defense_type_id",
            "defense_family_id",
            "defense_name_ar",
            "exact_defense_phrases",
            "factual_elements_to_extract",
            "expected_target_types",
            "expected_requested_effects",
            "final_validation_decision",
            "effective_index_membership",
        )
        for row in canonical:
            missing = [
                field for field in required_record_fields
                if field not in row or row[field] in (None, "", [])
            ]
            if missing:
                errors.append(
                    f"{row.get('defense_type_id')}: missing canonical fields {missing}"
                )

        runtime_policy = self.package.get("release", {}).get("runtime_policy", {})
        if runtime_policy.get("package_enabled") is not False:
            errors.append("DEFENSE package must remain disabled before runtime gate completion")
        if runtime_policy.get("stable_instance_ids_generated_by_llm") is not False:
            errors.append("LLM stable defense IDs must remain disabled")
        if runtime_policy.get("automatic_court_disposition_inference") is not False:
            errors.append("automatic court disposition inference must remain disabled")
        if runtime_policy.get("automatic_legal_effects_enabled") is True:
            errors.append("automatic legal effects must remain disabled")

        return DefenseRegistryValidationReport(
            registry_count=actual["registry"],
            canonical_count=actual["canonical"],
            validated_count=actual["validated"],
            scope_guarded_count=actual["scope_guarded"],
            merge_count=actual["merge"],
            reclassify_count=actual["reclassify"],
            family_count=actual["families"],
            relation_count=actual["relations"],
            transition_count=actual["transitions"],
            errors=tuple(errors),
        )

    def route(self, defense_type_id: str) -> DefenseRoutingDecision:
        try:
            row = self.records[defense_type_id]
        except KeyError as exc:
            raise DefensePackageError(f"unknown defense_type_id: {defense_type_id}") from exc

        final = row.get("final_validation_decision", "UNKNOWN")
        if row.get("effective_index_membership") == "DEFENSE_CANONICAL":
            route_kind = "CANONICAL_DEFENSE_CANDIDATE"
            target: str | tuple[str, ...] | None = defense_type_id
        else:
            routing = row.get("compatibility_routing", {})
            raw_target = routing.get("target", row.get("migration_destination"))
            if isinstance(raw_target, list):
                target = tuple(str(x) for x in raw_target)
            elif raw_target is None:
                target = None
            else:
                target = str(raw_target)
            route_kind = (
                "MERGE_COMPATIBILITY_ROUTE"
                if final == "MERGE_ENRICH_EXISTING"
                else "RECLASSIFY_OUT_OF_DEFENSE"
            )

        return DefenseRoutingDecision(
            source_defense_type_id=defense_type_id,
            route_kind=route_kind,
            target=target,
            effective_record_class=row.get("effective_record_class"),
            final_validation_decision=final,
            is_canonical_defense_candidate=bool(row.get("is_canonical_defense_candidate")),
            requires_current_law_validity_check=bool(
                row.get("requires_current_law_validity_check")
            ),
            automatic_legal_effect_allowed=bool(
                row.get("automatic_legal_effect_allowed", False)
            ),
        )


@dataclass(frozen=True)
class LoadedDefensePackage:
    delivery_zip_sha256: str
    package_sha256: str
    validation_report_sha256: str
    changeset_sha256: str
    registry: DefenseRegistry
    registry_report: DefenseRegistryValidationReport
    snapshot: ExecutionSnapshot
    runtime_status: str
    activation_blockers: tuple[str, ...]


class DefensePackageLoader:
    PACKAGE_NAME = "QANUN_AI_DEFENSE_BACKEND_PACKAGE_v1.3.0_REBUILT_GOVERNANCE_CANDIDATE.json"
    VALIDATION_NAME = "QANUN_AI_DEFENSE_REBUILD_VALIDATION_REPORT_v1.3.0.json"
    CHANGESET_NAME = "QANUN_AI_DEFENSE_REBUILD_CHANGESET_v1.3.0.json"
    MANIFEST_NAME = "DELIVERY_MANIFEST_v1.3.0.json"

    def __init__(self, runtime: GovernanceRuntime) -> None:
        self.runtime = runtime

    @staticmethod
    def _digest(payload: bytes) -> str:
        return sha256(payload).hexdigest()

    def load(self, zip_path: str | Path) -> LoadedDefensePackage:
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
                raise DefensePackageError(
                    f"DEFENSE delivery missing files: {sorted(required - names)}"
                )

            manifest = json.loads(archive.read(self.MANIFEST_NAME))
            manifest_rows = {row["name"]: row for row in manifest.get("files", [])}
            for name in (self.PACKAGE_NAME, self.VALIDATION_NAME, self.CHANGESET_NAME):
                if name not in manifest_rows:
                    raise DefensePackageError(f"manifest missing {name}")
                payload = archive.read(name)
                row = manifest_rows[name]
                if len(payload) != row["size_bytes"]:
                    raise DefensePackageError(f"size mismatch: {name}")
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

        if validation.get("validation_status") != "PASS":
            raise DefensePackageError("DEFENSE delivery validation report is not PASS")
        if validation.get("blocking_failures"):
            raise DefensePackageError("DEFENSE delivery contains blocking validation failures")

        registry = DefenseRegistry(package)
        report = registry.validate()
        if not report.valid:
            raise DefensePackageError(
                "DEFENSE registry validation failed: " + "; ".join(report.errors[:10])
            )

        release = package.get("release", {})
        runtime_policy = release.get("runtime_policy", {})
        if release.get("package_version") != "1.3.0":
            raise DefensePackageError("unexpected DEFENSE package version")
        if runtime_policy.get("package_enabled") is not False:
            raise DefensePackageError("DEFENSE v1.3.0 must not be activated by this loader")

        package_sha256 = self._digest(package_bytes)
        self.runtime.register_bytes(
            artifact_id="DEFENSE",
            version="1.3.0",
            expected_sha256=package_sha256,
            payload=package_bytes,
        )
        snapshot = self.runtime.snapshot(environment="registry_import")

        blockers = (
            "DEFENSE_PACKAGE_SOURCE_DISABLED",
            "DEFENSE_RUNTIME_VALIDATION_NOT_RUN",
            "BACKEND_STABLE_ID_SERVICE_REQUIRED",
            "ENTITY_RESOLUTION_REQUIRED",
            "PERSISTENCE_IDEMPOTENCY_REQUIRED",
            "RELATION_RESOLUTION_REQUIRED",
            "LIVE_LLM_SCHEMA_BINDING_REQUIRED",
            "LIVE_CASE_REGRESSION_REQUIRED",
        )
        return LoadedDefensePackage(
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


@dataclass(frozen=True)
class DefenseShadowCandidate:
    candidate_id: str
    case_id: str
    source_document_id: str
    source_defense_type_id: str
    canonical_defense_type_id: str | None
    defense_family_id: str | None
    effective_record_class: str | None
    raw_text: str
    source_quote: str
    litigation_stage: str
    certainty: str
    raised_by_party_candidate_ref: str | None
    target_type: str | None
    target_candidate_ref: str | None
    requested_effects: tuple[str, ...]
    status: str
    stable_defense_id: None = None
    canonical_persistence_allowed: bool = False
    automatic_legal_effect_allowed: bool = False
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class DefenseShadowObservation:
    routing: DefenseRoutingDecision
    candidate: DefenseShadowCandidate | None


class DefenseShadowEngine:
    """Candidate-only DEFENSE routing. It never satisfies the final instance contract."""

    def __init__(self, loaded: LoadedDefensePackage) -> None:
        self.loaded = loaded
        self.registry = loaded.registry

    @staticmethod
    def _candidate_id(payload: Mapping[str, Any]) -> str:
        canonical = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return f"defcand_{sha256(canonical).hexdigest()[:24]}"

    def observe(
        self,
        *,
        case_id: str,
        source_document_id: str,
        defense_type_id: str,
        raw_text: str,
        source_quote: str,
        litigation_stage: str,
        certainty: str = "EXPLICIT",
        raised_by_party_candidate_ref: str | None = None,
        target_type: str | None = None,
        target_candidate_ref: str | None = None,
        requested_effects: tuple[str, ...] = (),
    ) -> DefenseShadowObservation:
        routing = self.registry.route(defense_type_id)
        if routing.route_kind != "CANONICAL_DEFENSE_CANDIDATE":
            return DefenseShadowObservation(routing=routing, candidate=None)

        row = self.registry.records[defense_type_id]
        blockers = list(self.loaded.activation_blockers)
        if routing.requires_current_law_validity_check:
            blockers.append("CURRENT_LAW_VALIDITY_RECHECK_REQUIRED")
        if raised_by_party_candidate_ref is None:
            blockers.append("RAISER_PARTY_NOT_RESOLVED")
        if target_type and target_candidate_ref is None:
            blockers.append("TARGET_NOT_RESOLVED")

        seed = {
            "case_id": case_id,
            "source_document_id": source_document_id,
            "defense_type_id": defense_type_id,
            "raw_text": raw_text,
            "source_quote": source_quote,
            "litigation_stage": litigation_stage,
            "raised_by_party_candidate_ref": raised_by_party_candidate_ref,
            "target_type": target_type,
            "target_candidate_ref": target_candidate_ref,
            "requested_effects": list(requested_effects),
        }
        candidate = DefenseShadowCandidate(
            candidate_id=self._candidate_id(seed),
            case_id=case_id,
            source_document_id=source_document_id,
            source_defense_type_id=defense_type_id,
            canonical_defense_type_id=defense_type_id,
            defense_family_id=row.get("defense_family_id"),
            effective_record_class=routing.effective_record_class,
            raw_text=raw_text,
            source_quote=source_quote,
            litigation_stage=litigation_stage,
            certainty=certainty,
            raised_by_party_candidate_ref=raised_by_party_candidate_ref,
            target_type=target_type,
            target_candidate_ref=target_candidate_ref,
            requested_effects=tuple(requested_effects),
            status="SHADOW_CANDIDATE_ONLY",
            automatic_legal_effect_allowed=False,
            blockers=tuple(sorted(set(blockers))),
        )
        return DefenseShadowObservation(routing=routing, candidate=candidate)

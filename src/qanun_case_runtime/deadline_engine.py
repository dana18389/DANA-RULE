from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path
import calendar
import hashlib
import json
from typing import Any, Dict, Iterable, Optional, Tuple

PACKAGE_SHA256 = "46dd7c9ba5b2c28f25641f72ca8d86b9fc919ab69a1dd6f3014f401830cdd09c"
REPORT_SHA256 = "c2de4091c3706f7c05884ef5efe986199a6fd8188b35576523549312f5789f72"
SOURCE_PACKAGE_SHA256 = "f2055b759f0f94cf802347700ca606ba89e0f622ca50896b19e0140f61e1279f"
FROZEN_CHAIN_HEAD_SHA = "26f78e5595092dc2205e67ea67e373730e0c2eff"
PACKAGE_VERSION = "1.1.0-legal-rebuild-candidate.2026-08-16"


class DeadlineEnginePackageError(RuntimeError):
    pass


def _sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _projection(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class LoadedDeadlineEnginePackage:
    package: Dict[str, Any]
    report_text: str
    rules_by_id: Dict[str, Dict[str, Any]]
    deadline_type_ids: Tuple[str, ...]
    trigger_event_type_ids: Tuple[str, ...]
    relationship_type_ids: Tuple[str, ...]
    modifier_only_rule_ids: Tuple[str, ...]
    backward_or_window_rule_ids: Tuple[str, ...]
    test_case_count: int


class DeadlineEnginePackageLoader:
    """Pins the rebuilt package and validates only source-supported V1.1 contracts.

    This loader deliberately does not convert a PRODUCTION_CANDIDATE_NOT_FROZEN
    package into an active rule catalog.
    """

    def load(self, package_path: str | Path, report_path: str | Path) -> LoadedDeadlineEnginePackage:
        if _sha(package_path) != PACKAGE_SHA256:
            raise DeadlineEnginePackageError("PACKAGE_SHA256_MISMATCH")
        if _sha(report_path) != REPORT_SHA256:
            raise DeadlineEnginePackageError("REPORT_SHA256_MISMATCH")

        d = json.loads(Path(package_path).read_text(encoding="utf-8"))
        meta = d.get("package_metadata", {})
        if meta.get("package_version") != PACKAGE_VERSION:
            raise DeadlineEnginePackageError("PACKAGE_VERSION_MISMATCH")
        if meta.get("jurisdiction") != "SYRIA":
            raise DeadlineEnginePackageError("JURISDICTION_MISMATCH")
        if meta.get("governing_release_status") != "PRODUCTION_CANDIDATE_NOT_FROZEN":
            raise DeadlineEnginePackageError("SOURCE_STATUS_CHANGED")
        if meta.get("deadline_calculation_execution_allowed") is not False:
            raise DeadlineEnginePackageError("SOURCE_CALCULATION_GATE_CHANGED")
        if meta.get("production_release_allowed") is not False:
            raise DeadlineEnginePackageError("SOURCE_PRODUCTION_GATE_CHANGED")
        if meta.get("final_legal_effect_automation_allowed") is not False:
            raise DeadlineEnginePackageError("SOURCE_LEGAL_EFFECT_GATE_CHANGED")

        artifacts = d.get("artifacts", {})
        required_artifacts = {
            "taxonomy", "rule_catalog", "calculation_policy", "relationship_catalog",
            "runtime_models", "test_suite", "validation_report",
        }
        if set(artifacts) != required_artifacts:
            raise DeadlineEnginePackageError("ARTIFACT_SET_MISMATCH")

        taxonomy = artifacts["taxonomy"]
        rule_catalog = artifacts["rule_catalog"]
        test_suite = artifacts["test_suite"]
        relations = artifacts["relationship_catalog"]
        validation = artifacts["validation_report"]

        families = taxonomy.get("deadline_families", [])
        deadline_types = [t for f in families for t in f.get("deadline_types", [])]
        rules = rule_catalog.get("deadline_rules", [])
        triggers = taxonomy.get("trigger_event_types", [])
        rels = relations.get("relationship_types", [])
        tests = test_suite.get("test_cases", [])

        actual = (len(families), len(deadline_types), len(rules), len(triggers), len(rels), len(tests))
        expected = (14, 136, 270, 38, 43, 5400)
        if actual != expected:
            raise DeadlineEnginePackageError(f"INVENTORY_MISMATCH:{actual}")

        rule_ids = [r.get("deadline_rule_id") for r in rules]
        type_ids = [t.get("deadline_type_id") for t in deadline_types]
        trigger_ids = [t.get("event_type_id") for t in triggers]
        relation_ids = [r.get("relation_id") for r in rels]
        if len(set(rule_ids)) != 270 or None in rule_ids:
            raise DeadlineEnginePackageError("RULE_ID_UNIQUENESS_FAILED")
        if len(set(type_ids)) != 136 or None in type_ids:
            raise DeadlineEnginePackageError("DEADLINE_TYPE_ID_UNIQUENESS_FAILED")
        if len(set(trigger_ids)) != 38 or None in trigger_ids:
            raise DeadlineEnginePackageError("TRIGGER_ID_UNIQUENESS_FAILED")
        if len(set(relation_ids)) != 43 or None in relation_ids:
            raise DeadlineEnginePackageError("RELATION_ID_UNIQUENESS_FAILED")

        if any(r.get("rule_status") != "BLOCKED" or r.get("production_eligible") is not False for r in rules):
            raise DeadlineEnginePackageError("CURRENT_CATALOG_MUST_REMAIN_FAIL_CLOSED")
        if any(r.get("requires_legal_review") is not True for r in rules):
            raise DeadlineEnginePackageError("LEGAL_REVIEW_GATE_CHANGED")

        static = test_suite.get("static_contract_validation_v1_1", {})
        checks = static.get("checks", {})
        if static.get("status") != "PASS" or len(checks) != 24 or not all(checks.values()):
            raise DeadlineEnginePackageError("V1_1_STATIC_CONTRACT_FAILED")
        if static.get("validated_test_blueprint_count") != 5400:
            raise DeadlineEnginePackageError("STATIC_TEST_COUNT_MISMATCH")
        if static.get("runtime_executed_test_count") != 0:
            raise DeadlineEnginePackageError("SOURCE_RUNTIME_STATE_UNEXPECTED")
        if any(t.get("execution_status") != "NOT_RUN" for t in tests):
            raise DeadlineEnginePackageError("TEST_RUNTIME_STATE_UNEXPECTED")
        if any(t.get("legal_reviewed") is not False for t in tests):
            raise DeadlineEnginePackageError("TEST_LEGAL_REVIEW_STATE_UNEXPECTED")
        if any(t.get("expected_status") == "NOT_APPLICABLE_TEST_CONDITION" for t in tests):
            raise DeadlineEnginePackageError("LEGACY_INVALID_RUNTIME_STATUS_PRESENT")

        v11 = validation.get("legal_rebuild_static_validation_v1_1", {})
        if v11.get("status") != "PASS" or v11.get("checks_total") != 24 or v11.get("checks_passed") != 24:
            raise DeadlineEnginePackageError("LEGAL_REBUILD_STATIC_VALIDATION_FAILED")
        metrics = v11.get("source_gate_metrics", {})
        required_metrics = {
            "rules_total": 270,
            "law_node_id_empty": 270,
            "article_node_id_empty": 270,
            "lifecycle_unresolved": 270,
            "effective_from_empty": 270,
            "resolution_not_exact": 270,
        }
        if any(metrics.get(k) != v for k, v in required_metrics.items()):
            raise DeadlineEnginePackageError("SOURCE_GATE_METRICS_CHANGED")

        rv = validation.get("runtime_validation_v1_1", {})
        if rv.get("status") != "NOT_RUN_REQUIRED_EXTERNAL_DEPENDENCIES_UNAVAILABLE":
            raise DeadlineEnginePackageError("REAL_RULE_RUNTIME_STATE_CHANGED")
        if rv.get("calculation_execution_allowed") is not False or rv.get("production_activation_allowed") is not False:
            raise DeadlineEnginePackageError("RUNTIME_GATE_CHANGED")

        unit = test_suite.get("deterministic_policy_unit_tests_v1_1", {})
        if unit.get("status") != "PASS" or unit.get("executed_count") != 21 or unit.get("passed_count") != 21:
            raise DeadlineEnginePackageError("SOURCE_POLICY_UNIT_TEST_DECLARATION_CHANGED")

        modifier_only = []
        backward = []
        for r in rules:
            sem = r.get("calculation", {}).get("temporal_semantics", {})
            if sem.get("creates_deadline_instance") is False:
                modifier_only.append(r["deadline_rule_id"])
            if sem.get("direction") == "BACKWARD" or sem.get("kind") == "BACKWARD_WINDOW":
                backward.append(r["deadline_rule_id"])
        if len(modifier_only) != 7 or len(backward) != 14:
            raise DeadlineEnginePackageError("TEMPORAL_SEMANTICS_COUNT_MISMATCH")

        return LoadedDeadlineEnginePackage(
            package=d,
            report_text=Path(report_path).read_text(encoding="utf-8"),
            rules_by_id={r["deadline_rule_id"]: r for r in rules},
            deadline_type_ids=tuple(sorted(type_ids)),
            trigger_event_type_ids=tuple(sorted(trigger_ids)),
            relationship_type_ids=tuple(sorted(relation_ids)),
            modifier_only_rule_ids=tuple(sorted(modifier_only)),
            backward_or_window_rule_ids=tuple(sorted(backward)),
            test_case_count=len(tests),
        )


@dataclass(frozen=True)
class DeadlineCandidateHandoff:
    """Non-canonical candidate only; never a DeadlineInstance."""

    candidate_fingerprint: str
    tenant_id: str
    case_scope_id: str
    source_entity_id: str
    source_document_id: Optional[str]
    deadline_rule_id: str
    deadline_type_id: str
    required_action_type_id: str
    trigger_event_type_id: str
    trigger_date_role: str
    trigger_raw_date: Optional[str]
    trigger_verification_status: str
    calculation_status: str = "BLOCKED_REQUIRES_REVIEW"
    legal_effect_status: str = "NOT_DETERMINED_BY_ENGINE"
    requires_legal_review: bool = True
    canonical_persistence_allowed: bool = False
    deadline_instance_creation_allowed: bool = False
    automatic_final_legal_effect_allowed: bool = False


@dataclass(frozen=True)
class DeadlineSandboxResult:
    candidates: Tuple[DeadlineCandidateHandoff, ...]
    blocking_errors: Tuple[str, ...]
    source_blocking_reason_codes: Tuple[str, ...]
    signals: Tuple[str, ...]
    deadline_instances: Tuple[dict, ...]
    calculation_runs: Tuple[dict, ...]
    stable_projection_sha256: str


class DeadlineEngineSandboxRuntime:
    """Fail-closed integration runtime for the current V1.1 catalog.

    It validates handoffs and preserves source blocking semantics. It does not
    execute any of the 270 legal rules while the source catalog is blocked.
    """

    def __init__(self, loaded: LoadedDeadlineEnginePackage):
        self.loaded = loaded
        self.error_codes = {
            e["code"] for e in loaded.package["artifacts"]["calculation_policy"].get("error_codes", [])
        }

    def evaluate_handoff(
        self,
        *,
        tenant_id: str,
        case_scope_id: str,
        source_entity_id: str,
        deadline_rule_id: str,
        trigger: Optional[Dict[str, Any]],
        source_document_id: Optional[str] = None,
        derived_secondary_source: bool = False,
        final_legal_effect_requested: bool = False,
        llm_in_calculation_path: bool = False,
    ) -> DeadlineSandboxResult:
        if derived_secondary_source or source_document_id == "D30":
            return self._result((), (), (), ("DERIVED_SOURCE_SUPPRESSED",))

        rule = self.loaded.rules_by_id.get(deadline_rule_id)
        if rule is None:
            raise DeadlineEnginePackageError("UNKNOWN_SOURCE_RULE_ID")

        sem = rule.get("calculation", {}).get("temporal_semantics", {})
        errors = []
        if rule.get("rule_status") != "ACTIVE":
            errors.append("DLC-E001")
        if rule.get("production_eligible") is not True:
            errors.append("DLC-E002")
        if rule.get("blocking_reason_codes"):
            errors.append("DLC-E003")
        source = rule.get("source", {})
        if source.get("lifecycle_status") != "RESOLVED" or source.get("resolution_status") != "EXACT":
            errors.append("DLC-E004")

        expected_trigger = rule.get("trigger", {})
        if not trigger:
            errors.append("DLC-E010")
            trigger = {}
        alt = trigger.get("alternative_trigger_candidates") or []
        if len(alt) > 1:
            errors.append("DLC-E011")
        verification = str(trigger.get("verification_status") or "UNVERIFIED")
        if verification not in {"VERIFIED", "USER_VERIFIED"}:
            errors.append("DLC-E012")
        raw_date = trigger.get("raw_date")
        if trigger.get("date_precision") in {"APPROXIMATE", "INCOMPLETE", "UNKNOWN"}:
            errors.append("DLC-E014")
        if expected_trigger.get("date_role") == "VALID_SERVICE_DATE" and trigger.get("notification_validity") != "VERIFIED_VALID":
            errors.append("DLC-E016")
        if final_legal_effect_requested:
            errors.append("DLC-E052")
        if llm_in_calculation_path:
            errors.append("DLC-E053")

        errors = tuple(dict.fromkeys(e for e in errors if e in self.error_codes))
        source_errors = tuple(rule.get("blocking_reason_codes") or ())
        signals = ["LEGAL_RULE_CALCULATION_BLOCKED", "HUMAN_LEGAL_REVIEW_REQUIRED"]
        if sem.get("creates_deadline_instance") is False:
            signals.append("MODIFIER_ONLY_NO_DEADLINE_INSTANCE")
        if sem.get("direction") == "BACKWARD" or sem.get("kind") == "BACKWARD_WINDOW":
            signals.append("BACKWARD_SEMANTICS_PRESERVED")
        if expected_trigger.get("alternative_event_types"):
            signals.append("ALTERNATIVE_TRIGGER_PRECEDENCE_REQUIRES_RESOLUTION")

        fp = _projection({
            "tenant_id": tenant_id,
            "case_scope_id": case_scope_id,
            "source_entity_id": source_entity_id,
            "deadline_rule_id": deadline_rule_id,
            "trigger": trigger,
        })
        candidate = DeadlineCandidateHandoff(
            candidate_fingerprint=fp,
            tenant_id=tenant_id,
            case_scope_id=case_scope_id,
            source_entity_id=source_entity_id,
            source_document_id=source_document_id,
            deadline_rule_id=deadline_rule_id,
            deadline_type_id=rule.get("deadline_type_id", ""),
            required_action_type_id=rule.get("required_action", {}).get("action_type_id", ""),
            trigger_event_type_id=str(trigger.get("event_type_id") or expected_trigger.get("event_type_id") or ""),
            trigger_date_role=str(trigger.get("date_role") or expected_trigger.get("date_role") or ""),
            trigger_raw_date=str(raw_date) if raw_date is not None else None,
            trigger_verification_status=verification,
        )
        return self._result((candidate,), errors, source_errors, tuple(signals))

    @staticmethod
    def _result(candidates, errors, source_errors, signals) -> DeadlineSandboxResult:
        payload = {
            "candidates": [asdict(x) for x in candidates],
            "blocking_errors": list(errors),
            "source_blocking_reason_codes": list(source_errors),
            "signals": list(signals),
            "deadline_instances": [],
            "calculation_runs": [],
        }
        return DeadlineSandboxResult(
            candidates=tuple(candidates),
            blocking_errors=tuple(errors),
            source_blocking_reason_codes=tuple(source_errors),
            signals=tuple(signals),
            deadline_instances=(),
            calculation_runs=(),
            stable_projection_sha256=_projection(payload),
        )


class DeadlineEngineBatchProcessor:
    def __init__(self, runtime: DeadlineEngineSandboxRuntime):
        self.runtime = runtime
        self._seen = set()

    def process(self, **kwargs) -> Optional[DeadlineSandboxResult]:
        key = (
            kwargs.get("tenant_id"),
            kwargs.get("case_scope_id"),
            kwargs.get("source_entity_id"),
            kwargs.get("deadline_rule_id"),
        )
        if key in self._seen:
            return None
        self._seen.add(key)
        return self.runtime.evaluate_handoff(**kwargs)


class DeterministicTemporalPolicyKernel:
    """Pure date primitives only. Never selects or activates a legal rule."""

    @staticmethod
    def forward_days(anchor: date, days: int, include_anchor: bool = False) -> date:
        if days < 0:
            raise ValueError("days must be non-negative")
        return anchor + timedelta(days=max(days - 1, 0) if include_anchor and days else days)

    @staticmethod
    def backward_days(anchor: date, days: int) -> date:
        if days < 0:
            raise ValueError("days must be non-negative")
        return anchor - timedelta(days=days)

    @staticmethod
    def add_months_clamped(anchor: date, months: int) -> date:
        total = anchor.year * 12 + (anchor.month - 1) + months
        year, month0 = divmod(total, 12)
        month = month0 + 1
        day = min(anchor.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def roll_forward(day: date, closed_dates: Iterable[date]) -> date:
        closed = set(closed_dates)
        while day in closed:
            day += timedelta(days=1)
        return day

    @staticmethod
    def formula_with_caps(value: int, multiplier: int, minimum: int, maximum: int) -> int:
        return min(max(value * multiplier, minimum), maximum)

    @staticmethod
    def interruption_restart(restart_date: date, full_period_days: int) -> date:
        return restart_date + timedelta(days=full_period_days)

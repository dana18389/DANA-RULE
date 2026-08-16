from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import hashlib
import json

PACKAGE_SHA256 = "12d4614384db59e185df0d5c84b6d3eff130bdf2463cc27750a49f8a443cb40f"
REPORT_SHA256 = "3a0cb16c2ca73362fefa59dc38e66802228d8b5db4600cffda1348fb85db480d"
PACKAGE_VERSION = "CASE_TASK_ALERT_BACKEND_PACKAGE_V1.2.0-LEGAL-REBUILD-CANDIDATE"
ENGINE_VERSION = "CASE_TASK_ALERT_RULE_ENGINE_V1.2.0-LEGAL-REBUILD-CANDIDATE"
DEADLINE_PACKAGE_VERSION = "1.1.0-legal-rebuild-candidate.2026-08-16"
ACTUAL_LEGAL_ISSUE_VERSION = "1.1.0-legal-rebuild-candidate.2026-08-16"
ACTUAL_LEGAL_ISSUE_SHA256 = "4bcb71d529a0bca3d02913ee4c019bf289ef69d010fc7fc9dc43cf6834c5d0a1"
CANONICAL_CALCULATION_STATUSES = {
    "CALCULATED_PROVISIONAL", "BLOCKED_REQUIRES_REVIEW", "NOT_APPLICABLE", "FAILED_TECHNICAL"
}


class TaskAlertPackageError(RuntimeError):
    pass


def _sha(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _projection(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class LoadedTaskAlertPackage:
    package: Dict[str, Any]
    report_text: str
    rules_by_id: Dict[str, Dict[str, Any]]
    task_type_ids: Tuple[str, ...]
    alert_type_ids: Tuple[str, ...]
    relation_type_ids: Tuple[str, ...]
    scenario_tests: Tuple[Dict[str, Any], ...]
    legacy_optional_deadline_status_refs: Tuple[Tuple[str, str], ...]
    legal_issue_binding_status: str


class TaskAlertPackageLoader:
    def load(self, package_path: str | Path, report_path: str | Path) -> LoadedTaskAlertPackage:
        if _sha(package_path) != PACKAGE_SHA256:
            raise TaskAlertPackageError("PACKAGE_SHA256_MISMATCH")
        if _sha(report_path) != REPORT_SHA256:
            raise TaskAlertPackageError("REPORT_SHA256_MISMATCH")
        d = json.loads(Path(package_path).read_text(encoding="utf-8"))
        if d.get("backend_package_version") != PACKAGE_VERSION or d.get("engine_version") != ENGINE_VERSION:
            raise TaskAlertPackageError("PACKAGE_VERSION_MISMATCH")
        if d.get("jurisdiction_scope") != "SYRIA":
            raise TaskAlertPackageError("JURISDICTION_MISMATCH")
        v = d.get("validation", {})
        if v.get("status") != "PASS_STATIC_LEGAL_CONTRACT_VALIDATION":
            raise TaskAlertPackageError("SOURCE_STATIC_STATUS_CHANGED")
        if v.get("production_eligible") is not False or v.get("production_activation") != "BLOCKED" or v.get("freeze_status") != "NOT_FROZEN":
            raise TaskAlertPackageError("SOURCE_PRODUCTION_GATE_CHANGED")
        if v.get("runtime_status") != "NOT_RUN_RUNTIME_UNAVAILABLE":
            raise TaskAlertPackageError("SOURCE_RUNTIME_STATE_CHANGED")

        c = d.get("components", {})
        required = {
            "01_task_alert_taxonomy.json", "02_task_alert_dictionary.json", "03_task_alert_generation_rules.json",
            "04_task_alert_relations.json", "05_task_alert_schemas.json", "06_priority_severity_policies.json",
            "07_reminder_policies.json", "08_escalation_policies.json", "09_delivery_policies.json",
            "10_actor_role_permission_matrix.json", "11_cross_dictionary_trigger_map.json",
            "12_deadline_engine_integration_contract.json", "13_legal_reference_integration_contract.json",
            "14_task_alert_api_contract.json", "15_task_alert_event_contract.json", "16_task_alert_migration_map.json",
            "17_task_alert_validation_report.json", "18_task_alert_test_cases.json", "19_task_alert_readme.md",
            "20_task_alert_correction_run.json", "manifest.json"
        }
        if set(c) != required:
            raise TaskAlertPackageError("COMPONENT_SET_MISMATCH")

        tax = c["01_task_alert_taxonomy.json"]
        dic = c["02_task_alert_dictionary.json"]
        rc = c["03_task_alert_generation_rules.json"]
        rel = c["04_task_alert_relations.json"]
        tc = c["18_task_alert_test_cases.json"]
        vr = c["17_task_alert_validation_report.json"]
        task_ids = [x["task_type_id"] for x in tax["task_types"]]
        alert_ids = [x["alert_type_id"] for x in tax["alert_types"]]
        rule_ids = [x["rule_id"] for x in rc["rules"]]
        rel_ids = [x["relation_type_id"] for x in rel["relation_types"]]
        tests = tc["mandatory_test_cases"]
        actual = (len(tax["task_families"]), len(task_ids), len(tax["alert_families"]), len(alert_ids), len(rule_ids), len(rel_ids), len(tests))
        if actual != (7, 86, 8, 76, 167, 54, 52):
            raise TaskAlertPackageError(f"INVENTORY_MISMATCH:{actual}")
        if len(set(task_ids)) != 86 or len(set(alert_ids)) != 76 or len(set(rule_ids)) != 167 or len(set(rel_ids)) != 54:
            raise TaskAlertPackageError("CANONICAL_ID_UNIQUENESS_FAILED")
        dictionary_ids = [x["output_type_id"] for x in dic["entries"]]
        if len(dictionary_ids) != 162 or set(dictionary_ids) != set(task_ids + alert_ids):
            raise TaskAlertPackageError("TAXONOMY_DICTIONARY_PARITY_FAILED")

        known_tasks, known_alerts, known_rules = set(task_ids), set(alert_ids), set(rule_ids)
        for r in rc["rules"]:
            if r.get("automatic_execution_allowed") is not False:
                raise TaskAlertPackageError(f"AUTOMATIC_EXECUTION_PROHIBITED:{r['rule_id']}")
            for out in r.get("outputs", {}).get("task_candidate_templates", []):
                if out.get("output_type_id") not in known_tasks:
                    raise TaskAlertPackageError(f"UNKNOWN_TASK_OUTPUT:{r['rule_id']}")
            for out in r.get("outputs", {}).get("alert_templates", []):
                if out.get("output_type_id") not in known_alerts:
                    raise TaskAlertPackageError(f"UNKNOWN_ALERT_OUTPUT:{r['rule_id']}")
        for t in tests:
            if any(x not in known_rules for x in t.get("applicable_rule_ids", [])):
                raise TaskAlertPackageError(f"UNKNOWN_TEST_RULE:{t.get('test_id')}")
            for x in t.get("expected_tasks", []):
                if x.get("task_type_id") not in known_tasks:
                    raise TaskAlertPackageError(f"UNKNOWN_TEST_TASK:{t.get('test_id')}")
            for x in t.get("expected_alerts", []) + t.get("expected_suppressed_outputs", []):
                oid = x.get("alert_type_id") or x.get("task_type_id") or x.get("existing_alert_type_id")
                if oid is not None and oid not in known_alerts | known_tasks:
                    raise TaskAlertPackageError(f"UNKNOWN_TEST_OUTPUT:{t.get('test_id')}")

        sv = d["legal_rebuild_v1_2"]["static_validation_evidence"]
        cc = sv["cross_cutting_invariant_checks"]
        if (cc.get("executed"), cc.get("passed"), cc.get("failed")) != (23, 23, 0) or not all(cc.get("results", {}).values()):
            raise TaskAlertPackageError("SOURCE_CROSS_CUTTING_VALIDATION_FAILED")
        sc = sv["scenario_contract_checks"]
        cs = sv["critical_semantic_simulations"]
        if (sc.get("executed"), sc.get("passed"), sc.get("failed")) != (52, 52, 0):
            raise TaskAlertPackageError("SOURCE_SCENARIO_CONTRACT_FAILED")
        if (cs.get("executed"), cs.get("passed"), cs.get("failed")) != (9, 9, 0):
            raise TaskAlertPackageError("SOURCE_CRITICAL_SIMULATION_FAILED")
        if vr.get("validation_status") != "PASS_STATIC_WITH_EXTERNAL_RUNTIME_GATES" or vr.get("production_eligible") is not False:
            raise TaskAlertPackageError("VALIDATION_REPORT_GATE_CHANGED")
        if len(vr.get("blocking_errors", [])) != 4 or len(vr.get("warnings", [])) != 2:
            raise TaskAlertPackageError("BLOCKER_INVENTORY_CHANGED")

        required_deadline_invalid = []
        legacy_optional = []
        for r in rc["rules"]:
            gate = r.get("deadline_gate") or {}
            for status in gate.get("allowed_calculation_statuses", []) or []:
                if status not in CANONICAL_CALCULATION_STATUSES:
                    if gate.get("required"):
                        required_deadline_invalid.append((r["rule_id"], status))
                    else:
                        legacy_optional.append((r["rule_id"], status))
        if required_deadline_invalid:
            raise TaskAlertPackageError(f"NON_CANONICAL_REQUIRED_DEADLINE_STATUS:{required_deadline_invalid}")

        dep = d.get("upstream_dependency_bindings_v1_2", {})
        dl = dep.get("deadline_engine", {})
        if dl.get("version") != DEADLINE_PACKAGE_VERSION:
            raise TaskAlertPackageError("DEADLINE_VERSION_BINDING_MISMATCH")
        li = dep.get("legal_issue_index", {})
        li_status = "BOUND" if li.get("version") == ACTUAL_LEGAL_ISSUE_VERSION else "UNRESOLVED_VERSION_BINDING"

        return LoadedTaskAlertPackage(
            package=d,
            report_text=Path(report_path).read_text(encoding="utf-8"),
            rules_by_id={r["rule_id"]: r for r in rc["rules"]},
            task_type_ids=tuple(sorted(task_ids)),
            alert_type_ids=tuple(sorted(alert_ids)),
            relation_type_ids=tuple(sorted(rel_ids)),
            scenario_tests=tuple(tests),
            legacy_optional_deadline_status_refs=tuple(sorted(legacy_optional)),
            legal_issue_binding_status=li_status,
        )


_MISSING = object()


def _get(ctx: Dict[str, Any], path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def _verified(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").upper() in {
        "VERIFIED", "USER_VERIFIED", "VERIFIED_VALID", "VERIFIED_DELIVERED", "REVIEWED", "CONFIRMED"
    }


def _condition(tree: Optional[Dict[str, Any]], ctx: Dict[str, Any]) -> bool:
    if not tree:
        return True
    op = tree.get("op")
    if op == "ALL":
        return all(_condition(x, ctx) for x in tree.get("conditions", []))
    if op == "ANY":
        return any(_condition(x, ctx) for x in tree.get("conditions", []))
    field = tree.get("field")
    value = _get(ctx, field) if field else _MISSING
    cmp = _get(ctx, tree["compare_to_field"]) if tree.get("compare_to_field") else tree.get("value", _MISSING)
    if op == "EXISTS": return value is not _MISSING and value is not None
    if op == "NOT_EXISTS": return value is _MISSING or value is None
    if op == "NOT_EMPTY": return value is not _MISSING and value not in (None, "", [], {}, ())
    if op == "EQUALS": return value is not _MISSING and cmp is not _MISSING and value == cmp
    if op == "NOT_EQUALS": return value is not _MISSING and cmp is not _MISSING and value != cmp
    if op == "IN": return value is not _MISSING and value in (tree.get("value") or [])
    if op == "NOT_IN": return value is not _MISSING and value not in (tree.get("value") or [])
    if op == "LESS_THAN": return value is not _MISSING and cmp is not _MISSING and value < cmp
    if op == "GREATER_THAN_OR_EQUAL": return value is not _MISSING and cmp is not _MISSING and value >= cmp
    if op == "COUNT_AT_LEAST": return value is not _MISSING and hasattr(value, "__len__") and len(value) >= int(tree.get("count", 0))
    if op == "SOURCE_VERIFIED": return value is not _MISSING and _verified(value)
    if op == "STATUS_IS": return value is not _MISSING and value == tree.get("value")
    if op == "PERMISSION_EXISTS": return value is not _MISSING and tree.get("value") in (value or [])
    if op in {"RELATION_EXISTS", "RELATION_NOT_EXISTS"}:
        relations = ctx.get("relations") or []
        from_id = _get(ctx, tree.get("from_field", ""))
        exists = any(r.get("relation_type") == tree.get("relation_type") and (from_id is _MISSING or r.get("from_id") == from_id) for r in relations)
        return exists if op == "RELATION_EXISTS" else not exists
    if op == "DATE_WITHIN_WINDOW":
        return bool((ctx.get("policy") or {}).get("window_results", {}).get(tree.get("window_ref"), False))
    if op == "STATUS_TRANSITIONED_FROM_TO":
        tr = ctx.get("transition") or {}
        spec = tree.get("value") or {}
        return tr.get("from") in (spec.get("from") or []) and tr.get("to") == spec.get("to")
    return False


@dataclass(frozen=True)
class TaskCandidate:
    candidate_id: str
    record_match_key: str
    evaluation_idempotency_key: str
    tenant_id: str
    case_id: str
    rule_id: str
    task_type_id: str
    source_entity_id: str
    source_entity_version: str
    actor_mode: str
    due_at: Optional[str]
    deadline_id: Optional[str]
    deadline_version: Optional[str]
    status: str = "DRAFT_CANDIDATE_PENDING_REVIEW"
    activation_allowed: bool = False
    automatic_execution_allowed: bool = False
    legal_compliance_verified: bool = False


@dataclass(frozen=True)
class AlertCandidate:
    candidate_id: str
    record_match_key: str
    evaluation_idempotency_key: str
    tenant_id: str
    case_id: str
    rule_id: str
    alert_type_id: str
    source_entity_id: str
    source_entity_version: str
    status: str = "REVIEW_CANDIDATE"
    delivery_allowed: bool = False
    final_legal_effect_determined: bool = False


@dataclass(frozen=True)
class IntegrationEventCandidate:
    event_candidate_id: str
    tenant_id: str
    case_id: str
    rule_id: str
    event_type: str
    target_engine: str
    dispatch_allowed: bool = False


@dataclass(frozen=True)
class RuleEvaluationResult:
    rule_id: str
    matched: bool
    suppressed: bool
    suppression_reasons: Tuple[str, ...]
    task_candidates: Tuple[TaskCandidate, ...]
    alert_candidates: Tuple[AlertCandidate, ...]
    integration_event_candidates: Tuple[IntegrationEventCandidate, ...]
    duplicate_evaluations_suppressed: int
    signals: Tuple[str, ...]
    stable_projection_sha256: str


class TaskAlertSandboxRuntime:
    def __init__(self, loaded: LoadedTaskAlertPackage):
        self.loaded = loaded
        self._seen_eval = set()

    def _keys(self, ctx: Dict[str, Any], rule: Dict[str, Any], output_type_id: str) -> Tuple[str, str]:
        source = ctx.get("source") or {}
        deadline = ctx.get("deadline") or {}
        base = [ctx.get("tenant_id"), ctx.get("case_id"), rule["rule_id"], source.get("entity_type"), source.get("entity_id"),
                (ctx.get("actor") or {}).get("mode"), (ctx.get("actor") or {}).get("represented_party_scope_hash"), output_type_id]
        rec = _projection(base)
        ev = _projection(base + [source.get("version"), deadline.get("version") or deadline.get("rule_catalog_version"), (ctx.get("event") or {}).get("event_version")])
        return rec, ev

    def evaluate_rule(self, rule_id: str, ctx: Dict[str, Any]) -> RuleEvaluationResult:
        rule = self.loaded.rules_by_id.get(rule_id)
        if rule is None:
            raise TaskAlertPackageError("UNKNOWN_RULE_ID")
        signals = []
        reasons = []
        source = ctx.get("source") or {}
        if source.get("derived_secondary_source") or source.get("document_id") == "D30":
            reasons.append("DERIVED_SOURCE_SUPPRESSED")
        scope = ctx.get("scope") or {}
        if scope.get("tenant_match") is not True or scope.get("case_match") is not True:
            reasons.append("TENANT_CASE_SCOPE_MISMATCH")
        actor_mode = (ctx.get("actor") or {}).get("mode")
        if actor_mode not in rule.get("allowed_actor_modes", []):
            reasons.append("ACTOR_MODE_NOT_ALLOWED")
        if rule.get("source_family") == "LEGAL_ISSUE_DERIVED" and self.loaded.legal_issue_binding_status != "BOUND":
            reasons.append("LEGAL_ISSUE_VERSION_BINDING_UNRESOLVED")
        if not rule.get("enabled", False):
            reasons.append("RULE_DISABLED")
        event = ctx.get("event") or {}
        if event.get("event_type") and event.get("event_type") != rule.get("trigger_type"):
            reasons.append("TRIGGER_TYPE_MISMATCH")
        if source.get("entity_type") and source.get("entity_type") not in rule.get("trigger_entity_types", []):
            reasons.append("TRIGGER_ENTITY_TYPE_MISMATCH")
        if any(_condition(x, ctx) for x in rule.get("suppression_conditions", [])):
            reasons.append("RULE_SUPPRESSION_CONDITION")
        if reasons:
            return self._result(rule_id, False, True, reasons, (), (), (), 0, signals)
        if not _condition(rule.get("condition_tree"), ctx):
            return self._result(rule_id, False, False, ("CONDITION_NOT_MATCHED",), (), (), (), 0, signals)
        for gate in rule.get("evidence_gates", []):
            if gate.get("required") and not _condition(gate.get("condition_tree"), ctx):
                return self._result(rule_id, False, True, (f"EVIDENCE_GATE_FAILED:{gate.get('gate_id')}",), (), (), (), 0, signals)

        lrg = rule.get("legal_reference_gate") or {}
        requirement = lrg.get("requirement", "NONE")
        if requirement in {"RESOLVED_REQUIRED", "VERIFIED_REQUIRED"}:
            lr = ctx.get("legal_reference") or {}
            state = lr.get("resolution_status")
            roles = set(lr.get("role_ids") or [])
            needed = set(lrg.get("required_role_ids") or [])
            ok_state = state == "VERIFIED" if requirement == "VERIFIED_REQUIRED" else state in {"RESOLVED", "VERIFIED"}
            if not ok_state or not needed.issubset(roles):
                return self._result(rule_id, False, True, ("LEGAL_REFERENCE_GATE_UNRESOLVED",), (), (), (), 0, signals)
        elif requirement == "CANDIDATE_ALLOWED":
            signals.append("LEGAL_REFERENCE_CANDIDATE_ALLOWED_NO_VERIFIED_RESOLUTION_INFERRED")

        dlg = rule.get("deadline_gate") or {}
        if dlg.get("required"):
            deadline = ctx.get("deadline") or {}
            calc = (deadline.get("calculation") or {}).get("calculation_status")
            if calc not in set(dlg.get("allowed_calculation_statuses") or []):
                return self._result(rule_id, False, True, ("DEADLINE_GATE_BLOCKED",), (), (), (), 0, signals)
            if dlg.get("prohibit_if_date_uncertain") and deadline.get("date_uncertain") is True:
                return self._result(rule_id, False, True, ("DEADLINE_DATE_UNCERTAIN",), (), (), (), 0, signals)

        tasks, alerts, events = [], [], []
        duplicate_count = 0
        source_id = str(source.get("entity_id") or "")
        source_version = str(source.get("version") or "")
        tenant_id, case_id = str(ctx.get("tenant_id") or ""), str(ctx.get("case_id") or "")
        deadline = ctx.get("deadline") or {}
        for out in rule.get("outputs", {}).get("task_candidate_templates", []):
            typ = out["output_type_id"]
            rec, ev = self._keys(ctx, rule, typ)
            if ev in self._seen_eval:
                duplicate_count += 1
                continue
            self._seen_eval.add(ev)
            due_at = None
            deadline_id = None
            deadline_version = None
            if out.get("due_date_source") == "DEADLINE_ENGINE":
                calc = deadline.get("calculation") or {}
                if calc.get("calculation_status") == "CALCULATED_PROVISIONAL":
                    due_at = calc.get("final_end_date")
                    deadline_id = deadline.get("deadline_instance_id")
                    deadline_version = str(deadline.get("version") or deadline.get("rule_catalog_version") or "") or None
                signals.append("DUE_DATE_COPIED_FROM_DEADLINE_ENGINE_NO_LOCAL_RECALCULATION")
            tasks.append(TaskCandidate("tacand_" + ev[:24], rec, ev, tenant_id, case_id, rule_id, typ, source_id, source_version,
                                       str(actor_mode or ""), due_at, deadline_id, deadline_version))
        for out in rule.get("outputs", {}).get("alert_templates", []):
            typ = out["output_type_id"]
            rec, ev = self._keys(ctx, rule, typ)
            if ev in self._seen_eval:
                duplicate_count += 1
                continue
            self._seen_eval.add(ev)
            alerts.append(AlertCandidate("aacand_" + ev[:24], rec, ev, tenant_id, case_id, rule_id, typ, source_id, source_version))
        for out in rule.get("outputs", {}).get("integration_events", []):
            typ = out["event_type"]
            _, ev = self._keys(ctx, rule, "EVENT:" + typ)
            if ev in self._seen_eval:
                duplicate_count += 1
                continue
            self._seen_eval.add(ev)
            events.append(IntegrationEventCandidate("ievcand_" + ev[:24], tenant_id, case_id, rule_id, typ, out.get("target_engine", "")))
        if duplicate_count:
            signals.append("IDEMPOTENT_REPLAY_SUPPRESSED")
        signals += ["CANDIDATE_ONLY", "AUTOMATIC_EXECUTION_PROHIBITED", "PRODUCTION_DELIVERY_DISABLED"]
        return self._result(rule_id, True, False, (), tasks, alerts, events, duplicate_count, signals)

    @staticmethod
    def _result(rule_id, matched, suppressed, reasons, tasks, alerts, events, duplicate_count, signals):
        payload = {
            "rule_id": rule_id, "matched": matched, "suppressed": suppressed, "reasons": list(reasons),
            "tasks": [asdict(x) for x in tasks], "alerts": [asdict(x) for x in alerts], "events": [asdict(x) for x in events],
            "duplicate_evaluations_suppressed": duplicate_count, "signals": list(dict.fromkeys(signals)),
        }
        return RuleEvaluationResult(rule_id, matched, suppressed, tuple(reasons), tuple(tasks), tuple(alerts), tuple(events), duplicate_count,
                                    tuple(dict.fromkeys(signals)), _projection(payload))

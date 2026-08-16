import copy, sys, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from qanun_case_runtime.task_alert_runtime import TaskAlertPackageLoader, TaskAlertSandboxRuntime
PKG="/mnt/data/QANUN_CASE_TASK_ALERT_RULE_ENGINE_LEGAL_REBUILD_V1_2_PRODUCTION_CANDIDATE(1).json"
REPORT="/mnt/data/QANUN_CASE_TASK_ALERT_RULE_ENGINE_LEGAL_REBUILD_REPORT_V1_2(1).md"

def env():
    loaded=TaskAlertPackageLoader().load(PKG,REPORT)
    return loaded,TaskAlertSandboxRuntime(loaded)

def base(source_type,event_type):
    return {"tenant_id":"TENANT-A","case_id":"CASE-A","scope":{"tenant_match":True,"case_match":True},"actor":{"mode":"PARTY_COUNSEL","represented_party_scope_hash":"P1","permissions":[]},"event":{"event_type":event_type,"event_version":"1"},"source":{"entity_type":source_type,"entity_id":"SRC-1","version":"1","status":"ACTIVE","verification_status":"VERIFIED","trace":{"present":True},"attributes":{}},"legal_reference":{"resolution_status":"UNRESOLVED","role_ids":[]},"policy":{"window_results":{}},"relations":[]}

def test_package_inventory_and_source_gates():
    loaded,_=env()
    assert len(loaded.task_type_ids)==86 and len(loaded.alert_type_ids)==76 and len(loaded.rules_by_id)==167
    assert len(loaded.relation_type_ids)==54 and len(loaded.scenario_tests)==52
    assert loaded.package["validation"]["production_eligible"] is False
    assert loaded.package["validation"]["runtime_status"]=="NOT_RUN_RUNTIME_UNAVAILABLE"

def test_independent_52_contract_reference_validation():
    loaded,_=env(); task_ids,alert_ids,rule_ids=set(loaded.task_type_ids),set(loaded.alert_type_ids),set(loaded.rules_by_id)
    for t in loaded.scenario_tests:
        assert set(t.get("applicable_rule_ids",[])).issubset(rule_ids)
        assert all(x.get("task_type_id") in task_ids for x in t.get("expected_tasks",[]))
        assert all((x.get("alert_type_id") in alert_ids) if x.get("alert_type_id") is not None else True for x in t.get("expected_alerts",[]))
        for x in t.get("expected_suppressed_outputs",[]):
            oid=x.get("task_type_id") or x.get("alert_type_id") or x.get("existing_alert_type_id")
            if oid is not None: assert oid in task_ids|alert_ids

def test_all_rules_non_executing_and_all_task_types_non_auto_active():
    loaded,_=env(); rules=loaded.package["components"]["03_task_alert_generation_rules.json"]["rules"]; tasks=loaded.package["components"]["01_task_alert_taxonomy.json"]["task_types"]
    assert all(r["automatic_execution_allowed"] is False for r in rules)
    assert all(t["automatic_activation_allowed"] is False for t in tasks)

def test_required_deadline_gates_are_canonical_but_legacy_optional_metadata_is_flagged():
    loaded,_=env()
    assert len(loaded.legacy_optional_deadline_status_refs)==15
    assert len({r for r,_ in loaded.legacy_optional_deadline_status_refs})==5
    assert ("TAR-EXAMPLE-001","VERIFIED") in loaded.legacy_optional_deadline_status_refs

def test_legal_issue_binding_mismatch_is_fail_closed():
    loaded,rt=env(); assert loaded.legal_issue_binding_status=="UNRESOLVED_VERSION_BINDING"
    res=rt.evaluate_rule("TAR-ISSUE-001",base("LEGAL_ISSUE_CANDIDATE","ON_ENTITY_CREATED"))
    assert res.suppressed and "LEGAL_ISSUE_VERSION_BINDING_UNRESOLVED" in res.suppression_reasons

def test_active_deadline_consumed_as_integration_event_only():
    _,rt=env(); ctx=base("LEGAL_DEADLINE","ON_DEADLINE_CALCULATED")
    ctx["deadline"]={"deadline_instance_id":"DL-1","version":"1","deadline_status":"DLDS-ACTIVE","legal_effect_status":"NOT_DETERMINED_BY_ENGINE","calculation":{"calculation_status":"CALCULATED_PROVISIONAL","final_end_date":"2026-08-20T23:59:59+03:00","timezone":"Asia/Damascus"}}
    res=rt.evaluate_rule("TAR-DL-001",ctx)
    assert res.matched and not res.suppressed and not res.task_candidates and not res.alert_candidates
    assert [x.event_type for x in res.integration_event_candidates]==["LINK_OR_UPDATE_DEADLINE_ON_DEPENDENT_RECORDS"]
    assert res.integration_event_candidates[0].dispatch_allowed is False

def test_calculated_end_passed_creates_potential_review_not_verified_overdue():
    _,rt=env(); ctx=base("LEGAL_DEADLINE","SCHEDULED_REEVALUATION")
    ctx["deadline"]={"deadline_instance_id":"DL-END","version":"1","deadline_status":"DLDS-CALCULATED-END-PASSED","legal_effect_status":"NOT_DETERMINED_BY_ENGINE","calculation":{"calculation_status":"CALCULATED_PROVISIONAL","final_end_date":"2026-08-10T23:59:59+03:00","timezone":"Asia/Damascus"}}
    res=rt.evaluate_rule("TAR-DL-010",ctx)
    assert [x.task_type_id for x in res.task_candidates]==["VERIFY_DEADLINE_INPUTS"]
    assert [x.alert_type_id for x in res.alert_candidates]==["DEADLINE_POTENTIALLY_OVERDUE"]
    assert "DEADLINE_VERIFIED_OVERDUE" not in [x.alert_type_id for x in res.alert_candidates]

def test_verified_overdue_requires_independent_compliance_verification():
    _,rt=env(); ctx=base("LEGAL_COMPLIANCE_VERIFICATION","ON_ENTITY_UPDATED")
    ctx["deadline"]={"deadline_instance_id":"DL-MISS","version":"1","deadline_status":"DLDS-POSSIBLY-MISSED","legal_effect_status":"NOT_DETERMINED_BY_ENGINE","calculation":{"calculation_status":"CALCULATED_PROVISIONAL","final_end_date":"2026-08-10T23:59:59+03:00","timezone":"Asia/Damascus"}}
    no_ver=rt.evaluate_rule("TAR-DL-009",ctx); assert not no_ver.alert_candidates
    ctx["compliance_verification"]={"status":"VERIFIED","verification_type":"DEADLINE_MISSED_STATUS","missed_deadline_finding":"MISSED","verified_by":{"authorization_verified":True},"source_trace":{"present":True}}
    yes=rt.evaluate_rule("TAR-DL-009",ctx)
    assert [x.alert_type_id for x in yes.alert_candidates]==["DEADLINE_VERIFIED_OVERDUE"]
    assert yes.alert_candidates[0].final_legal_effect_determined is False

def test_optional_legacy_gate_never_drives_due_date_and_due_is_copied_only_from_deadline_engine():
    _,rt=env(); ctx=base("COURT_POSITION","ON_ENTITY_CREATED")
    ctx["source"]["attributes"].update({"order_action":"PAY_EXPERT_ADVANCE","deadline_start_dependency":"NOTIFICATION","addressee_resolution_status":"RESOLVED"})
    ctx["deadline"]={"deadline_instance_id":"DL-X","version":"2","deadline_status":"DLDS-ACTIVE","calculation":{"calculation_status":"CALCULATED_PROVISIONAL","final_end_date":"2026-08-22T23:59:59+03:00","timezone":"Asia/Damascus"}}
    res=rt.evaluate_rule("TAR-EXAMPLE-001",ctx)
    assert res.task_candidates and res.task_candidates[0].due_at=="2026-08-22T23:59:59+03:00" and res.task_candidates[0].deadline_id=="DL-X"
    assert "DUE_DATE_COPIED_FROM_DEADLINE_ENGINE_NO_LOCAL_RECALCULATION" in res.signals

def test_cross_tenant_and_d30_are_suppressed():
    _,rt=env(); ctx=base("LEGAL_DEADLINE","SCHEDULED_REEVALUATION"); ctx["scope"]["tenant_match"]=False
    res=rt.evaluate_rule("TAR-DL-010",ctx); assert res.suppressed and "TENANT_CASE_SCOPE_MISMATCH" in res.suppression_reasons
    ctx2=base("LEGAL_DEADLINE","SCHEDULED_REEVALUATION"); ctx2["source"]["document_id"]="D30"
    res2=rt.evaluate_rule("TAR-DL-010",ctx2); assert res2.suppressed and "DERIVED_SOURCE_SUPPRESSED" in res2.suppression_reasons

def test_replay_idempotency_and_record_identity_across_deadline_version():
    _,rt=env(); ctx=base("LEGAL_DEADLINE","SCHEDULED_REEVALUATION")
    ctx["deadline"]={"deadline_instance_id":"DL-R","version":"1","deadline_status":"DLDS-CALCULATED-END-PASSED","calculation":{"calculation_status":"CALCULATED_PROVISIONAL","final_end_date":"2026-08-10T23:59:59+03:00","timezone":"Asia/Damascus"}}
    first=rt.evaluate_rule("TAR-DL-010",ctx); replay=rt.evaluate_rule("TAR-DL-010",ctx)
    assert first.task_candidates and first.alert_candidates
    assert not replay.task_candidates and not replay.alert_candidates and replay.duplicate_evaluations_suppressed==2
    ctx2=copy.deepcopy(ctx); ctx2["deadline"]["version"]="2"; ctx2["event"]["event_version"]="2"
    changed=rt.evaluate_rule("TAR-DL-010",ctx2)
    assert changed.task_candidates and changed.alert_candidates
    assert changed.task_candidates[0].record_match_key==first.task_candidates[0].record_match_key
    assert changed.task_candidates[0].evaluation_idempotency_key!=first.task_candidates[0].evaluation_idempotency_key

def test_completion_does_not_imply_legal_compliance_static_invariant():
    loaded,_=env(); inv=loaded.package["components"]["05_task_alert_schemas.json"]["runtime_invariants"]
    assert "TASK COMPLETED does not imply LEGAL_COMPLIANCE VERIFIED." in inv
    assert "DEADLINE_CALCULATED_END_PASSED_DOES_NOT_IMPLY_HUMAN_VERIFIED_OVERDUE" in inv

def test_four_source_blockers_preserved():
    loaded,_=env(); errs=loaded.package["components"]["17_task_alert_validation_report.json"]["blocking_errors"]
    assert [x["error_id"] for x in errs]==["TA-B01","TA-B02","TA-B03","TA-B04"]

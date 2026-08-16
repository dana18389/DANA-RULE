import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from qanun_case_runtime.deadline_engine import (
    DeadlineEngineBatchProcessor,
    DeadlineEnginePackageLoader,
    DeadlineEngineSandboxRuntime,
    DeterministicTemporalPolicyKernel,
)

PKG = Path("/mnt/data/deadline_engine_extract/QANUN_AI_SYRIA_DEADLINE_ENGINE_LEGAL_REBUILD_V1_1_PRODUCTION_CANDIDATE.json")
REPORT = Path("/mnt/data/QANUN_AI_SYRIA_DEADLINE_ENGINE_LEGAL_REBUILD_REPORT_V1_1(2).md")


def env():
    loaded = DeadlineEnginePackageLoader().load(PKG, REPORT)
    return loaded, DeadlineEngineSandboxRuntime(loaded)


def verified_trigger(rule):
    t = rule["trigger"]
    return {
        "event_type_id": t["event_type_id"],
        "date_role": t["date_role"],
        "raw_date": "2026-01-01",
        "date_precision": "EXACT",
        "verification_status": "VERIFIED",
        "notification_validity": "VERIFIED_VALID",
        "alternative_trigger_candidates": [],
    }


def test_source_package_contract_and_inventory():
    d, _ = env()
    assert len(d.rules_by_id) == 270
    assert len(d.deadline_type_ids) == 136
    assert len(d.trigger_event_type_ids) == 38
    assert len(d.relationship_type_ids) == 43
    assert d.test_case_count == 5400
    assert len(d.modifier_only_rule_ids) == 7
    assert len(d.backward_or_window_rule_ids) == 14


def test_all_270_current_rules_fail_closed_without_deadline_instance():
    d, rt = env()
    for rid, rule in d.rules_by_id.items():
        r = rt.evaluate_handoff(
            tenant_id="TENANT-T",
            case_scope_id="CASE-T",
            source_entity_id=f"SRC-{rid}",
            deadline_rule_id=rid,
            trigger=verified_trigger(rule),
        )
        assert len(r.candidates) == 1
        assert r.candidates[0].calculation_status == "BLOCKED_REQUIRES_REVIEW"
        assert r.candidates[0].legal_effect_status == "NOT_DETERMINED_BY_ENGINE"
        assert r.candidates[0].canonical_persistence_allowed is False
        assert r.candidates[0].deadline_instance_creation_allowed is False
        assert r.deadline_instances == ()
        assert r.calculation_runs == ()
        assert {"DLC-E001", "DLC-E002", "DLC-E003", "DLC-E004"}.issubset(r.blocking_errors)


def test_modifier_only_rule_never_creates_deadline_instance():
    d, rt = env()
    rid = d.modifier_only_rule_ids[0]
    rule = d.rules_by_id[rid]
    r = rt.evaluate_handoff(
        tenant_id="T", case_scope_id="C", source_entity_id="S", deadline_rule_id=rid,
        trigger=verified_trigger(rule),
    )
    assert "MODIFIER_ONLY_NO_DEADLINE_INSTANCE" in r.signals
    assert r.deadline_instances == ()


def test_backward_semantics_are_preserved_not_forward_calculated():
    d, rt = env()
    rid = d.backward_or_window_rule_ids[0]
    rule = d.rules_by_id[rid]
    r = rt.evaluate_handoff(
        tenant_id="T", case_scope_id="C", source_entity_id="S", deadline_rule_id=rid,
        trigger=verified_trigger(rule),
    )
    assert "BACKWARD_SEMANTICS_PRESERVED" in r.signals
    assert r.calculation_runs == ()


def test_contested_notification_and_ambiguous_trigger_block():
    d, rt = env()
    rid = "DLR-SY-CPM-A36-A"
    trig = verified_trigger(d.rules_by_id[rid])
    trig.update({
        "verification_status": "CONTESTED",
        "notification_validity": "UNRESOLVED",
        "alternative_trigger_candidates": ["A", "B"],
    })
    r = rt.evaluate_handoff(
        tenant_id="T", case_scope_id="C", source_entity_id="S", deadline_rule_id=rid, trigger=trig
    )
    assert "DLC-E011" in r.blocking_errors
    assert "DLC-E012" in r.blocking_errors
    assert "DLC-E016" in r.blocking_errors
    assert r.deadline_instances == ()


def test_final_legal_effect_and_llm_calculation_are_prohibited():
    d, rt = env()
    rid = next(iter(d.rules_by_id))
    r = rt.evaluate_handoff(
        tenant_id="T", case_scope_id="C", source_entity_id="S", deadline_rule_id=rid,
        trigger=verified_trigger(d.rules_by_id[rid]), final_legal_effect_requested=True,
        llm_in_calculation_path=True,
    )
    assert "DLC-E052" in r.blocking_errors
    assert "DLC-E053" in r.blocking_errors
    assert r.candidates[0].automatic_final_legal_effect_allowed is False


def test_d30_zero_primary_candidate_guard():
    _, rt = env()
    r = rt.evaluate_handoff(
        tenant_id="T", case_scope_id="CASE-T", source_entity_id="D30-X",
        deadline_rule_id="DLR-SY-CPM-A34-A", trigger=None, source_document_id="D30",
        derived_secondary_source=True,
    )
    assert r.candidates == ()
    assert r.deadline_instances == ()
    assert r.calculation_runs == ()
    assert r.signals == ("DERIVED_SOURCE_SUPPRESSED",)


def test_tenant_and_case_scope_batch_isolation_including_judicial_liability_scope():
    d, rt = env()
    b = DeadlineEngineBatchProcessor(rt)
    rid = "DLR-SY-CPM-A34-A"
    trig = verified_trigger(d.rules_by_id[rid])
    common = dict(tenant_id="TENANT-A", source_entity_id="E-1", deadline_rule_id=rid, trigger=trig)
    a = b.process(case_scope_id="CASE-SY-DAM-REALTY-2022-000731", **common)
    dup = b.process(case_scope_id="CASE-SY-DAM-REALTY-2022-000731", **common)
    other = b.process(case_scope_id="CASE-SY-DAM-REALTY-2022-000731::JUDICIAL_LIABILITY", **common)
    other_tenant = b.process(tenant_id="TENANT-B", case_scope_id="CASE-SY-DAM-REALTY-2022-000731", source_entity_id="E-1", deadline_rule_id=rid, trigger=trig)
    assert a is not None and dup is None and other is not None and other_tenant is not None
    assert a.stable_projection_sha256 != other.stable_projection_sha256
    assert a.stable_projection_sha256 != other_tenant.stable_projection_sha256


def test_replay_is_deterministic():
    d, rt = env()
    rid = "DLR-SY-CPM-A34-A"
    kw = dict(tenant_id="T", case_scope_id="C", source_entity_id="S", deadline_rule_id=rid,
              trigger=verified_trigger(d.rules_by_id[rid]))
    a = rt.evaluate_handoff(**kw)
    b = rt.evaluate_handoff(**kw)
    assert a.stable_projection_sha256 == b.stable_projection_sha256


def test_pure_temporal_policy_primitives_are_deterministic_and_rule_agnostic():
    k = DeterministicTemporalPolicyKernel
    assert k.forward_days(date(2026, 1, 1), 30, include_anchor=False) == date(2026, 1, 31)
    assert k.forward_days(date(2026, 1, 1), 1, include_anchor=True) == date(2026, 1, 1)
    assert k.backward_days(date(2026, 1, 31), 15) == date(2026, 1, 16)
    assert k.add_months_clamped(date(2025, 1, 31), 1) == date(2025, 2, 28)
    assert k.add_months_clamped(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert k.roll_forward(date(2026, 1, 31), {date(2026, 1, 31), date(2026, 2, 1)}) == date(2026, 2, 2)
    assert k.formula_with_caps(3, 2, 10, 20) == 10
    assert k.formula_with_caps(7, 2, 10, 20) == 14
    assert k.formula_with_caps(12, 2, 10, 20) == 20
    assert k.interruption_restart(date(2026, 1, 20), 30) == date(2026, 2, 19)

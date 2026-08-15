import os

import pytest

from qanun_case_runtime.defense import (
    DefensePackageLoader,
    DefenseShadowEngine,
)
from qanun_case_runtime.governance import GovernanceRuntime


ZIP_ENV = "QANUN_DEFENSE_DELIVERY_ZIP"


def load_defense():
    zip_path = os.environ.get(ZIP_ENV)
    if not zip_path:
        pytest.skip(f"set {ZIP_ENV} to run DEFENSE delivery integration tests")
    runtime = GovernanceRuntime(production_activation_allowed=False)
    return DefensePackageLoader(runtime).load(zip_path)


def test_defense_delivery_counts_and_activation_gate():
    loaded = load_defense()
    report = loaded.registry_report
    assert report.valid
    assert report.registry_count == 260
    assert report.canonical_count == 207
    assert report.validated_count == 98
    assert report.scope_guarded_count == 109
    assert report.merge_count == 26
    assert report.reclassify_count == 27
    assert report.family_count == 13
    assert report.relation_count == 74
    assert report.transition_count == 21
    assert loaded.runtime_status == "LOADED_NOT_ACTIVATED"
    assert "DEFENSE_PACKAGE_SOURCE_DISABLED" in loaded.activation_blockers


def test_golden_case_core_defenses_route_to_real_canonical_ids():
    loaded = load_defense()
    ids = [
        "DEF_PRO_INVALID_SERVICE",
        "DEF_PAR_PREMATURE_ACTION",
        "DEF_EVD_DENIAL_PRIVATE_INSTRUMENT_SIGNATURE",
        "DEF_SUB_SIMULATION",
    ]
    for defense_id in ids:
        decision = loaded.registry.route(defense_id)
        assert decision.route_kind == "CANONICAL_DEFENSE_CANDIDATE"
        assert decision.target == defense_id
        assert decision.automatic_legal_effect_allowed is False


def test_reclassified_non_defense_is_not_promoted_to_defense_candidate():
    loaded = load_defense()
    decision = loaded.registry.route("DEF_EVD_PRODUCE_ORIGINAL_REQUEST")
    assert decision.route_kind == "RECLASSIFY_OUT_OF_DEFENSE"
    assert decision.target == ("REQUEST/EVIDENCE_PRODUCTION",)


def test_counter_defense_compatibility_record_does_not_become_canonical_defense():
    loaded = load_defense()
    decision = loaded.registry.route("DEF_PRO_PROCEDURAL_DEFECT_CURED")
    assert decision.route_kind == "RECLASSIFY_OUT_OF_DEFENSE"
    assert decision.target == "COUNTER_DEFENSE to procedural nullity"


def test_shadow_candidate_never_issues_stable_id_or_legal_effect():
    loaded = load_defense()
    engine = DefenseShadowEngine(loaded)
    result = engine.observe(
        case_id="CASE-SY-DAM-REALTY-2022-000731",
        source_document_id="D4",
        defense_type_id="DEF_SUB_SIMULATION",
        raw_text="العلاقة الحقيقية كانت قرضاً وورقة البيع صورية",
        source_quote="العلاقة الحقيقية كانت قرضاً مقداره /300,000,000/ ل.س، وطلب المدعي ورقة ضمان على شكل بيع صوري.",
        litigation_stage="FIRST_INSTANCE",
        raised_by_party_candidate_ref="test:CASE-SY-DAM-REALTY-2022-000731:SAMER",
        target_type="DOCUMENT",
        target_candidate_ref="doccand-contract",
        requested_effects=("REJECT_SPECIFIC_PERFORMANCE",),
    )
    assert result.candidate is not None
    assert result.candidate.status == "SHADOW_CANDIDATE_ONLY"
    assert result.candidate.stable_defense_id is None
    assert result.candidate.canonical_persistence_allowed is False
    assert result.candidate.automatic_legal_effect_allowed is False
    assert "DEFENSE_PACKAGE_SOURCE_DISABLED" in result.candidate.blockers


def test_reclassification_observation_emits_no_defense_candidate():
    loaded = load_defense()
    engine = DefenseShadowEngine(loaded)
    result = engine.observe(
        case_id="CASE-SY-DAM-REALTY-2022-000731",
        source_document_id="D18",
        defense_type_id="DEF_EVD_PRODUCE_ORIGINAL_REQUEST",
        raw_text="نطلب إبراز الأصل",
        source_quote="نطلب إبراز الأصل",
        litigation_stage="FIRST_INSTANCE",
    )
    assert result.routing.route_kind == "RECLASSIFY_OUT_OF_DEFENSE"
    assert result.candidate is None

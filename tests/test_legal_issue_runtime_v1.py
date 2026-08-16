import sys, json, gzip, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from qanun_case_runtime.legal_issue import LegalIssuePackageLoader, LegalIssueSandboxRuntime
PKG="/mnt/data/QANUN_AI_LEGAL_ISSUE_LEGAL_REBUILD_V1_1_PRODUCTION_CANDIDATE(1).json"
REP="/mnt/data/QANUN_AI_LEGAL_ISSUE_LEGAL_REBUILD_REPORT_V1_1(1).md"
FIX=ROOT/"tests/fixtures/statement_golden_case_d01_d30.json.gz"
def loaded_runtime():
    d=LegalIssuePackageLoader().load(PKG,REP)
    return d, LegalIssueSandboxRuntime(d)
def test_source_and_static_contracts():
    d,_=loaded_runtime(); sv=d["static_rebuild_validation"]["checks"]
    assert sv["issue_type_count"]==409 and sv["dictionary_entry_count"]==409
    assert sv["discovery_rule_count"]==1333 and sv["normalized_relation_contract_count"]==82
    assert sv["mandatory_test_spec_count"]==35 and sv["legal_rebuild_regression_spec_count"]==15
    assert sv["new_canonical_issue_ids"]==0 and sv["deleted_canonical_issue_ids"]==0
def test_all_35_mandatory_specs_contract_harness_executes_without_forbidden_finalization():
    d,rt=loaded_runtime(); specs=d["generated_components"]["21_test_cases.json"]["tests"]
    assert len(specs)==35
    for i,s in enumerate(specs,1):
        doc={"document_id":f"LI-T{i:02d}","document_type_id":"TEST_SCENARIO_CONTRACT","raw_text":s["scenario_ar"],"derived_secondary_source":False}
        r=rt.extract_document("CASE-CONTRACT",doc)
        assert all(c.canonical_persistence_allowed is False and c.automatic_verification_allowed is False for c in r.issue_candidates)
        assert all(t.canonical_persistence_allowed is False for t in r.court_treatments)
        assert all(h["status"]=="LEGAL_REFERENCE_RESEARCH_NOT_EXECUTED" for h in r.research_handoffs)
def test_15_legal_regressions_present_and_boundaries_declared():
    d,_=loaded_runtime(); regs=d["legal_rebuild_regression_specs"]
    assert len(regs)==15
    keys={x["case_key"] for x in regs}
    for k in ["STAY_VS_INTERRUPTION","DIGITAL_EVIDENCE_MULTI_AXIS","POSSESSION_TITLE","FINALITY_RESJUDICATA_ENFORCEABILITY","PARTIAL_CASSATION","COURT_QUOTED_PRECEDENT","TRANSITIONAL_LAW","DRAFT_AMENDMENT"]: assert k in keys
def test_golden_d01_d30_and_derived_suppression():
    _,rt=loaded_runtime(); fixture=json.loads(gzip.open(FIX,"rt",encoding="utf-8").read()); out=rt.extract_batch(fixture["case_id"],fixture["documents"])
    assert len(out)==30
    d30=out[(fixture["case_id"],"D30")]
    assert len(d30.issue_candidates)==0 and len(d30.court_treatments)==0
    assert "DERIVED_SOURCE_SUPPRESSED" in d30.semantic_signals
    assert sum(len(x.issue_candidates) for x in out.values())>0
def test_party_argument_never_becomes_court_resolution():
    _,rt=loaded_runtime(); doc={"document_id":"X1","document_type_id":"DEFENSE_MEMORANDUM","raw_text":"دفع المدعى عليه بعدم الاختصاص المحلي وتمسك ببطلان التبليغ.","derived_secondary_source":False}
    r=rt.extract_document("C1",doc)
    assert all(t.status!="EXPRESS_RESOLUTION_CANDIDATE_REQUIRES_DECISION_POSITION" for t in r.court_treatments)
def test_court_resolution_is_only_candidate_and_requires_decision_position():
    _,rt=loaded_runtime(); doc={"document_id":"X2","document_type_id":"FIRST_INSTANCE_JUDGMENT","raw_text":"قررت المحكمة رد الدفع بعدم الاختصاص المحلي.","derived_secondary_source":False}
    r=rt.extract_document("C1",doc)
    assert all(t.decision_position_binding_required for t in r.court_treatments)
    assert all(t.canonical_persistence_allowed is False for t in r.court_treatments)
def test_determinism():
    _,rt=loaded_runtime(); doc={"document_id":"X3","document_type_id":"MEMO","raw_text":"يثور النزاع حول حجية الأمر المقضي وصحة التبليغ.","derived_secondary_source":False}
    a=rt.extract_document("C1",doc); b=rt.extract_document("C1",doc)
    assert a.stable_projection_sha256==b.stable_projection_sha256
def test_batch_case_scope_isolation():
    _,rt=loaded_runtime(); d={"document_id":"D1","document_type_id":"MEMO","raw_text":"مسألة الاختصاص النوعي.","derived_secondary_source":False}
    a=rt.extract_batch("C1",[dict(d,case_scope_id="C1")]); b=rt.extract_batch("C2",[dict(d,case_scope_id="C2")])
    aa=next(iter(a.values())); bb=next(iter(b.values()))
    if aa.issue_candidates and bb.issue_candidates: assert aa.issue_candidates[0].candidate_id != bb.issue_candidates[0].candidate_id
def test_source_runtime_and_production_state_preserved():
    d,_=loaded_runtime()
    assert d["package_status"]=="PRODUCTION_CANDIDATE_NOT_FROZEN"
    assert d["production_activation_eligible"] is False
    assert d["static_rebuild_validation"]["runtime_tests"]=="NOT_RUN_RUNTIME_UNAVAILABLE"

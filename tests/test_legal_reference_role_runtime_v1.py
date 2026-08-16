import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"src"))
from qanun_case_runtime.legal_reference_role import LegalReferenceRolePackageLoader
from qanun_case_runtime.legal_reference_role_runtime import LegalReferenceRoleSandboxRuntime
PKG=r"/mnt/data/QANUN_AI_LEGAL_REFERENCE_ROLE_LEGAL_REBUILD_V1_1_PRODUCTION_CANDIDATE(1).json"
REPORT=r"/mnt/data/QANUN_AI_LEGAL_REFERENCE_ROLE_LEGAL_REBUILD_REPORT_V1_1(1).md"
def env():
    d=LegalReferenceRolePackageLoader().load(PKG,REPORT); return d,LegalReferenceRoleSandboxRuntime(d)
def test_source_contract_and_inventory():
    d,_=env(); assert len(d.role_ids)==279 and len(d.query_intent_ids)==41 and len(d.scenario_tests)==25
def test_all_25_scenarios_execute():
    d,rt=env()
    for t in d.scenario_tests:
        s=t["source_case_entity"]; r=rt.extract("CASE-T",s["type"],s["id"],s["scenario"])
        assert [x.role_id for x in r.needs]==t["expected_role_ids"]
        assert [x.query_intent_id for x in r.query_intents]==t["expected_query_intent_ids"]
        assert all(x.lookup_policy==t["expected_lookup_policy"] for x in r.needs+r.query_intents)
        assert all(x.resolution_status=="UNRESOLVED" for x in r.needs)
def test_no_resolution_role_assignment_or_cypher():
    d,rt=env()
    for t in d.scenario_tests:
        s=t["source_case_entity"]; r=rt.extract("CASE-T",s["type"],s["id"],s["scenario"])
        assert all(x.automatic_role_assignment_allowed is False for x in r.needs)
        assert all(x.cypher_generated is False for x in r.query_intents)
        assert r.query_packet["cypher_template"] is None and r.query_packet["schema_dependency_missing"] is True
def test_party_citation_not_court_application():
    _,rt=env(); r=rt.extract("C","STATEMENT","S","الخصم يستشهد باجتهاد")
    assert [x.query_intent_id for x in r.query_intents]==["RESOLVE_EXPLICIT_JUDGMENT_REFERENCE"]
def test_historical_version_requires_resolution():
    _,rt=env(); r=rt.extract("C","FACT","F","المادة تعدلت بعد الواقعة")
    assert "FIND_APPLICABLE_VERSION_AT_DATE" in [x.query_intent_id for x in r.query_intents]
def test_general_rule_exception_searches_both():
    _,rt=env(); r=rt.extract("C","LEGAL_ISSUE","L","general rule with special exception")
    assert set(x.query_intent_id for x in r.query_intents)=={"EXPAND_GENERAL_RULE_TO_SPECIAL_RULE","FIND_EXCEPTION_ARTICLES"}
def test_public_graph_isolation_contract():
    _,rt=env(); r=rt.extract("C","DEFENSE","D","عدم اختصاص")
    assert r.query_packet["public_graph_read_only"] is True and r.query_packet["private_case_data_persisted_to_public_graph"] is False
def test_determinism():
    _,rt=env(); a=rt.extract("C","DEFENSE","D","عدم اختصاص"); b=rt.extract("C","DEFENSE","D","عدم اختصاص"); assert a.stable_projection_sha256==b.stable_projection_sha256
def test_batch_case_scope_isolation():
    from qanun_case_runtime.legal_reference_role_batch import LegalReferenceRoleBatchProcessor
    _,rt=env(); b=LegalReferenceRoleBatchProcessor(rt)
    a=b.process('CASE-A','DEFENSE','D-1','عدم اختصاص')
    dup=b.process('CASE-A','DEFENSE','D-1','عدم اختصاص')
    other=b.process('CASE-B','DEFENSE','D-1','عدم اختصاص')
    assert a is not None and dup is None and other is not None
    assert a.stable_projection_sha256 != other.stable_projection_sha256

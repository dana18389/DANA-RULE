from qanun_case_runtime.case_proceeding_core import CaseProceedingCoreRuntime, stable_projection_sha256

def mention(doc, role="CURRENT_PROCEEDING_MENTION", tenant="T1", number="100", year="2024", court="محكمة أ"):
    return {
        "tenant_id":tenant,"case_scope_id":"CASE-X","document_id":doc,
        "proceeding_mentions":[{
            "mention_role":role,"court_name_raw":court,"chamber_name_raw":None,
            "case_number_raw":number,"case_year_raw":year,"registration_number_raw":None,
            "proceeding_type_raw":None,"procedural_stage_raw":None,
            "related_case_reference_raw":None,"related_decision_reference_raw":None,
            "relationship_phrase_raw":None,"source_quote":"أساس 100 لعام 2024","source_locator":f"{doc}:1"
        }]
    }

def test_d30_zero_primary():
    rt=CaseProceedingCoreRuntime(); p=mention("D30"); p["derived_source"]=True
    assert rt.extract_mentions(p)==()

def test_same_number_different_court_no_merge():
    rt=CaseProceedingCoreRuntime(); a=rt.extract_mentions(mention("D1",court="محكمة أ"))[0]; b=rt.extract_mentions(mention("D2",court="محكمة ب"))[0]
    r=rt.resolve_pair(a,b)
    assert r.resolution_status=="UNRESOLVED" and r.stable_instance_id is None and r.canonical_persistence_allowed is False

def test_same_number_different_year_no_merge():
    rt=CaseProceedingCoreRuntime(); a=rt.extract_mentions(mention("D1",year="2024"))[0]; b=rt.extract_mentions(mention("D2",year="2025"))[0]
    assert rt.resolve_pair(a,b).resolution_status=="UNRESOLVED"

def test_same_number_same_year_same_raw_court_still_no_auto_merge():
    rt=CaseProceedingCoreRuntime(); a=rt.extract_mentions(mention("D1"))[0]; b=rt.extract_mentions(mention("D2"))[0]; r=rt.resolve_pair(a,b)
    assert r.resolution_status=="UNRESOLVED" and r.stable_instance_id is None

def test_current_and_referenced_stay_distinct():
    rt=CaseProceedingCoreRuntime(); p=mention("J1")
    p["proceeding_mentions"].append(dict(p["proceeding_mentions"][0], mention_role="REFERENCED_PROCEEDING_MENTION", case_number_raw="50", case_year_raw="2022", source_quote="قضية أساس 50 لعام 2022", source_locator="J1:2"))
    rows=rt.extract_mentions(p)
    assert len(rows)==2 and rows[0].mention_role != rows[1].mention_role

def test_cross_tenant_hard_reject():
    rt=CaseProceedingCoreRuntime(); a=rt.extract_mentions(mention("D1",tenant="T1"))[0]; b=rt.extract_mentions(mention("D1",tenant="T2"))[0]
    assert rt.resolve_pair(a,b).resolution_status=="REJECTED_CROSS_TENANT"

def test_no_source_trace_no_candidate():
    rt=CaseProceedingCoreRuntime(); p=mention("D1"); p["proceeding_mentions"][0]["source_quote"]=""
    assert rt.extract_mentions(p)==()

def test_lineage_requires_explicit_source_relation():
    rt=CaseProceedingCoreRuntime(); a=rt.extract_mentions(mention("D1"))[0]; b=rt.extract_mentions(mention("D2",number="200"))[0]
    assert rt.propose_lineage(a,b,False)["status"]=="UNRESOLVED_NO_EXPLICIT_SOURCE_RELATION"
    assert rt.propose_lineage(a,b,True)["status"]=="RELATION_CANDIDATE_ONLY"

def test_lineage_cross_tenant_rejected():
    rt=CaseProceedingCoreRuntime(); a=rt.extract_mentions(mention("D1",tenant="T1"))[0]; b=rt.extract_mentions(mention("D2",tenant="T2"))[0]
    assert rt.propose_lineage(a,b,True)["status"]=="REJECTED_CROSS_TENANT"

def test_missing_scope_rejected():
    rt=CaseProceedingCoreRuntime(); p=mention("D1"); p["case_scope_id"]=""
    try:
        rt.extract_mentions(p); assert False
    except ValueError:
        assert True

def test_determinism():
    rt=CaseProceedingCoreRuntime(); a=rt.extract_mentions(mention("D1"))[0]; b=rt.extract_mentions(mention("D2"))[0]
    r1=rt.resolve_pair(a,b); r2=rt.resolve_pair(a,b)
    assert r1.candidate_key==r2.candidate_key
    assert stable_projection_sha256(r1.__dict__)==stable_projection_sha256(r2.__dict__)

def test_no_llm_stable_ids():
    rt=CaseProceedingCoreRuntime(); a=rt.extract_mentions(mention("D1"))[0]; b=rt.extract_mentions(mention("D2"))[0]
    assert rt.resolve_pair(a,b).stable_instance_id is None

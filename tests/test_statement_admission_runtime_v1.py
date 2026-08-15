import json, os, gzip, hashlib
from pathlib import Path
from qanun_case_runtime.governance import GovernanceRuntime
from qanun_case_runtime.statement_admission import StatementAdmissionPackageLoader
from qanun_case_runtime.statement_admission_runtime import StatementAdmissionActivationPatch, StatementAdmissionSandboxRuntime
from qanun_case_runtime.statement_admission_batch import StatementAdmissionBatchDocument, StatementAdmissionBatchOrchestrator

ROOT=Path(__file__).resolve().parent.parent
SRC_ENV="QANUN_STATEMENT_ADMISSION_PACKAGE"
PATCH=ROOT/"config/statement_admission_runtime_activation_patch_v1.json"
FIX=ROOT/"tests/fixtures/statement_golden_case_d01_d30.json.gz"

def runtime():
    src=os.environ.get(SRC_ENV)
    if not src: import pytest; pytest.skip(f"set {SRC_ENV} to run STATEMENT_ADMISSION integration tests")
    loaded=StatementAdmissionPackageLoader(GovernanceRuntime(production_activation_allowed=False)).load(Path(src))
    patch=StatementAdmissionActivationPatch.from_mapping(json.loads(PATCH.read_text(encoding="utf-8")))
    return loaded,StatementAdmissionSandboxRuntime(loaded,patch)

def fact_refs(docid):
    if docid=="D15":
        return {"fact_candidate:D15:samer_payment":{"canonical_type_id":"FACT_PAYMENT_STATUS","source_document_id":"D15"}}
    return None

def docs():
    comp=FIX.read_bytes(); assert hashlib.sha256(comp).hexdigest()=="c15e5f44cbb11fe14f3ff3da7703758bfd6cd9897e4b83c513290358d0a459d7"
    raw=gzip.decompress(comp); assert hashlib.sha256(raw).hexdigest()=="e1d323912286b6a6eede5d1a7449bcfdfd9fd438f8a7a4540f67fc7de23f50c0"
    f=json.loads(raw.decode("utf-8"))
    return [StatementAdmissionBatchDocument(r["case_scope_id"],r["document_id"],r["document_date"],r["document_type_id"],r["litigation_stage"],r["raw_text"],fact_refs(r["document_id"]),None,r.get("derived_secondary_source",False)) for r in f["documents"]]

def test_static_registry_and_lineage():
    loaded,rt=runtime(); r=loaded.registry_report
    assert r.valid
    assert (r.statement_event_type_count,r.statement_function_type_count,r.proposition_type_count)==(29,37,45)
    assert (r.denial_type_count,r.admission_candidate_type_count,r.concrete_taxonomy_type_count)==(14,36,174)
    assert (r.dictionary_entry_count,r.relation_count,r.validation_check_count,r.unresolved_extension_count)==(174,116,55,3)
    assert loaded.baseline_sha256=="f19b51cf0fe54a97d00491f1a852198987d6139809396a0dfce02261f24e2d55"
    assert rt.STATUS=="SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY"

def test_conditional_reply_and_legal_argument_do_not_auto_create_admission():
    _,rt=runtime(); by=dict(StatementAdmissionBatchOrchestrator(rt).run(docs()).document_results)
    d03=by["D03"]
    assert len(d03.statements)==2 and len(d03.admissions)==0
    assert any("CONSENT_CANDIDATE" in s.semantic_boundary_flags for s in d03.statements)
    assert any("LEGAL_ARGUMENT_CANDIDATE" in s.semantic_boundary_flags for s in d03.statements)
    assert all("NO_AUTOMATIC_LEGAL_EFFECT" in s.blockers for s in d03.statements)
    d25=by["D25"]
    assert len(d25.admissions)==0
    assert any("LEGAL_ARGUMENT_CANDIDATE" in s.semantic_boundary_flags for s in d25.statements)

def test_denial_testimony_admission_and_reported_speech_boundaries():
    _,rt=runtime(); by=dict(StatementAdmissionBatchOrchestrator(rt).run(docs()).document_results)
    d08=by["D08"]
    sig=next(p for p in d08.propositions if p.denial_type_id=="DENIAL_OF_SIGNATURE")
    assert sig.function_type_id=="DENIAL" and not d08.admissions
    d11=by["D11"]
    assert len(d11.statements)==1 and len(d11.admissions)==0
    assert "REPORTED_STATEMENT_NOT_DIRECT_SPEAKER_STATEMENT" in d11.propositions[0].blockers
    d15=by["D15"]
    assert len(d15.statements)==5 and sum(s.event_type_id=="TESTIMONIAL_STATEMENT" for s in d15.statements)==2
    assert len(d15.admissions)==3
    pay=next(a for a in d15.admissions if a.admission_type_id=="PAYMENT_RECEIPT_ADMISSION")
    assert "PAYMENT_RECEIPT_ADMISSION_DOES_NOT_ESTABLISH_PAYMENT_CAUSE" in pay.blockers
    assert "PAYMENT_RECEIPT_ADMISSION_DOES_NOT_EXTINGUISH_OBLIGATION" in pay.blockers
    support=[r for r in d15.relations if r.relation_id=="PROPOSITION_ADMITS_FACT_CANDIDATE"]
    assert {r.target_ref for r in support}=={"fact_candidate:D15:samer_payment"}
    for did in ["D18","D20","D22","D24"]:
        r=by[did]; assert r.statements and len(r.admissions)==0
        assert all("REPORTED_STATEMENT_NOT_DIRECT_SPEAKER_STATEMENT" in p.blockers for p in r.propositions)
    assert any("COURT_NARRATION_NOT_COURT_ADOPTION" in p.blockers for p in by["D18"].propositions)

def test_candidate_only_and_unresolved_extensions_have_no_ids():
    loaded,rt=runtime(); run=StatementAdmissionBatchOrchestrator(rt).run(docs())
    exts=loaded.registry.unresolved_extensions
    assert {x["concept"] for x in exts}=={"CONSENT","WAIVER","LEGAL_ARGUMENT"}
    assert all(x["stable_type_id"] is None for x in exts)
    for _,res in run.document_results:
        for x in res.statements: assert x.stable_statement_id is None and not x.canonical_persistence_allowed and not x.automatic_legal_effect_allowed
        for x in res.propositions: assert x.stable_proposition_id is None and not x.canonical_persistence_allowed and not x.automatic_fact_truth_allowed
        for x in res.admissions: assert x.stable_admission_id is None and not x.canonical_persistence_allowed and not x.automatic_legal_effect_allowed and not x.fact_truth_transition_allowed
        for x in res.relations: assert x.status=="RELATION_CANDIDATE_ONLY_UNVERIFIED" and not x.user_verified and not x.canonical_persistence_allowed

def test_full_golden_determinism_scope_and_derived_summary():
    _,rt=runtime(); orch=StatementAdmissionBatchOrchestrator(rt); ds=docs()
    a=orch.run(ds); b=orch.run(ds); c=orch.run(list(reversed(ds)))
    assert a.stable_projection_sha256==b.stable_projection_sha256==c.stable_projection_sha256=="a26fe0d3f5b09a9ab6c122dc0963d41ff7b53a73b7e7a2bd652a98271216e6d3"
    by=dict(a.document_results)
    assert not by["D30"].statements and not by["D30"].propositions and not by["D30"].admissions
    assert all(s.case_id.endswith("::JUDICIAL_LIABILITY") for s in by["D24"].statements)
    total_s=sum(len(r.statements) for _,r in a.document_results); total_p=sum(len(r.propositions) for _,r in a.document_results)
    total_a=sum(len(r.admissions) for _,r in a.document_results); total_rel=sum(len(r.relations) for _,r in a.document_results)
    assert (total_s,total_p,total_a,total_rel)==(18,21,3,62)

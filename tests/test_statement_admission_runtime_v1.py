import gzip, hashlib, json, os
from pathlib import Path
import pytest
from qanun_case_runtime.governance import GovernanceRuntime
from qanun_case_runtime.statement_admission import StatementAdmissionPackageLoader
from qanun_case_runtime.statement_admission_runtime import StatementAdmissionActivationPatch, StatementAdmissionSandboxRuntime
from qanun_case_runtime.statement_admission_batch import StatementBatchDocument, StatementBatchOrchestrator

ROOT=Path(__file__).resolve().parent.parent
PATCH=ROOT/'config/statement_admission_runtime_activation_patch_v1.json.gz'
FIX=ROOT/'tests/fixtures/statement_golden_case_d01_d30.json.gz'
ZIP_ENV='QANUN_STATEMENT_ADMISSION_DELIVERY_ZIP'
GOLDEN='b88eb1a62e6ded8aad57bc78c614655b296bdc8caa56f36f2d18fe21ac3a9b11'
GZ_SHA='e8d96714d7b5b19a03393f971df4ae5f59d20beee622c6cd505815ffa0786444'
RAW_SHA='9ea186b9ed6736e995db17670a9d8be9005ec23dc5da1576e85d43a28a01c220'
DOCX_SHA='83fc2b2324750246bd5dc3e3d0fd4d89de67bc8c38192d97c3f43e712508d970'

def runtime():
    p=os.environ.get(ZIP_ENV)
    if not p: pytest.skip(f'set {ZIP_ENV}')
    loaded=StatementAdmissionPackageLoader(GovernanceRuntime(False)).load(p)
    patch=StatementAdmissionActivationPatch.from_mapping(json.loads(gzip.decompress(PATCH.read_bytes())))
    return loaded, StatementAdmissionSandboxRuntime(loaded=loaded,patch=patch)

def docs():
    comp=FIX.read_bytes(); assert hashlib.sha256(comp).hexdigest()==GZ_SHA
    raw=gzip.decompress(comp); assert hashlib.sha256(raw).hexdigest()==RAW_SHA
    obj=json.loads(raw); assert obj['source_docx_sha256']==DOCX_SHA
    return [StatementBatchDocument(r['case_scope_id'],r['document_id'],r['document_date'],r['document_type_id'],r['litigation_stage'],r['raw_text'],r['derived_secondary_source']) for r in obj['documents']]

def run_all():
    _,rt=runtime(); return StatementBatchOrchestrator(rt).run(docs())

def test_static_delivery_and_registry_contract():
    loaded,rt=runtime(); r=loaded.registry_report
    assert r.valid
    assert (r.statement_event_types,r.statement_function_types,r.proposition_types,r.denial_types)==(29,37,45,14)
    assert (r.admission_candidate_types,r.attribution_types,r.scope_types,r.explicitness_types,r.lifecycle_statuses)==(36,10,7,5,16)
    assert (r.concrete_taxonomy_types,r.dictionary_entries,r.relationship_types)==(174,174,116)
    assert (r.statement_transitions,r.admission_transitions,r.backend_models,r.source_validation_checks,r.unresolved_extensions)==(16,14,14,55,3)
    assert loaded.runtime_status=='LOADED_NOT_ACTIVATED'
    assert rt.STATUS=='SANDBOX_RUNTIME_ENABLED_SHADOW_CANDIDATE_ONLY'
    assert loaded.registry.package['package_metadata']['runtime_activation_state']=='NOT_RUNTIME_ACTIVATED'
    assert loaded.registry.package['package_metadata']['production_eligible'] is False

def test_external_document_admission_is_shadow_only_and_authenticity_guarded():
    by=dict(run_all().document_results); d02=by[('CASE-SY-DAM-REALTY-2022-000731','D02')]
    assert len(d02.admission_candidates)==1
    a=d02.admission_candidates[0]
    assert a.admission_type_id=='PAYMENT_RECEIPT_ADMISSION'
    assert a.context_type_id=='EXTRAJUDICIAL_ADMISSION_CANDIDATE'
    assert a.source_capacity_type_id=='ADMISSION_IN_EXTERNAL_DOCUMENT_CANDIDATE'
    assert {'SOURCE_DOCUMENT_AUTHENTICITY_UNRESOLVED','PAYMENT_RECEIPT_ADMISSION_DOES_NOT_ESTABLISH_PAYMENT_CAUSE','PAYMENT_RECEIPT_ADMISSION_DOES_NOT_ESTABLISH_OBLIGATION_EXTINGUISHMENT'} <= set(a.blockers)
    assert not a.canonical_assessment_creation_allowed and not a.canonical_persistence_allowed and not a.automatic_legal_effect_allowed

def test_consent_legal_argument_representative_and_hypothetical_guards():
    by=dict(run_all().document_results)
    d03=by[('CASE-SY-DAM-REALTY-2022-000731','D03')]
    assert len(d03.statement_candidates)==2 and not d03.admission_candidates
    assert any('CONSENT_CANDIDATE' in s.semantic_boundary_flags for s in d03.statement_candidates)
    assert any('LEGAL_ARGUMENT_CANDIDATE' in s.semantic_boundary_flags for s in d03.statement_candidates)
    d08=by[('CASE-SY-DAM-REALTY-2022-000731','D08')]
    assert all(s.event_type_id=='REPRESENTATIVE_STATEMENT' for s in d08.statement_candidates)
    assert all('REPRESENTATIVE_STATEMENT_NOT_PRINCIPAL_STATEMENT' in s.blockers for s in d08.statement_candidates)
    assert any(p.denial_type_id=='DENIAL_OF_SIGNATURE' for p in d08.proposition_candidates)
    assert not d08.admission_candidates
    d17=by[('CASE-SY-DAM-REALTY-2022-000731','D17')]
    hyp=next(p for p in d17.proposition_candidates if p.occurrence_key=='HYPOTHETICAL_SIGNATURE_NOT_ADMISSION')
    assert hyp.function_type_id=='HYPOTHETICAL_STATEMENT' and not d17.admission_candidates

def test_hearing_direct_reported_and_admission_scope_separation():
    by=dict(run_all().document_results); d15=by[('CASE-SY-DAM-REALTY-2022-000731','D15')]
    assert (len(d15.statement_candidates),len(d15.proposition_candidates),len(d15.admission_candidates))==(6,10,3)
    assert sum(s.event_type_id=='TESTIMONIAL_STATEMENT' for s in d15.statement_candidates)==2
    assert sum(s.event_type_id=='REPORTED_SPEECH' for s in d15.statement_candidates)==2
    assert all(not a.source_quote.startswith('الشاهد فادي') for a in d15.admission_candidates)
    types={a.admission_type_id for a in d15.admission_candidates}
    assert types=={'PAYMENT_RECEIPT_ADMISSION','DOCUMENT_ISSUANCE_ADMISSION','FACT_ADMISSION'}
    pay=next(a for a in d15.admission_candidates if a.admission_type_id=='PAYMENT_RECEIPT_ADMISSION')
    assert {'PAYMENT_RECEIPT_ADMISSION_DOES_NOT_ESTABLISH_PAYMENT_CAUSE','PAYMENT_RECEIPT_ADMISSION_DOES_NOT_ESTABLISH_OBLIGATION_EXTINGUISHMENT'} <= set(pay.blockers)
    doc=next(a for a in d15.admission_candidates if a.admission_type_id=='DOCUMENT_ISSUANCE_ADMISSION')
    assert 'DOCUMENT_ISSUANCE_ADMISSION_DOES_NOT_EQUAL_DOCUMENT_CONTENT_ADMISSION' in doc.blockers
    fact=next(a for a in d15.admission_candidates if a.admission_type_id=='FACT_ADMISSION')
    assert 'KNOWLEDGE_ADMISSION_DOES_NOT_ESTABLISH_UNDERLYING_RIGHT' in fact.blockers

def test_reported_and_court_narration_never_create_new_admission():
    by=dict(run_all().document_results)
    for scope,did in [('CASE-SY-DAM-REALTY-2022-000731','D18'),('CASE-SY-DAM-REALTY-2022-000731','D20'),('CASE-SY-DAM-REALTY-2022-000731','D22')]:
        r=by[(scope,did)]; assert not r.admission_candidates; assert all(s.reported_only for s in r.statement_candidates)
    d18=by[('CASE-SY-DAM-REALTY-2022-000731','D18')]
    assert d18.statement_candidates[0].court_narration
    d24=by[('CASE-SY-DAM-REALTY-2022-000731::JUDICIAL_LIABILITY','D24')]
    assert len(d24.statement_candidates)==2 and not d24.admission_candidates
    assert all(s.case_id.endswith('::JUDICIAL_LIABILITY') and s.reported_only for s in d24.statement_candidates)

def test_candidate_only_d30_and_full_determinism_counts():
    loaded,rt=runtime(); ds=docs(); orch=StatementBatchOrchestrator(rt)
    a=orch.run(ds); b=orch.run(ds); c=orch.run(list(reversed(ds)))
    assert len(ds)==30
    assert a.stable_projection_sha256==b.stable_projection_sha256==c.stable_projection_sha256==GOLDEN
    S=[];P=[];A=[];R=[]
    for _,r in a.document_results: S+=list(r.statement_candidates);P+=list(r.proposition_candidates);A+=list(r.admission_candidates);R+=list(r.relation_candidates)
    assert (len(S),len(P),len(A),len(R))==(23,27,4,96)
    assert all(s.stable_statement_id is None and not s.canonical_persistence_allowed and not s.automatic_legal_effect_allowed for s in S)
    assert all(p.stable_proposition_id is None and not p.canonical_persistence_allowed and not p.automatic_legal_effect_allowed for p in P)
    assert all(a.stable_admission_id is None and not a.canonical_assessment_creation_allowed and not a.canonical_persistence_allowed and not a.automatic_legal_effect_allowed for a in A)
    by=dict(a.document_results); d30=by[('CASE-SY-DAM-REALTY-2022-000731','D30')]
    assert not d30.statement_candidates and not d30.proposition_candidates and not d30.admission_candidates and not d30.relation_candidates

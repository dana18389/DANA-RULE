import gzip, hashlib, json, os
from pathlib import Path
import pytest
from qanun_case_runtime.evidence import EvidencePackageLoader
from qanun_case_runtime.evidence_runtime import EvidenceActivationPatch, EvidenceSandboxRuntime
from qanun_case_runtime.evidence_batch import EvidenceBatchDocument, EvidenceBatchOrchestrator
from qanun_case_runtime.governance import GovernanceRuntime

ROOT=Path(__file__).resolve().parent.parent
PATCH=ROOT/'config/evidence_runtime_activation_patch_v1.json'
ZIP_ENV='QANUN_EVIDENCE_DELIVERY_ZIP'
GOLDEN_SHA='27bb93ccd73b10aa976dddbffc9a6bb62dae7da6dd62b36c9bee994280d8d0b6'
GZ_SHA='9cf9f3c45c7709a4008214915601446945fa6f7adb951b8fc0e2d2524919ccef'
RAW_SHA='78093fae4cbba9ecef46aa2d129f9cd27f4d0c5a2870c29cb161f7c6cd2b28d8'

def runtime():
    path=os.environ.get(ZIP_ENV)
    if not path: pytest.skip(f'set {ZIP_ENV} to run EVIDENCE integration tests')
    loaded=EvidencePackageLoader(GovernanceRuntime(production_activation_allowed=False)).load(Path(path))
    patch=EvidenceActivationPatch.from_mapping(json.loads(PATCH.read_text(encoding='utf-8')))
    return loaded,EvidenceSandboxRuntime(loaded=loaded,patch=patch)

def fact_refs():
    return {
      'D02':{
        'fecand_a844ca04f52549ed17206662':{'canonical_type_id':'FACT_PAYMENT_STATUS','source_document_id':'D02','source_quote':'إيصال يدوي مؤرخ 12/4/2022: استلمت من السيد نبيل حسن المصري مبلغ تسعين مليون ليرة سورية تتمة للدفعة الثانية من ثمن المقسم /8/ موضوع عقد 12/3/2022، وبذلك يصبح مجموع المقبوض /390,000,000/ ل.س.'},
        'fecand_0d2c60398a05d5ad5b454502':{'canonical_type_id':'FACT_PAYMENT_STATUS','source_document_id':'D02','source_quote':'إشعار تحويل مصرفي رقم TRX-88219: تاريخ التنفيذ 13/04/2022، من حساب نبيل حسن المصري إلى حساب سامر فوزي العطار، القيمة /90,000,000/ ل.س، البيان: دفعة عقد شقة المزة.'},
        'no_contract_link':{'canonical_type_id':'FACT_CONTRACT_EXISTENCE','source_document_id':'D02','source_quote':'مرجع عقد فقط'}},
      'D04':{
        'fecand_09b86bce103a116b01feec95':{'canonical_type_id':'FACT_REAL_PROPERTY_REGISTRATION_STATUS','source_document_id':'D04'},
        'fecand_cd8b2097a42772380fd17554':{'canonical_type_id':'FACT_REAL_PROPERTY_ENCUMBRANCE_STATUS','source_document_id':'D04'},
        'fecand_37adfb889f075aaf6169d68e':{'canonical_type_id':'FACT_REAL_PROPERTY_ENCUMBRANCE_STATUS','source_document_id':'D04'},
        'no_ownership_link':{'canonical_type_id':'FACT_REAL_PROPERTY_OWNERSHIP_STATUS','source_document_id':'D04'}},
      'D14':{
        'fecand_d7050028cf3dc35acdb8b921':{'canonical_type_id':'FACT_REAL_PROPERTY_BOUNDARY_OR_PHYSICAL_STATUS','source_document_id':'D14'},
        'fecand_fc8585051e6748cc2026d1bd':{'canonical_type_id':'FACT_REAL_PROPERTY_POSSESSION_OR_OCCUPANCY_STATUS','source_document_id':'D14'}}}

def fixture_docs():
    p=ROOT/'tests/fixtures/evidence_golden_case_d01_d30.json.gz'; comp=p.read_bytes()
    assert hashlib.sha256(comp).hexdigest()==GZ_SHA
    raw=gzip.decompress(comp); assert hashlib.sha256(raw).hexdigest()==RAW_SHA
    rows=json.loads(raw.decode())['documents']; refs=fact_refs()
    return [EvidenceBatchDocument(r['case_scope_id'],r['document_id'],r['document_date'],r['document_type_id'],r['litigation_stage'],r['raw_text'],refs.get(r['document_id']),r.get('derived_secondary_source',False)) for r in rows]

def test_static_delivery_contract():
    loaded,rt=runtime(); r=loaded.registry_report
    assert r.valid
    assert (r.evidence_family_count,r.evidence_type_count,r.dictionary_entry_count)==(10,166,166)
    assert (r.evidence_function_count,r.challenge_type_count,r.authenticity_status_count,r.admissibility_status_count)==(28,16,17,11)
    assert (r.relation_count,r.transition_count,r.custody_event_count,r.validation_check_count,r.entity_schema_count)==(96,65,21,40,8)
    assert loaded.runtime_status=='LOADED_NOT_ACTIVATED' and rt.STATUS=='SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY'

def test_occurrence_aware_support_and_ownership_guard():
    _,rt=runtime(); run=EvidenceBatchOrchestrator(rt).run(fixture_docs()); by=dict(run.document_results)
    d02=[r for r in by['D02'].relation_candidates if r.relation_id=='EVIDENCE_SUPPORTS_FACT']
    assert len(d02)==2 and {r.target_ref for r in d02}=={'fecand_a844ca04f52549ed17206662','fecand_0d2c60398a05d5ad5b454502'}
    per_source={r.source_ref:set() for r in d02}
    for r in d02: per_source[r.source_ref].add(r.target_ref)
    assert all(len(x)==1 for x in per_source.values())
    d04=[r for r in by['D04'].relation_candidates if r.relation_id=='EVIDENCE_SUPPORTS_FACT']
    assert {r.target_ref for r in d04}=={'fecand_09b86bce103a116b01feec95','fecand_cd8b2097a42772380fd17554','fecand_37adfb889f075aaf6169d68e'}
    assert 'no_ownership_link' not in {r.target_ref for r in d04}

def test_truth_digital_reference_and_chain_guards():
    _,rt=runtime(); by=dict(EvidenceBatchOrchestrator(rt).run(fixture_docs()).document_results)
    digital=next(c for c in by['D02'].candidates if c.canonical_type_id=='EVI_ELECTRONIC_TRANSFER_RECORD')
    assert digital.authenticity_status=='EVAU_UNRESOLVED' and digital.admissibility_status=='EVAD_UNRESOLVED' and digital.probative_status=='EVPA_UNRESOLVED'
    assert {'DIGITAL_FORMAT_DOES_NOT_PROVE_AUTHENTICITY','NO_FORMAL_DIGITAL_CHAIN_LOG_ASSUMED','SUPPORT_DOES_NOT_EQUAL_FACT_TRUTH'}<=set(digital.blockers)
    assert all(c.record_kind=='EVIDENCE_REFERENCE' for c in by['D12'].candidates)
    assert all(r.relation_id!='COURT_RELIED_ON_EVIDENCE' for r in by['D18'].relation_candidates)
    assert 'HISTORICAL_REFERENCE_NOT_NEW_PAYMENT_EVIDENCE_ITEM' in by['D20'].candidates[0].blockers
    assert not by['D30'].candidates

def test_candidate_only_and_source_activation_boundary():
    loaded,rt=runtime(); run=EvidenceBatchOrchestrator(rt).run(fixture_docs())
    for _,res in run.document_results:
      for c in res.candidates:
        assert c.stable_instance_id is None and not c.canonical_persistence_allowed and not c.automatic_legal_effect_allowed
        assert not c.automatic_admissibility_decision_allowed and not c.automatic_probative_value_decision_allowed
      for r in res.relation_candidates:
        assert not r.user_verified and not r.canonical_persistence_allowed and not r.automatic_legal_effect_allowed
    assert loaded.registry.package['governance']['runtime_activation']=='NOT_RUNTIME_ACTIVATED'
    assert loaded.registry.package['governance']['sandbox_activation']=='BLOCKED_PENDING_RUNTIME_VALIDATION'
    assert rt.patch.sandbox_runtime_enabled and not rt.patch.production_activation_allowed

def test_full_d01_d30_golden_determinism_scope_and_counts():
    _,rt=runtime(); docs=fixture_docs(); orch=EvidenceBatchOrchestrator(rt)
    a=orch.run(docs); b=orch.run(docs); c=orch.run(list(reversed(docs))); by=dict(a.document_results)
    assert len(docs)==30 and a.stable_projection_sha256==b.stable_projection_sha256==c.stable_projection_sha256==GOLDEN_SHA
    cs=[x for _,r in a.document_results for x in r.candidates]; rs=[x for _,r in a.document_results for x in r.relation_candidates]
    assert (len(cs),sum(x.record_kind=='EVIDENCE_ITEM' for x in cs),sum(x.record_kind=='EVIDENCE_REFERENCE' for x in cs),len(rs))==(37,20,17,44)
    assert sum(x.relation_id=='EVIDENCE_SUPPORTS_FACT' for x in rs)==7
    assert len(by['D24'].candidates)==5 and all(x.case_id.endswith('::JUDICIAL_LIABILITY') for x in by['D24'].candidates)
    assert {x.occurrence_key for x in by['D24'].candidates if x.canonical_type_id=='EVT_COURT_DECISION_DOCUMENT'}=={'CASSATION_DECISION_ATTACHMENT','APPELLATE_JUDGMENT_ATTACHMENT'}
    assert not by['D30'].candidates

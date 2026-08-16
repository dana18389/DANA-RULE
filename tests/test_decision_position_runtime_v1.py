import os,json,gzip,hashlib
from pathlib import Path
import pytest

from qanun_case_runtime.decision_position import DecisionPositionPackageLoader, DecisionPositionPackageError
from qanun_case_runtime.decision_position_runtime import DecisionPositionSandboxRuntime
from qanun_case_runtime.decision_position_batch import DecisionBatchDocument, DecisionPositionBatchOrchestrator

ROOT=Path(__file__).resolve().parent.parent
PATCH=ROOT/'config/decision_position_runtime_activation_patch_v1.json'
FIX=ROOT/'tests/fixtures/statement_golden_case_d01_d30.json.gz'
PKG_ENV='QANUN_DECISION_POSITION_PACKAGE_JSON'
REPORT_ENV='QANUN_DECISION_POSITION_REPORT_MD'

@pytest.fixture(scope='module')
def env():
    pkg=os.environ.get(PKG_ENV)
    rep=os.environ.get(REPORT_ENV)
    if not pkg or not rep:
        pytest.skip(f'set {PKG_ENV} and {REPORT_ENV}')
    loaded=DecisionPositionPackageLoader().load(pkg,rep)
    patch=json.loads(PATCH.read_text(encoding='utf-8'))
    return loaded,DecisionPositionSandboxRuntime(loaded,patch)

def _golden(rt):
    d=json.loads(gzip.decompress(FIX.read_bytes()))
    rows=[]; counts={'decisions':0,'dispositions':0,'positions':0,'reasoning':0,'relations':0}; per={}
    for x in d['documents']:
        r=rt.extract(case_id=d['case_id'],source_document_id=x['document_id'],
                     document_type_id=x['document_type_id'],litigation_stage=x['litigation_stage'],
                     raw_text=x['raw_text'],derived_secondary_source=x.get('derived_secondary_source',False))
        per[x['document_id']]=r
        rows.append((x['document_id'],r.stable_projection_sha256))
        counts['decisions']+=len(r.decision_candidates)
        counts['dispositions']+=len(r.disposition_candidates)
        counts['positions']+=len(r.court_position_candidates)
        counts['reasoning']+=len(r.reasoning_candidates)
        counts['relations']+=len(r.relation_candidates)
    payload={'rows':rows,'counts':counts}
    h=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return h,counts,per

def test_source_integrity_and_static_37(env):
    loaded,_=env
    s=loaded.validation['summary']
    assert loaded.package['status']=='PRODUCTION_CANDIDATE_NOT_FROZEN'
    assert s['validation_checks_total']==37 and s['validation_checks_passed']==37
    assert s['validation_checks_needing_revision']==0
    assert loaded.validation['runtime_validation_status']=='NOT_RUN_RUNTIME_UNAVAILABLE'
    assert loaded.validation['activation_status']=='BLOCKED_PENDING_SANDBOX_RUNTIME_VALIDATION'
    assert len(loaded.registry.decision_type_ids)==202
    assert len(loaded.registry.court_position_type_ids)==76
    assert len(loaded.registry.disposition_type_ids)==28
    assert len(loaded.registry.relation_ids)==104
    assert len(loaded.registry.dictionary_by_type)==278

def test_party_argument_caption_and_quote_do_not_create_current_decision(env):
    _,rt=env
    cases=[
        ('APPEAL_PETITION','يلتمس المستأنف فسخ الحكم ورد الدعوى موضوعاً.'),
        ('GENERIC_DOCUMENT','طلب على عريضة لإصدار أمر على عريضة.'),
        ('CASSATION_DECISION','ورد في قرار سابق أن المحكمة حكمت بتثبيت البيع، دون أن يصدر في الوثيقة الحالية حكم.'),
        ('DETENTION_WARRANT_DOCUMENT','مذكرة توقيف رقم 12/2025 صادرة كوثيقة تنفيذية فقط.')
    ]
    for i,(dtype,text) in enumerate(cases):
        r=rt.extract(case_id='X',source_document_id=f'N{i}',document_type_id=dtype,litigation_stage='TEST',raw_text=text)
        assert r.decision_candidates==()
        assert r.disposition_candidates==()
        assert r.court_position_candidates==()

def test_atomic_golden_decisions_and_appeal_semantics(env):
    _,rt=env
    h,counts,per=_golden(rt)
    for did in ['D06','D12','D18','D21','D23','D26','D28']:
        assert per[did].decision_candidates, did
    for did in ['D05','D08','D09','D19','D20','D22','D24','D25','D27','D30']:
        assert per[did].decision_candidates==(), did
    d06=[x.decision_type_id for x in per['D06'].decision_candidates if x.decision_type_id]
    assert d06.count('DT_ANNOTATION_PLACED')==1
    d12=[x.decision_type_id for x in per['D12'].decision_candidates if x.decision_type_id]
    assert d12.count('DT_EXPERT_APPOINTED')==1
    d26={x.decision_type_id for x in per['D26'].decision_candidates if x.decision_type_id}
    assert {'DT_CASE_FORMALLY_ACCEPTED','DT_INTERIM_ENFORCEMENT_STAY_REJECTED'} <= d26
    d18={x.decision_type_id for x in per['D18'].decision_candidates if x.decision_type_id}
    assert 'DT_SALE_CONFIRMED' in d18
    assert 'DT_NON_EFFECTIVENESS_DECLARED' in d18
    assert 'DT_COMPENSATION_AWARDED' in d18
    assert 'DT_MULTI_ITEM_CIVIL_JUDGMENT' not in d18
    assert len(per['D18'].disposition_candidates)>=4
    d21={x.decision_type_id for x in per['D21'].decision_candidates if x.decision_type_id}
    assert 'DT_APPEAL_FORMALLY_ACCEPTED' in d21
    assert 'DT_PRIOR_DECISION_REVERSED' in d21
    assert 'DT_CASE_REJECTED_ON_MERITS' in d21
    d23={x.decision_type_id for x in per['D23'].decision_candidates if x.decision_type_id}
    assert 'DT_APPEAL_REJECTED_ON_MERITS' in d23
    assert 'DT_APPEAL_FORMALLY_ACCEPTED' not in d23
    assert counts['decisions']>7 and counts['dispositions']>=8
    assert h

def test_reasoning_boundaries_no_prior_court_adoption(env):
    _,rt=env
    _,_,per=_golden(rt)
    d18={p.position_type_id for p in per['D18'].court_position_candidates}
    assert 'POS_FACT_FOUND' in d18
    assert 'POS_EVIDENCE_RELIED_ON' in d18
    d21={p.position_type_id for p in per['D21'].court_position_candidates}
    assert 'POS_EVIDENCE_PARTIALLY_RELIED_ON' in d21
    d23={p.position_type_id for p in per['D23'].court_position_candidates}
    assert 'POS_FACT_FOUND' not in d23
    assert 'POS_EVIDENCE_RELIED_ON' not in d23
    assert any(r.reasoning_kind=='PRIOR_DECISION_REASONING_RECITED' for r in per['D23'].reasoning_candidates)

def test_finality_notification_and_silence_guards(env):
    _,rt=env
    _,_,per=_golden(rt)
    sig=set(per['D18'].semantic_signals)
    assert 'FINALITY_CONDITION_TEXT_PRESENT_NOT_CURRENT_FINALITY' in sig
    prohibited=rt.PROHIBITED_SIGNALS
    for r in per.values():
        assert not (set(r.semantic_signals)&prohibited)
    for r in per.values():
        for c in r.decision_candidates:
            assert c.automatic_legal_effect_allowed is False
            assert c.canonical_persistence_allowed is False
            assert c.stable_decision_id is None

def test_same_input_determinism_and_order_independence(env):
    _,rt=env
    a=_golden(rt)[0]; b=_golden(rt)[0]
    assert a==b
    data=json.loads(gzip.decompress(FIX.read_bytes()))
    docs=list(reversed(data['documents']))
    rows=[]
    for x in docs:
        r=rt.extract(case_id=data['case_id'],source_document_id=x['document_id'],
                     document_type_id=x['document_type_id'],litigation_stage=x['litigation_stage'],
                     raw_text=x['raw_text'],derived_secondary_source=x.get('derived_secondary_source',False))
        rows.append((x['document_id'],r.stable_projection_sha256))
    normal={did:r.stable_projection_sha256 for did,r in _golden(rt)[2].items()}
    assert {did:h for did,h in rows}==normal

def test_batch_composite_key_isolation(env):
    _,rt=env
    orch=DecisionPositionBatchOrchestrator(rt)
    text='تقرر: 1- رد دعوى المدعي موضوعاً.'
    docs=[DecisionBatchDocument('scope-A','case-A','D1','JUDGMENT','FIRST',text),DecisionBatchDocument('scope-B','case-B','D1','JUDGMENT','FIRST',text)]
    out=orch.run(docs)
    assert len(out.results)==2
    assert out.result_for('scope-A','D1')
    with pytest.raises(ValueError):
        orch.run([docs[0],docs[0]])

def test_provenance_quote_is_literal_and_page_not_invented(env):
    _,rt=env
    data=json.loads(gzip.decompress(FIX.read_bytes()))
    raw_by_id={x['document_id']:x['raw_text'] for x in data['documents']}
    _,_,per=_golden(rt)
    for did,r in per.items():
        raw=raw_by_id[did]
        for c in list(r.decision_candidates)+list(r.disposition_candidates)+list(r.court_position_candidates)+list(r.reasoning_candidates):
            assert c.source_quote in raw
            assert c.source_page is None
            assert c.locator_status=='UNRESOLVED_SOURCE_PAGE'

def test_activation_pins_reject_modified_package_hash(env,tmp_path):
    loaded,_=env
    patch=json.loads(PATCH.read_text(encoding='utf-8'))
    bad=dict(patch); bad['target_package_sha256']='0'*64
    with pytest.raises(DecisionPositionPackageError):
        DecisionPositionSandboxRuntime(loaded,bad)

import gzip,json,hashlib,os
from pathlib import Path
import pytest
from qanun_case_runtime.procedure_hearing import ProcedureHearingPackageLoader,ProcedureHearingPackageError
from qanun_case_runtime.procedure_hearing_runtime import ProcedureHearingSandboxRuntime

ROOT=Path(__file__).resolve().parent.parent
PATCH=ROOT/'config/procedure_hearing_runtime_activation_patch_v1.json'
FIX=ROOT/'tests/fixtures/statement_golden_case_d01_d30.json.gz'
ZIP_ENV='QANUN_PROCEDURE_HEARING_DELIVERY_ZIP'
GOLDEN='b318be69b7cfcc5d9ee07112a3e25e1cdd6c9305dd16a89fab24035bbf2f3d18'
PROHIBITED={
'VALID_SERVICE_INFERRED_FROM_MINUTE','FINAL_ABSENCE_EFFECT','PARTY_PERSONAL_APPEARANCE',
'COURT_ACCEPTANCE','EXPERT_APPOINTMENT_EXECUTED','UNIVERSAL_PUBLIC_ORDER_RULE',
'UNIVERSAL_RAISE_AT_ANY_STAGE','AUTOMATIC_INTERRUPTION','LEGAL_DEADLINE_CALCULATED_HERE',
'EXECUTION_INFERRED','AUTHENTICITY_VERIFIED','FACT_PROVEN','COURT_ADOPTS_REPORT',
'JUDGMENT_ISSUED','JUDGMENT_FINAL','JUDGMENT_NOTIFIED','VALID_NOTIFICATION',
'APPEAL_DEADLINE_STARTED_AUTOMATICALLY','MERITS_JURISDICTION_INFERRED',
'EXECUTION_PRESIDENT_JURISDICTION_INFERRED','FULL_OBLIGATION_EXTINGUISHMENT',
'ALL_DEBT_AND_SECURITY_RIGHTS_EXTINGUISHED','AWARD_ISSUANCE_EQUALS_ENFORCEMENT',
'CURRENT_HEARING_OR_PROCEDURE_EVENT','STATEMENT_CONTENT_STORED_AS_PROCEDURE_ONLY',
'UNSCOPED_SUBSTANTIVE_WAIVER'}

@pytest.fixture(scope='module')
def env():
    p=os.environ.get(ZIP_ENV)
    if not p: pytest.skip(f'set {ZIP_ENV}')
    loaded=ProcedureHearingPackageLoader().load(p)
    patch=json.loads(PATCH.read_text(encoding='utf-8'))
    return loaded,ProcedureHearingSandboxRuntime(loaded,patch)

def test_source_hashes_and_static_55(env):
    loaded,_=env
    assert loaded.validation['summary']['static_legal_rebuild_pass_count']==55
    assert loaded.validation['summary']['static_legal_rebuild_failure_count']==0
    assert loaded.cross_index_specs['case_count']==18
    assert loaded.manifest['production_eligible'] is False

def test_cross_index_18_executed_and_boundaries(env):
    loaded,rt=env
    for case in loaded.cross_index_specs['cases']:
        r=rt.extract(case_id='XI',source_document_id=case['test_id'],document_type_id='SYNTHETIC',litigation_stage='TEST',raw_text=case['scenario_ar'])
        got={s.signal_code for s in r.signals}
        assert set(case['expected']) <= got, (case['test_id'],case['expected'],got)
        assert not (set(case['prohibited']) & got)
        assert not (PROHIBITED & got)
        assert all(c.canonical_persistence_allowed is False and c.automatic_legal_effect_allowed is False for c in r.candidates)

def _golden(rt):
    d=json.loads(gzip.decompress(FIX.read_bytes()))
    rows=[]; kc={}; sc={}; per={}
    for x in d['documents']:
        r=rt.extract(case_id=d['case_id'],source_document_id=x['document_id'],document_type_id=x['document_type_id'],litigation_stage=x['litigation_stage'],raw_text=x['raw_text'],derived_secondary_source=x.get('derived_secondary_source',False))
        rows.append((x['document_id'],r.stable_projection_sha256)); per[x['document_id']]=r
        for c in r.candidates: kc[c.entity_kind]=kc.get(c.entity_kind,0)+1
        for s in r.signals: sc[s.signal_code]=sc.get(s.signal_code,0)+1
    payload={'rows':rows,'kind_counts':dict(sorted(kc.items())),'signal_counts':dict(sorted(sc.items()))}
    h=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return h,per,kc,sc

def test_golden_d01_d30_and_derived_summary_zero(env):
    _,rt=env
    h,per,kc,sc=_golden(rt)
    assert h==GOLDEN
    assert len(per)==30
    assert per['D30'].candidates==()
    assert per['D30'].signals==()
    assert kc['PROCEDURAL_ACTION_EVENT']>=1
    assert sc['HEARING_OCCURRENCE']>=1

def test_determinism(env):
    _,rt=env
    a=_golden(rt)[0]; b=_golden(rt)[0]
    assert a==b==GOLDEN

def test_scheduled_never_occurrence_without_occurrence_source(env):
    _,rt=env
    r=rt.extract(case_id='X',source_document_id='S1',document_type_id='NOTICE',litigation_stage='FIRST',raw_text='تقرر تحديد موعد جلسة بتاريخ 21/06/2022.')
    kinds={c.entity_kind for c in r.candidates}
    assert 'SCHEDULED_HEARING' in kinds
    assert 'HEARING_OCCURRENCE' not in kinds

def test_representative_never_personal_appearance_and_deadline_candidate_not_legal(env):
    _,rt=env
    r=rt.extract(case_id='X',source_document_id='S2',document_type_id='MINUTE',litigation_stage='FIRST',raw_text='حضر وكيل المدعي المحامي عادل. وقررت المحكمة تكليفه بتقديم مستند خلال مدة خمسة أيام.')
    got={s.signal_code for s in r.signals}
    assert 'LAWYER_APPEARANCE' in got and 'REPRESENTED_PARTY_LINK' in got
    assert 'PARTY_PERSONAL_APPEARANCE' not in got
    assert 'DEADLINE_CANDIDATE' in got
    assert 'LEGAL_DEADLINE_CALCULATED_HERE' not in got

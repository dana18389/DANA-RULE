import os, json, zipfile, pathlib, gzip
import pytest
from qanun_case_runtime.governance import GovernanceRuntime
from qanun_case_runtime.asset_amount import AssetAmountPackageLoader, AssetAmountPackageError
from qanun_case_runtime.asset_amount_runtime import AssetAmountSandboxRuntime

ZIP_ENV='QANUN_ASSET_AMOUNT_DELIVERY_ZIP'
ZIP=os.environ.get(ZIP_ENV)
STATEMENT_PROJ='b88eb1a62e6ded8aad57bc78c614655b296bdc8caa56f36f2d18fe21ac3a9b11'

def runtime():
    if not ZIP: pytest.skip(f'set {ZIP_ENV}')
    loaded=AssetAmountPackageLoader(GovernanceRuntime(False)).load(ZIP)
    return loaded,AssetAmountSandboxRuntime(loaded,STATEMENT_PROJ)

def test_01_source_manifest_and_registry():
    loaded,rt=runtime()
    assert loaded.delivery_zip_sha256=='975341a698c86dde58978a190d99487cc1b5951ab9aa7ce03a9e311c9c7f19a9'
    assert loaded.package_sha256=='298b39d5e372c0308189279250c69b51a97105486c763b46426db142f73dfeb0'
    assert loaded.validation['summary']['static_governance_pass_count']==64
    assert loaded.validation['summary']['static_governance_failure_count']==0
    assert loaded.registry.dictionary_entry_count==281
    assert len(loaded.registry.relation_ids)==190
    assert loaded.registry.unresolved_extensions==('PRIVILEGE_AS_SECURITY_RIGHT',)

def test_02_candidate_only_and_exact_amount():
    _,rt=runtime(); out=rt.extract(case_id='C',source_document_id='D',raw_text='يطالب المدعي بمبلغ 10,000,000 ل.س')
    vals=[x for x in out.candidates if x.entity_kind=='MONETARY_VALUE']
    assert any(x.amount_decimal_string=='10000000' and x.currency_code=='SYP' for x in vals)
    assert any(x.entity_kind=='FINANCIAL_REQUEST' for x in out.candidates)
    assert all(not x.canonical_persistence_allowed and not x.automatic_legal_effect_allowed and x.stable_id is None for x in out.candidates)

def test_03_source_acceptance_35_primary_semantics():
    loaded,rt=runtime(); cases=loaded.package['runtime_v1_2']['modules']['test_cases']['test_cases']
    assert len(cases)==35
    nonempty=0
    for tc in cases:
        out=rt.extract(case_id='ACCEPT',source_document_id=tc['test_id'],raw_text=tc['input_text'])
        if out.candidates or out.guard_signals: nonempty+=1
        expected={e.get('entity_type') for e in tc.get('expected_entities',[])}
        kinds={x.entity_kind for x in out.candidates}
        if 'MONETARY_EXPRESSION' in expected: assert 'MONETARY_EXPRESSION' in kinds, tc['test_id']
        if 'MONETARY_VALUE' in expected and any(ch.isdigit() for ch in tc['input_text']): assert 'MONETARY_VALUE' in kinds, tc['test_id']
        if 'FINANCIAL_REQUEST' in expected: assert 'FINANCIAL_REQUEST' in kinds, tc['test_id']
        if 'ASSET_MENTION' in expected: assert 'ASSET_MENTION' in kinds, tc['test_id']
        if 'VALUATION_ASSESSMENT' in expected: assert 'VALUATION_ASSESSMENT' in kinds, tc['test_id']
        if 'COURT_POSITION' in expected and tc['test_id'] in {'AA-TC-025','AA-TC-026','AA-TC-034'}: assert 'COURT_POSITION' in kinds, tc['test_id']
    assert nonempty>=33

def test_04_cross_index_14_prohibited_inferences_absent():
    loaded,rt=runtime(); cases=loaded.cross_index_specs['cases']; assert len(cases)==14
    prohibited_global={
      'OWNERSHIP_ESTABLISHED_FROM_POSSESSION','DEBT_IMPLIES_VALID_ENFORCEABLE_SECURITY','ENFORCEABLE_IMPLIES_PRIORITY_CORRECT',
      'FULL_PERFORMANCE','OBLIGATION_EXTINGUISHED','FULL_SATISFACTION','UNDERLYING_DEBT_AUTOMATICALLY_EXTINGUISHED',
      'PAYMENT_COURT_ESTABLISHED','COURT_ADOPTS_ALL_EXPERT_VALUES','COURT_AWARDS_AMOUNT','FINAL_INTEREST_AMOUNT',
      'RESOLVED_CURRENCY_CONVERSION','LOAN_OBLIGATION_EXTINGUISHED','SILENT_STATE_COURT_FINANCIAL_POSITION','AWARD_EQUALS_ENFORCEMENT'}
    for tc in cases:
        out=rt.extract(case_id='XI',source_document_id=tc['test_id'],raw_text=tc['scenario_ar'])
        assert prohibited_global.isdisjoint(set(out.guard_signals)), tc['test_id']
        assert set(tc['prohibited']).isdisjoint(set(out.guard_signals)), tc['test_id']
    signals={tc['test_id']:set(rt.extract(case_id='XI',source_document_id=tc['test_id'],raw_text=tc['scenario_ar']).guard_signals) for tc in cases}
    assert {'IN_POSSESSION','OWNERSHIP_CLAIMED'} <= signals['AA-XI-001']
    assert 'SECURITY_CANDIDATE_WITH_UNRESOLVED_DIMENSIONS' in signals['AA-XI-002']
    assert {'PAYMENT_ASSERTION_OR_EVENT','PAYMENT_CAUSE_DISPUTED'} <= signals['AA-XI-004']
    assert 'PARTIAL_PAYMENT' in signals['AA-XI-005']
    assert 'PAYMENT_EVIDENCE_SUPPORT_ONLY' in signals['AA-XI-007']
    assert 'REQUESTED_AMOUNT_OR_NARRATION_ONLY' in signals['AA-XI-009']
    assert 'DERIVATION_BLOCKED_PENDING_CURRENT_LAW_VALIDITY' in signals['AA-XI-010']
    assert 'AMOUNT_EQUIVALENCE_CANDIDATE' in signals['AA-XI-011']
    assert {'PARTIAL_COLLECTION','OUTSTANDING_BALANCE'} <= signals['AA-XI-012']
    assert {'RECEIPT_EVENT_OR_PROPOSITION','PAYMENT_CAUSE_SEPARATE'} <= signals['AA-XI-013']
    assert {'ARBITRAL_AMOUNT_CONTEXT','ENFORCEMENT_CONTEXT_SEPARATE'} <= signals['AA-XI-014']

def test_05_payment_evidence_and_admission_do_not_prove_extinguishment():
    _,rt=runtime()
    for txt in ['شيك بمبلغ 5,000 دولار لم يثبت صرفه','أقر بقبض مبلغ لكنه بدل أجرة لا وفاء قرض','حوالة 50 مليون مع نزاع بأنها لمعاملة أخرى']:
        out=rt.extract(case_id='C',source_document_id='D',raw_text=txt)
        assert 'FULL_PERFORMANCE' not in out.guard_signals
        assert 'OBLIGATION_EXTINGUISHED' not in out.guard_signals
        assert 'LOAN_OBLIGATION_EXTINGUISHED' not in out.guard_signals

def test_06_court_narration_not_award_and_expert_not_court_value():
    _,rt=runtime()
    a=rt.extract(case_id='C',source_document_id='N',raw_text='وعرضت المحكمة أن المدعي طلب مبلغ 7,000,000 ل.س')
    assert not any(x.entity_kind=='COURT_POSITION' for x in a.candidates)
    b=rt.extract(case_id='C',source_document_id='E',raw_text='خلص الخبير إلى أن قيمة العقار السوقية 120,000,000 ل.س')
    assert any(x.entity_kind=='VALUATION_ASSESSMENT' for x in b.candidates)
    assert not any(x.entity_kind=='COURT_POSITION' for x in b.candidates)

def test_07_d01_d30_golden_determinism_and_boundaries():
    _,rt=runtime(); root=pathlib.Path(__file__).parent/'fixtures/statement_golden_case_d01_d30.json.gz'
    bundle=json.loads(gzip.decompress(root.read_bytes())); docs=bundle['documents']; assert len(docs)==30
    def run(seq):
        rows=[]
        for d in seq:
            o=rt.extract(case_id=bundle['case_id'],source_document_id=d['document_id'],raw_text=d['raw_text'],derived_secondary_source=d.get('derived_secondary_source',False))
            rows.append((d['document_id'],o.projection_sha256,len(o.candidates),len(o.relations),o.guard_signals))
        return sorted(rows)
    a=run(docs); b=run(docs); c=run(list(reversed(docs)))
    assert a==b==c
    by={x[0]:x for x in a}
    assert 'PAYMENT_ASSERTION_OR_EVENT' in by['D02'][4]
    assert 'OBLIGATION_EXTINGUISHED' not in by['D02'][4]
    assert 'COURT_AWARDS_AMOUNT_EXPLICIT' not in by['D03'][4]
    assert by['D30'][2]==0

def test_08_wrong_upstream_projection_rejected():
    if not ZIP: pytest.skip(f'set {ZIP_ENV}')
    loaded=AssetAmountPackageLoader(GovernanceRuntime(False)).load(ZIP)
    with pytest.raises(AssetAmountPackageError): AssetAmountSandboxRuntime(loaded,'bad')

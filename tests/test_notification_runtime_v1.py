import gzip,json,hashlib,os,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"src"))
from qanun_case_runtime.notification import NotificationPackageLoader,NotificationPackageError
from qanun_case_runtime.notification_runtime import NotificationActivationPatch,NotificationSandboxRuntime
from qanun_case_runtime.notification_batch import NotificationBatchDocument,NotificationBatchOrchestrator

PATCH=ROOT/"config/notification_runtime_activation_patch_v1.json"
FIX=ROOT/"tests/fixtures/statement_golden_case_d01_d30.json.gz"
ZIP_ENV="QANUN_NOTIFICATION_DELIVERY_ZIP"

@pytest.fixture(scope="module")
def env():
    p=os.environ.get(ZIP_ENV)
    if not p: pytest.skip(f"set {ZIP_ENV}")
    loaded=NotificationPackageLoader().load(p)
    patch=NotificationActivationPatch.from_mapping(json.loads(PATCH.read_text(encoding="utf-8")))
    return loaded,NotificationSandboxRuntime(loaded,patch)

def test_source_hashes_static_and_gates(env):
    loaded,_=env
    s=loaded.validation["summary"]
    assert s["new_static_check_count"]==77
    assert s["new_static_pass_count"]==77
    assert s["new_static_failure_count"]==0
    assert loaded.cross_index_specs["case_count"]==28
    assert loaded.manifest["sandbox_activation_allowed"] is False
    assert loaded.manifest["production_eligible"] is False

def test_cross_index_28_executed(env):
    loaded,rt=env
    for case in loaded.cross_index_specs["cases"]:
        r=rt.extract(case_id="XI",source_document_id=case["test_id"],document_type_id="SYNTHETIC",litigation_stage="TEST",raw_text=case["scenario_ar"])
        got={s.signal_code for s in r.signals}
        assert set(case["expected"]) <= got, (case["test_id"],case["expected"],got)
        assert not (set(case["prohibited"]) & got), (case["test_id"],case["prohibited"],got)
        assert not (rt.FORBIDDEN_SIGNALS & got)
        assert all(c.stable_instance_id is None and not c.canonical_persistence_allowed and not c.automatic_legal_effect_allowed for c in r.candidates)

def _golden(rt):
    d=json.loads(gzip.decompress(FIX.read_bytes())); rows=[]; kinds={}; signals={}; per={}
    for x in d["documents"]:
        r=rt.extract(case_id=d["case_id"],source_document_id=x["document_id"],document_type_id=x["document_type_id"],litigation_stage=x["litigation_stage"],raw_text=x["raw_text"],derived_secondary_source=x.get("derived_secondary_source",False))
        per[x["document_id"]]=r; rows.append((x["document_id"],r.stable_projection_sha256))
        for c in r.candidates: kinds[c.entity_kind]=kinds.get(c.entity_kind,0)+1
        for s in r.signals: signals[s.signal_code]=signals.get(s.signal_code,0)+1
    payload={"rows":rows,"kind_counts":dict(sorted(kinds.items())),"signal_counts":dict(sorted(signals.items()))}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest(),per,kinds,signals

def test_golden_d01_d30_boundaries(env):
    _,rt=env; _,per,_,signals=_golden(rt)
    assert len(per)==30 and per["D30"].candidates==() and per["D30"].signals==()
    d7=per["D07"]
    assert sum(c.entity_kind=="ServiceAttempt" for c in d7.candidates)==2
    assert sum(c.entity_kind=="ServiceEvent" for c in d7.candidates)==1
    assert not any(c.entity_kind=="ServiceAssessment" for c in per["D08"].candidates)
    assert not any(c.entity_kind=="ServiceAssessment" for c in per["D09"].candidates)
    assert any(c.notification_type_id=="NT_PRE_NOTARIAL_NOTICE" for c in per["D03"].candidates)
    assert not any(c.entity_kind=="ServiceEvent" for c in per["D03"].candidates)
    assert any(c.entity_kind=="Notification" and c.notification_type_id=="NT_PRE_PAYMENT_DEMAND" for c in per["D29"].candidates)
    assert not any(c.entity_kind=="ServiceEvent" for c in per["D29"].candidates)
    assert not (rt.FORBIDDEN_SIGNALS & set(signals))

def test_same_input_determinism(env):
    _,rt=env; assert _golden(rt)[0]==_golden(rt)[0]

def test_order_package_dispatch_attempt_service_separated(env):
    _,rt=env
    samples=[("O","قررت المحكمة تنظيم ورقة تبليغ للخصم.",{"NotificationOrder"}),("P","أرسلت حزمة أوراق تبليغ إلى الجهة المنفذة دون ورود نتيجة بعد.",{"Notification","NotificationPackage"}),("A","المحاولة الأولى: انتقل المحضر ولم يجد المطلوب.",{"Notification","ServiceAttempt"}),("E","المحاولة الأولى: جرى التبليغ إلى المطلوب بالذات.",{"Notification","ServiceAttempt","ServiceEvent"})]
    for doc,text,expected in samples:
        r=rt.extract(case_id="X",source_document_id=doc,document_type_id="TEST",litigation_stage="FIRST",raw_text=text)
        assert expected <= {c.entity_kind for c in r.candidates}

def test_deadline_never_calculated_here(env):
    _,rt=env; r=rt.extract(case_id="X",source_document_id="DL",document_type_id="TEST",litigation_stage="FIRST",raw_text="Service Event متحقق وتاريخ دوره محدد وقاعدة مهلة محلولة.")
    got={s.signal_code for s in r.signals}; assert "DEADLINE_CANDIDATE_HANDOFF" in got and "DEADLINE_CALCULATED_BY_NOTIFICATION_INDEX" not in got

def test_explicit_court_assessment_scope_only(env):
    _,rt=env; r=rt.extract(case_id="X",source_document_id="C",document_type_id="DECISION",litigation_stage="FIRST",raw_text="قررت المحكمة صراحة بطلان التبليغ في هذه المحاولة.")
    assert any(c.entity_kind=="ServiceAssessment" for c in r.candidates)
    got={s.signal_code for s in r.signals}; assert "COURT_EXPRESSLY_FOUND_NOTIFICATION_INVALID" in got and "GENERALIZE_INVALIDITY_TO_OTHER_ATTEMPTS" not in got

def test_batch_composite_identity_and_case_isolation(env):
    _,rt=env; b=NotificationBatchOrchestrator(rt)
    docs=[NotificationBatchDocument("CASE-A","D7","SERVICE_OF_PROCESS_PACKAGE","FIRST","المحاولة الأولى: انتقل المحضر ولم يجد المطلوب."),NotificationBatchDocument("CASE-B","D7","SERVICE_OF_PROCESS_PACKAGE","FIRST","المحاولة الأولى: جرى التبليغ إلى المطلوب بالذات.")]
    out=b.run(docs); assert len(out.items)==2
    assert out.result_for("CASE-A","D7").stable_projection_sha256 != out.result_for("CASE-B","D7").stable_projection_sha256
    with pytest.raises(ValueError): b.run([docs[0],docs[0]])

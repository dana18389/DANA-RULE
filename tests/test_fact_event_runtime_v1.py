import json
import os
from pathlib import Path

import pytest

from qanun_case_runtime.fact_event import FactEventPackageLoader
from qanun_case_runtime.fact_event_runtime import FactEventActivationPatch, FactEventSandboxRuntime
from qanun_case_runtime.fact_event_batch import FactEventBatchDocument, FactEventBatchOrchestrator
from qanun_case_runtime.governance import GovernanceRuntime


ZIP_ENV = "QANUN_FACT_EVENT_DELIVERY_ZIP"
ROOT = Path(__file__).resolve().parent.parent
PATCH = ROOT / "config" / "fact_event_runtime_activation_patch_v1.json"


def runtime():
    path = os.environ.get(ZIP_ENV)
    if not path:
        pytest.skip(f"set {ZIP_ENV} to run FACT_EVENT integration tests")
    loaded = FactEventPackageLoader(GovernanceRuntime(production_activation_allowed=False)).load(path)
    patch = FactEventActivationPatch.from_mapping(json.loads(PATCH.read_text(encoding="utf-8")))
    return loaded, FactEventSandboxRuntime(loaded=loaded, patch=patch)


def doc(doc_id, date, type_id, stage, text, *, scope="CASE-SY-DAM-REALTY-2022-000731",
        holder=None, derived=False):
    return FactEventBatchDocument(
        case_scope_id=scope, document_id=doc_id, document_date=date,
        document_type_id=type_id, litigation_stage=stage, raw_text=text,
        assertion_holder_candidate_ref=holder, derived_secondary_source=derived,
    )


def critical_docs():
    return [
        doc("D02","2022-04-12","PAYMENT_RECEIPT_AND_BANK_TRANSFER","PRE_LITIGATION",
            "إيصال يدوي مؤرخ 12/4/2022: استلمت من السيد نبيل حسن المصري مبلغ تسعين مليون ليرة سورية تتمة للدفعة الثانية من ثمن المقسم /8/ موضوع عقد 12/3/2022، وبذلك يصبح مجموع المقبوض /390,000,000/ ل.س. المقر بما فيه: سامر العطار.\nإشعار تحويل مصرفي رقم TRX-88219: تاريخ التنفيذ 13/04/2022، من حساب نبيل حسن المصري إلى حساب سامر فوزي العطار، القيمة /90,000,000/ ل.س، البيان: دفعة عقد شقة المزة."),
        doc("D04","2022-05-18","EXTRACT_RECORD_CADASTRAL","PRE_LITIGATION",
            "أمانة السجل العقاري بالمزة — إخراج قيد للعقار /3487/12/ منطقة المزة العقارية. المالك على القيد بتاريخ الإصدار: سامر فوزي العطار، /360/ سهماً من أصل /2400/ سهم، مرتبطة بالمقسم /8/. الإشارات: لا توجد إشارة دعوى حتى تاريخ 18/05/2022. يوجد تأمين من الدرجة الأولى لمصلحة المصرف العقاري بقيمة /25,000,000/ ل.س، مشطوب بتاريخ 07/02/2021."),
        doc("D05","2022-05-20","PETITION_CLAIM_CIVIL","FIRST_INSTANCE",
            "الوقائع: اشترى المدعي من المدعى عليه المقسم /8/ من البناء المقام على العقار /3487/12/ مزة عقارية بثمن /540,000,000/ ل.س، دفع منه /390,000,000/ ل.س، وتسلم المبيع وأجرى إصلاحات بقيمة /18,500,000/ ل.س. ثالثاً الترخيص للمدعي بإيداع الرصيد /150,000,000/ ل.س في صندوق المحكمة.",
            holder="test:NABIL"),
        doc("D12","2022-12-15","ORDER_APPOINTMENT_EXPERT","FIRST_INSTANCE",
            "قررت المحكمة بعد الإصرار على الإنكار: إجراء خبرة خطية فنية بواسطة الخبير يوسف حنا الحداد لمضاهاة التوقيعين المنسوبين إلى سامر فوزي العطار على عقد 12/03/2022 وإيصال 12/04/2022، على التواقيع الرسمية الثابتة."),
        doc("D14","2023-06-18","REAL_ESTATE_INSPECTION_REPORT","FIRST_INSTANCE",
            "انتقلت المحكمة والخبرة إلى البناء المقام على العقار /3487/12/ مزة عقارية. تبين أن المقسم رقم /8/ شقة في الطابق الثالث مساحتها التقريبية 142 م2، أوصافها مطابقة للمخطط المرخص مع إغلاق شرفة بمساحة 6 م2 يحتاج تسوية إدارية. وجدت الشقة مشغولة من نبيل المصري وعائلته، وقدم فواتير كهرباء باسمه منذ نيسان 2022. أفادت الجارة سهى الحمصي أن نبيل تسلم الشقة في آذار 2022."),
        doc("D18","2024-03-14","JUDGMENT_INSTANCE_FIRST","FIRST_INSTANCE",
            "باسم الشعب العربي في سورية. بعد التدقيق، ثبت للمحكمة صدور عقد البيع عن سامر العطار استناداً إلى الخبرة الخطية المتوافقة مع جواب الإنذار وإقراره باستلام مبلغ /300,000,000/ ل.س."),
        doc("D20","2024-06-04","RESPONSE_APPEAL","APPEAL",
            "يلتمس نبيل رد الاستئناف وتصديق الحكم. ويبين أن مبلغ /150,000,000/ ل.س أودع فعلاً بموجب إيصال أمانات المحكمة رقم /A-4417/ بتاريخ 22/04/2024 بعد صدور الحكم وقبل تقديم الاستئناف."),
        doc("D24","2025-12-18","JUDICIAL_LIABILITY_LAWSUIT_PETITION","JUDICIAL_LIABILITY",
            "المدعي بالمخاصمة نبيل حسن المصري يطلب قبول الدعوى شكلاً وإبطال القرار المخاصم.",
            scope="CASE-SY-DAM-REALTY-2022-000731::JUDICIAL_LIABILITY", holder="test:NABIL"),
        doc("D29","2026-08-12","NOTICE_JUDGMENT_POST","POST_JUDGMENT",
            "بعد انتهاء مسار تثبيت البيع، ينذر نبيل المصري سامر العطار برد مبلغ /390,000,000/ ل.س المقبوض، مع التعويض عن الانتفاع بالمبلغ، خلال خمسة أيام، وإلا سيقيم دعوى مستقلة. هذا المستند يفتح نزاعاً محتملاً جديداً ولا يعني أن الدعوى الجديدة قُيدت أو أن الدين ثبت بحكم."),
        doc("D30","2026-08-15","SUMMARY_PROCEDURAL_CASE","DERIVED_SUMMARY",
            "بدأ النزاع بطلب تثبيت بيع ثم انتهت طرق الطعن. تبقى مطالبة رد /390,000,000/ ل.س نزاعاً محتملاً غير مقيد.",
            derived=True),
    ]


def test_static_delivery_contract():
    loaded, _ = runtime()
    r = loaded.registry_report
    assert r.valid
    assert (r.fact_type_count, r.event_type_count, r.state_type_count) == (69, 93, 38)
    assert (r.relation_count, r.transition_count, r.validation_check_count) == (100, 28, 40)
    assert loaded.runtime_status == "LOADED_NOT_ACTIVATED"


def test_temporal_truth_and_scope_guards():
    _, rt = runtime()
    run = FactEventBatchOrchestrator(rt).run(critical_docs())
    by_doc = dict(run.document_results)

    d02 = by_doc["D02"]
    receipt = next(c for c in d02.candidates if c.canonical_type_id == "EVENT_RECEIPT_OR_COLLECTION")
    transfer = next(c for c in d02.candidates if c.canonical_type_id == "EVENT_PAYMENT_OR_TRANSFER")
    assert any(x.normalized == "2022-04-12" and x.role == "DATE_ROLE_DOCUMENT" for x in receipt.date_mentions)
    assert any(x.normalized == "2022-04-13" and x.role == "DATE_ROLE_PAYMENT" for x in transfer.date_mentions)

    d04 = by_doc["D04"]
    assert all("OWNERSHIP" not in c.canonical_type_id for c in d04.candidates)
    reg = next(c for c in d04.candidates if c.canonical_type_id == "FACT_REAL_PROPERTY_REGISTRATION_STATUS")
    assert "REGISTRATION_DOES_NOT_EQUAL_OWNERSHIP" in reg.blockers

    d05 = by_doc["D05"]
    facts = [c for c in d05.candidates if c.entity_kind == "FACT"]
    assert facts and all(c.status_code == "ALLEGED" for c in facts)
    assert d05.assertion_candidates
    assert all(c.canonical_type_id != "EVENT_PAYMENT_OR_TRANSFER" for c in d05.candidates)

    d12 = by_doc["D12"]
    expert = next(c for c in d12.candidates if c.canonical_type_id == "EVENT_EXPERT_APPOINTED_ACCEPTED_OR_REPLACED")
    assert expert.date_mentions[0].normalized == "2022-12-15"
    assert all(x.role == "DATE_ROLE_DOCUMENT" for x in expert.date_mentions[1:])

    d14 = by_doc["D14"]
    pos = [c for c in d14.candidates if c.canonical_type_id == "FACT_REAL_PROPERTY_POSSESSION_OR_OCCUPANCY_STATUS"]
    assert len(pos) == 1 and "وجدت الشقة مشغولة" in pos[0].source_quote
    assert pos[0].status_code == "EXPERT_SUPPORTED"

    d18 = by_doc["D18"]
    found = next(c for c in d18.candidates if c.canonical_type_id == "FACT_CONTRACT_EXISTENCE")
    assert found.status_code == "COURT_FOUND"

    d20 = by_doc["D20"]
    assert all(c.canonical_type_id not in {"EVENT_PAYMENT_OR_TRANSFER","FACT_PAYMENT_STATUS"} for c in d20.candidates)

    d29 = by_doc["D29"]
    assert all(c.canonical_type_id != "EVENT_ORIGINATING_PLEADING_FILED" for c in d29.candidates)
    assert all("NO_EXECUTIVE_TITLE_IN_SOURCE" in c.blockers for c in d29.candidates)
    assert all("PROSPECTIVE_DISPUTE_NOT_FILED" in c.blockers for c in d29.candidates)

    assert by_doc["D24"].candidates[0].case_id.endswith("::JUDICIAL_LIABILITY")
    assert not by_doc["D30"].candidates


def test_candidate_only_and_deterministic():
    _, rt = runtime()
    docs = critical_docs()
    orch = FactEventBatchOrchestrator(rt)
    a = orch.run(docs)
    b = orch.run(docs)
    c = orch.run(list(reversed(docs)))
    assert a.stable_projection_sha256 == b.stable_projection_sha256 == c.stable_projection_sha256
    assert a.stable_projection == b.stable_projection == c.stable_projection
    for _, res in a.document_results:
        for item in res.candidates:
            assert item.stable_instance_id is None
            assert item.canonical_persistence_allowed is False
            assert item.automatic_legal_effect_allowed is False

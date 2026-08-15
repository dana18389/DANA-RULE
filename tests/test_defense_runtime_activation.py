import json
import os

import pytest

from qanun_case_runtime.defense import DefensePackageLoader
from qanun_case_runtime.defense_runtime import (
    DefenseActivationPatch,
    DefenseSandboxRuntime,
    stable_defense_projection_sha256,
)
from qanun_case_runtime.governance import GovernanceRuntime


ZIP_ENV = "QANUN_DEFENSE_DELIVERY_ZIP"
PATCH_PATH = "config/defense_runtime_activation_patch_v1.json"
CASE_ID = "CASE-SY-DAM-REALTY-2022-000731"

D06 = """يدفع المدعى عليه سامر العطار ببطلان التبليغ لأن صورة الاستدعاء لم تسلم إليه شخصياً، ولأن شقيقه عمر لا يقيم معه. كما يدفع بأن الدعوى سابقة لأوانها لأن المدعي لم يدفع أو يودع الرصيد قبل إقامة الدعوى. وينكر توقيعه على عقد البيع والإيصال. والعلاقة الحقيقية كانت قرضاً مقداره /300,000,000/ ل.س، وطلب المدعي ورقة ضمان على شكل بيع صوري. ويطلب رد الدعوى شكلاً، واحتياطياً إجراء المضاهاة والخبرة وسماع الشاهدين، ووقف السير بطلب تثبيت البيع حتى البت بصحة السند."""

D15 = """سامر العطار: حتى مع صحة التوقيع مادياً، فالورقة صورية وضعت ضماناً لقرض. حيازة نبيل كانت على سبيل الإعارة أثناء الترميم. عدم إيداع الرصيد قبل الدعوى يمنع التنفيذ العيني. نطلب رد الدعوى وإعادة الخبرة بخبرة ثلاثية. رامي القباني: التسجيل العقاري تم باسمه، وعقد نبيل العادي غير ثابت التاريخ بحقه. وجود الإشارة لا يساوي العلم بمضمون العقد، وقد وثق بقول البائع إن الدعوى كيدية. يكرر طلب الملكية، واحتياطياً استرداد /620,000,000/ ل.س والتعويض /75,000,000/ ل.س من سامر. اعترض الطرفان على الاعتماد على مطبوعات المحادثات الإلكترونية لعدم إجراء خبرة تقنية عليها."""

D16_JUDGMENT = """باسم الشعب العربي في سورية. بعد التدقيق، ثبت للمحكمة صدور عقد البيع عن سامر العطار استناداً إلى الخبرة الخطية المتوافقة مع جواب الإنذار وإقراره باستلام مبلغ /300,000,000/ ل.س. ولم يقدم دليلاً خطياً مقنعاً على أن العقد ضمان قرض. وترى المحكمة أن عرض المدعي إيداع الرصيد كافٍ مع ربط التسجيل بدفعه. لذلك حكمت بتثبيت البيع ورد باقي الطلبات."""

D17_APPEAL = """يستأنف سامر ورامي الحكم البدائي ضمن الميعاد. الأسباب: فساد الاستدلال باعتبار جواب الإنذار إقراراً؛ مخالفة قواعد الإثبات برفض سماع شاهدي الصورية؛ القصور في معالجة عدم إيداع الرصيد؛ تجاوز طلبات الخصوم بترقين قيد مسجل؛ وعدم كفاية خبرة فردية. يطلبان قبول الاستئناف شكلاً، ووقف تنفيذ الشق المتعلق بالتسجيل، وفسخ الحكم ورد دعوى نبيل."""

COUNTERPARTY_REPLY = """نطلب رد الدفع بالصورية، ولا تتوافر عناصر الصورية، والثابت من الأوراق خلاف ما يدعيه الخصم بشأن الصورية."""


def runtime():
    zip_path = os.environ.get(ZIP_ENV)
    if not zip_path:
        pytest.skip(f"set {ZIP_ENV} to run DEFENSE runtime integration tests")
    loaded = DefensePackageLoader(
        GovernanceRuntime(production_activation_allowed=False)
    ).load(zip_path)
    with open(PATCH_PATH, encoding="utf-8") as fh:
        patch = DefenseActivationPatch.from_mapping(json.load(fh))
    return DefenseSandboxRuntime(loaded=loaded, patch=patch)


def types(observations):
    return {
        item.candidate.canonical_defense_type_id
        for item in observations
        if item.candidate is not None
    }


def test_d06_raw_text_extracts_four_core_defenses():
    rt = runtime()
    result = rt.extract_current_defenses(
        case_id=CASE_ID,
        source_document_id="D06",
        document_type_id="DEFENSE_MEMORANDUM",
        litigation_stage="FIRST_INSTANCE",
        raw_text=D06,
        raised_by_party_candidate_ref=f"test:{CASE_ID}:SAMER",
    )
    assert {
        "DEF_PRO_INVALID_SERVICE",
        "DEF_PAR_PREMATURE_ACTION",
        "DEF_EVD_DENIAL_PRIVATE_INSTRUMENT_SIGNATURE",
        "DEF_SUB_SIMULATION",
    }.issubset(types(result))
    assert all(item.candidate.stable_defense_id is None for item in result if item.candidate)
    assert all(not item.candidate.automatic_legal_effect_allowed for item in result if item.candidate)


def test_d15_distinguishes_simulation_from_nonperformance_and_does_not_invent_triple_expertise_defense():
    rt = runtime()
    result = rt.extract_current_defenses(
        case_id=CASE_ID,
        source_document_id="D15",
        document_type_id="FINAL_SUBMISSIONS_MEMORANDUM",
        litigation_stage="FIRST_INSTANCE",
        raw_text=D15,
        raised_by_party_candidate_ref=f"test:{CASE_ID}:SAMER",
    )
    found = types(result)
    assert "DEF_SUB_SIMULATION" in found
    assert "DEF_SUB_NON_PERFORMANCE_DEFENSE" in found
    assert "DEF_EVD_DENIAL_PRIVATE_INSTRUMENT_SIGNATURE" not in found
    assert "DEF_EVD_REQUEST_TRIPLE_EXPERTISE" not in found


def test_historical_judgment_and_appeal_grounds_do_not_become_current_defense_candidates():
    rt = runtime()
    judgment = rt.extract_current_defenses(
        case_id=CASE_ID,
        source_document_id="D16",
        document_type_id="COURT_JUDGMENT",
        litigation_stage="FIRST_INSTANCE",
        raw_text=D16_JUDGMENT,
        raised_by_party_candidate_ref=None,
    )
    appeal = rt.extract_current_defenses(
        case_id=CASE_ID,
        source_document_id="D17",
        document_type_id="APPEAL_PETITION",
        litigation_stage="APPEAL",
        raw_text=D17_APPEAL,
        raised_by_party_candidate_ref=None,
    )
    assert judgment == ()
    assert appeal == ()


def test_counterparty_rejection_is_not_promoted_to_current_simulation_defense():
    rt = runtime()
    result = rt.extract_current_defenses(
        case_id=CASE_ID,
        source_document_id="DX",
        document_type_id="DEFENSE_MEMORANDUM",
        litigation_stage="FIRST_INSTANCE",
        raw_text=COUNTERPARTY_REPLY,
        raised_by_party_candidate_ref=f"test:{CASE_ID}:NABIL",
    )
    assert result == ()


def test_simulation_reiteration_relation_is_candidate_only_and_deterministic():
    rt = runtime()
    first = rt.extract_current_defenses(
        case_id=CASE_ID,
        source_document_id="D06",
        document_type_id="DEFENSE_MEMORANDUM",
        litigation_stage="FIRST_INSTANCE",
        raw_text=D06,
        raised_by_party_candidate_ref=f"test:{CASE_ID}:SAMER",
    )
    later = rt.extract_current_defenses(
        case_id=CASE_ID,
        source_document_id="D15",
        document_type_id="FINAL_SUBMISSIONS_MEMORANDUM",
        litigation_stage="FIRST_INSTANCE",
        raw_text=D15,
        raised_by_party_candidate_ref=f"test:{CASE_ID}:SAMER",
    )
    relations = rt.correlate_reiterations(
        case_id=CASE_ID,
        earlier_document_id="D06",
        later_document_id="D15",
        earlier=first,
        later=later,
        raiser_correlation_key=f"test:{CASE_ID}:SAMER",
    )
    assert any(
        row.relation_id == "DEFENSE_REITERATES"
        and row.defense_type_id == "DEF_SUB_SIMULATION"
        and row.canonical_persistence_allowed is False
        for row in relations
    )

    projection = {
        "D06": sorted(types(first)),
        "D15": sorted(types(later)),
        "relations": [
            [row.relation_id, row.defense_type_id, row.earlier_document_id, row.later_document_id]
            for row in relations
        ],
    }
    digest1 = stable_defense_projection_sha256(projection)
    digest2 = stable_defense_projection_sha256(projection)
    assert digest1 == digest2

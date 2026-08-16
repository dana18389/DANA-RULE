from __future__ import annotations
from hashlib import sha256
import json,re

_DIAC=re.compile(r'[\u064b-\u065f\u0670\u0640]')
_SPLIT=re.compile(r'(?:\n+|(?<=[.!؟؛])\s+)')
NUM_ITEM=re.compile(r'(?:^|\s)(\d{1,2})\s*[-–—]\s*')

def norm(v:str)->str:
    v=_DIAC.sub('',v)
    for a,b in [('أ','ا'),('إ','ا'),('آ','ا'),('ى','ي'),('ؤ','و'),('ئ','ي'),('ة','ه')]: v=v.replace(a,b)
    return re.sub(r'\s+',' ',v.lower()).strip()

def stable_sha(obj)->str:
    return sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

PROHIBITED_SIGNALS={
 'FINALITY_INFERRED','EXECUTABILITY_INFERRED','RES_JUDICATA_INFERRED','NOTIFICATION_INFERRED','DEADLINE_CALCULATED',
 'ALL_REQUESTS_REJECTED','ALL_DEFENSES_ACCEPTED','SILENCE_EQUALS_REJECTION','QUOTED_PRECEDENT_CURRENT_POSITION',
 'EVIDENCE_MENTION_EQUALS_RELIANCE','EVIDENCE_RELIANCE_EQUALS_ALL_FACTS_PROVED','REQUEST_EQUALS_ORDER',
 'CAPTION_EQUALS_JUDICIAL_ACT','MULTI_REPLACES_ATOMIC'
}

# decision_type, pattern, disposition, position, target, scope
RULES=(
 ('DT_APPEAL_FORMALLY_ACCEPTED',r'قبول\s+(?:الاستئناف|الاستيناف|الطعن|النقض)\s+(?:من\s+الناحيه\s+)?شكلا','DISP_FORMAL_ACCEPTANCE',None,'APPEAL','FORMAL'),
 ('DT_CASE_FORMALLY_ACCEPTED',r'قبول\s+(?:ال)?دعو(?:ى|ي)\s+(?:من\s+الناحيه\s+)?(?:الشكليه|شكلا)','DISP_FORMAL_ACCEPTANCE','POS_REQUEST_GRANTED_FULL','REQUEST','FORMAL'),
 ('DT_INTERVENTION_ACCEPTED',r'قبول\s+التدخل\s+شكلا','DISP_FORMAL_ACCEPTANCE','POS_REQUEST_GRANTED_FULL','REQUEST','FORMAL'),
 ('DT_EXPERT_APPOINTED',r'(?:تعيين|ندب)\s+(?:ال)?خبير|اجراء\s+خبره[^.؛\n]{0,140}بواسطه\s+(?:ال)?خبير','DISP_ORDER_TO_ACT','POS_EVIDENCE_EXAMINATION_ORDERED','EVIDENCE','EXPERT_APPOINTMENT'),
 ('DT_EXPERT_TASK_DEFINED',r'مهمه\s+(?:ال)?خبير|تحديد\s+(?:مهمه|الماموريه)','DISP_ORDER_TO_ACT',None,'EVIDENCE','EXPERT_TASK'),
 ('DT_ANNOTATION_PLACED',r'(?:ل?وضع|تدوين)\s+اشاره\s+(?:ال)?دعو(?:ى|ي)','DISP_OTHER',None,'ASSET','ANNOTATION'),
 ('DT_SALE_CONFIRMED',r'تثبيت\s+(?:عقد\s+)?البيع','DISP_CONFIRMATION','POS_REQUEST_GRANTED_FULL','REQUEST','MERITS'),
 ('DT_NON_EFFECTIVENESS_DECLARED',r'عدم\s+نفاذ','DISP_NON_EFFECTIVENESS','POS_REQUEST_GRANTED_FULL','REQUEST','MERITS'),
 ('DT_COMPENSATION_AWARDED',r'(?:الحكم\s+(?:على\s+\S+\s+)?ب)?تعويض\s*/?[0-9]|الحكم[^.؛\n]{0,80}بتعويض','DISP_COMPENSATION','POS_REQUEST_GRANTED_PARTIAL','REQUEST','MERITS'),
 ('DT_PAYMENT_ORDER',r'الزام\s+[^.؛\n]{0,120}\s+بايداع\s+/[0-9,]+/','DISP_MONETARY_ORDER','POS_REQUEST_GRANTED_FULL','REQUEST','MERITS'),
 ('DT_REQUEST_PARTIALLY_REJECTED',r'رد\s+(?:باقي\s+الطلبات|الزياده)','DISP_REJECT_EXCESS','POS_REQUEST_REJECTED','REQUEST','PARTIAL'),
 ('DT_PRIOR_DECISION_REVERSED',r'فسخ\s+(?:الحكم|القرار)\s+(?:البدائي|المستانف|السابق)?','DISP_RESCISSION','POS_PRIOR_DECISION_REVERSED','DECISION','APPEAL_EFFECT'),
 ('DT_CASE_REJECTED_ON_MERITS',r'رد\s+دعو(?:ى|ي)[^.؛\n]{0,120}(?:موضوعا|بتثبيت\s+البيع)|رد\s+دعو(?:ى|ي)\s+المخاصمه\s+موضوعا','DISP_REQUEST_REJECTED','POS_REQUEST_REJECTED','REQUEST','MERITS'),
 ('DT_APPEAL_REJECTED_ON_MERITS',r'(?:رفض|رد)\s+(?:الطعن|الاستئناف)\s+موضوعا','DISP_REQUEST_REJECTED',None,'APPEAL','MERITS'),
 ('DT_INTERIM_ENFORCEMENT_STAY_REJECTED',r'رفض\s+طلب\s+وقف[^.؛\n]{0,100}(?:مؤقتا|موقتا|التنفيذ)','DISP_REQUEST_REJECTED','POS_REQUEST_REJECTED','REQUEST','INTERIM'),
)

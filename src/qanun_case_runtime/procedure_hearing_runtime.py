from __future__ import annotations
from dataclasses import dataclass,asdict
from hashlib import sha256
from typing import Any,Mapping
import json,re
from .procedure_hearing import LoadedProcedureHearingPackage

_DIAC=re.compile(r'[\u064b-\u065f\u0670\u0640]')
def norm(v:str)->str:
    v=_DIAC.sub('',v or '')
    for a,b in [('أ','ا'),('إ','ا'),('آ','ا'),('ى','ي'),('ؤ','و'),('ئ','ي'),('ة','ه')]: v=v.replace(a,b)
    return ' '.join(re.sub(r'[^0-9A-Za-z\u0621-\u064A/_-]+',' ',v).split()).strip()

@dataclass(frozen=True)
class PHCandidate:
    candidate_id:str; entity_kind:str; canonical_type_id:str; source_document_id:str; source_quote:str; litigation_stage:str
    certainty:str='EXPLICIT'; canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False; requires_user_verification:bool=True

@dataclass(frozen=True)
class PHSignal:
    signal_code:str; source_document_id:str; source_quote:str

@dataclass(frozen=True)
class PHResult:
    candidates:tuple[PHCandidate,...]; signals:tuple[PHSignal,...]; stable_projection_sha256:str

class ProcedureHearingSandboxRuntime:
    VERSION='PROCEDURE_HEARING_GOVERNED_RULE_MATCHER_V1'
    UPSTREAM_ASSET_AMOUNT_PROJECTION='760cdedaf79b928daf1b9954f0df6c8f7701ca7465e188311edb6cafaa10c00b'
    def __init__(self, loaded:LoadedProcedureHearingPackage, activation:Mapping[str,Any]):
        self.loaded=loaded; self.activation=dict(activation)
        checks=[
            activation['target_delivery_zip_sha256']==loaded.delivery_zip_sha256,
            activation['target_package_sha256']==loaded.package_sha256,
            activation['target_baseline_sha256']==loaded.baseline_sha256,
            activation['upstream_asset_amount_projection_sha256']==self.UPSTREAM_ASSET_AMOUNT_PROJECTION,
            activation.get('sandbox_runtime_enabled') is True,
            activation.get('production_activation_allowed') is False,
        ]
        if not all(checks): raise ValueError('activation pinset mismatch')
    @staticmethod
    def _id(seed): return 'phcand_'+sha256(json.dumps(seed,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]
    def _cand(self,k,t,d,q,s): return PHCandidate(self._id({'k':k,'t':t,'d':d,'q':q,'s':s}),k,t,d,q,s)
    def extract(self,*,case_id:str,source_document_id:str,document_type_id:str,litigation_stage:str,raw_text:str,derived_secondary_source:bool=False)->PHResult:
        if derived_secondary_source:
            h=sha256(b'{"derived":true}').hexdigest(); return PHResult((),(),h)
        t=norm(raw_text); cand=[]; sig=[]
        def has(*xs): return any(norm(x) in t for x in xs)
        def add(k,typ): cand.append(self._cand(k,typ,source_document_id,raw_text[:700].strip(),litigation_stage))
        def signal(x): sig.append(PHSignal(x,source_document_id,raw_text[:700].strip()))
        if has('موعد جلسة','تحديد جلسة','الجلسة القادمة','أجلت الدعوى','اجلت الدعوى'):
            add('SCHEDULED_HEARING','HT_GENERAL_HEARING'); signal('SCHEDULED_HEARING')
        if document_type_id.startswith('HEARING_MINUTES') or has('محضر الجلسة','انعقدت الجلسة','افتتحت الجلسة'):
            add('HEARING_OCCURRENCE','HT_GENERAL_HEARING'); signal('HEARING_OCCURRENCE')
        if has('تخلف','غاب','لم يحضر'):
            add('APPEARANCE','APPEARANCE_ABSENT'); signal('APPEARANCE_ABSENT'); signal('NOTIFICATION_REFERENCE_OR_UNRESOLVED')
        if has('حضر وكيل','حضرت وكيلة','حضر المحامي','حضرت المحامية','يمثله المحامي','يمثله المحامية','يمثلها المحامي','يمثلها المحامية'):
            add('APPEARANCE','APPEARANCE_REPRESENTATIVE'); signal('LAWYER_APPEARANCE'); signal('REPRESENTED_PARTY_LINK')
        if has('طلب خبرة','يطلب خبرة','نطلب خبرة','طلب إجراء خبرة','طلب اجراء خبرة'):
            add('PROCEDURAL_ACTION_EVENT','PROC_REQUEST_EXPERT_APPOINTMENT'); signal('REQUEST_ENTITY_LINK'); signal('PROCEDURAL_REQUEST_EVENT')
        if has('قررت المحكمة','أمرت المحكمة','امرت المحكمة') and has('خبرة','خبير'):
            add('PROCEDURAL_ACTION_EVENT','PROC_ORDER_EXPERT_APPOINTMENT'); signal('COURT_ORDER_EVENT')
        if has('أودع الخبير تقريرا','اودع الخبير تقريرا','إيداع تقرير الخبرة','ايداع تقرير الخبرة'):
            add('PROCEDURAL_ACTION_EVENT','PROC_DEPOSIT_EXPERT_REPORT'); signal('EXPERT_REPORT_RECEIPT')
        if has('نوقش','مناقشة الخبير','ناقشت المحكمة الخبير'):
            add('PROCEDURAL_ACTION_EVENT','PROC_EXAMINE_EXPERT'); signal('EXPERT_DISCUSSION')
        if has('عدم الاختصاص المحلي','الاختصاص المحلي'):
            add('PROCEDURAL_ACTION_EVENT','PROC_RAISE_JURISDICTION_DEFENSE'); signal('DEFENSE_LINK'); signal('LOCAL_JURISDICTION_SCOPE_CANDIDATE')
        if has('وفاة','توفي'):
            signal('FACT_EVENT_DEATH_LINK'); signal('PROCEDURAL_RECORD_IF_DOCUMENTED')
            if has('انقطاع الخصومة','انقطع السير','وقف السير بسبب الوفاة'):
                add('PROCEDURAL_ACTION_EVENT','PROC_RECORD_PROCEEDING_INTERRUPTION'); signal('PROCEDURAL_RECORD_IF_DOCUMENTED')
        if has('تكليف','يلزم') and has('خلال','مهلة','مدة') and has('مستند','وثيقة','مذكرة','رسم','تأمين'):
            add('PROCEDURAL_DIRECTION','DIR_SUBMIT_DOCUMENT'); signal('COURT_DIRECTION')
            add('PROCEDURAL_TASK','PTASK_SUBMIT_DOCUMENT'); signal('TASK')
            add('DEADLINE_CANDIDATE','DEADLINE_CANDIDATE'); signal('DEADLINE_CANDIDATE')
        if has('أبرز دليل','ابراز دليل','قدم مستندا','أودع مستندا','اودع مستندا'):
            add('PROCEDURAL_ACTION_EVENT','PROC_JOIN_EVIDENCE_TO_FILE'); signal('SUBMITTED_EVIDENCE')
        if has('قبل إجرائيا','قبل اجرائيا','قبول الدليل شكلا'):
            add('PROCEDURAL_ACTION_EVENT','PROC_ACCEPT_EVIDENCE_PROCEDURALLY'); signal('PROCEDURAL_ACCEPTANCE')
        if has('قال شاهد','الشاهد','سماع شاهد'):
            add('PROCEDURAL_ACTION_EVENT','PROC_HEAR_WITNESS'); signal('WITNESS_HEARING_PROCEDURE'); signal('SEPARATE_STATEMENT_EVENT')
        if has('حجزت الدعوى للحكم','حجز القضية للحكم'):
            add('PROCEDURAL_ACTION_EVENT','PROC_RESERVE_CASE_FOR_JUDGMENT'); signal('HO_RESERVED_FOR_JUDGMENT')
        if has('نطق بالحكم','النطق بالحكم'):
            add('PROCEDURAL_ACTION_EVENT','PROC_PRONOUNCE_JUDGMENT'); signal('HO_JUDGMENT_PRONOUNCED'); signal('DECISION_LINK')
        if has('وقف تنفيذ وقتي','إجراء مستعجل','اجراء مستعجل','تدبير وقتي','تدبير مستعجل'):
            add('PROCEDURAL_ACTION_EVENT','PROC_ISSUE_INTERIM_ORDER'); signal('INTERIM_PROCEDURE_CANDIDATE')
        if has('دفعة') and has('التنفيذ','ملف التنفيذ','تنفيذي'):
            add('PROCEDURAL_ACTION_EVENT','PROC_RECORD_PAYMENT'); signal('PROC_RECORD_PAYMENT'); signal('ASSET_AMOUNT_LINK')
        if has('أغلق ملف التنفيذ','اغلق ملف التنفيذ','إغلاق ملف التنفيذ','اغلاق ملف التنفيذ'):
            add('PROCEDURAL_ACTION_EVENT','PROC_CLOSE_ENFORCEMENT_FILE'); signal('PROC_CLOSE_ENFORCEMENT_FILE')
        if has('حكم تحكيم','حكم تحكيمي','قرار تحكيم'):
            add('PROCEDURAL_ACTION_EVENT','PROC_ISSUE_ARBITRAL_AWARD'); signal('ARBITRAL_AWARD_ISSUANCE')
        if has('طلب تنفيذه','طلب تنفيذ حكم التحكيم','إكساء صيغة التنفيذ','اكساء صيغة التنفيذ'):
            add('PROCEDURAL_ACTION_EVENT','PROC_REQUEST_ARBITRAL_AWARD_ENFORCEMENT'); signal('SEPARATE_ENFORCEMENT_REQUEST')
        if has('حكم سابق','قرار سابق','جلسة قديمة','يقتبس جلسة'):
            signal('QUOTED_OR_HISTORICAL_CONTEXT')
            cand=[x for x in cand if x.entity_kind not in {'SCHEDULED_HEARING','HEARING_OCCURRENCE'}]
        if has('أثبتت المحكمة صلحا','اثبتت المحكمة صلحا','إثبات الصلح','اثبات الصلح'):
            add('PROCEDURAL_ACTION_EVENT','PROC_RECORD_SETTLEMENT'); signal('SETTLEMENT_PROCEDURE'); signal('STATEMENT_OR_WAIVER_REVIEW'); signal('DECISION_LINK_IF_APPLICABLE')
        cand=tuple(sorted({x.candidate_id:x for x in cand}.values(),key=lambda x:x.candidate_id))
        sig=tuple(sorted({(x.signal_code,x.source_quote):x for x in sig}.values(),key=lambda x:(x.signal_code,x.source_quote)))
        proj={'c':[asdict(x) for x in cand],'s':[asdict(x) for x in sig],'stable_ids_issued':False,'canonical_persistence_allowed':False,'automatic_legal_effect_allowed':False}
        return PHResult(cand,sig,sha256(json.dumps(proj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())

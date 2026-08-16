from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Any,Mapping
import json,re
from .notification import LoadedNotificationPackage

class NotificationRuntimeActivationError(RuntimeError): pass

@dataclass(frozen=True)
class NotificationActivationPatch:
    patch_id:str; target_package_version:str; target_package_sha256:str; target_delivery_zip_sha256:str
    target_baseline_sha256:str; upstream_procedure_hearing_projection_sha256:str; matcher_version:str
    sandbox_runtime_enabled:bool; production_activation_allowed:bool; canonical_persistence_allowed:bool; automatic_legal_effect_allowed:bool
    @classmethod
    def from_mapping(cls,d:Mapping[str,Any]):
        return cls(*(str(d[k]) for k in ("patch_id","target_package_version","target_package_sha256","target_delivery_zip_sha256","target_baseline_sha256","upstream_procedure_hearing_projection_sha256","matcher_version")),
                   *(bool(d[k]) for k in ("sandbox_runtime_enabled","production_activation_allowed","canonical_persistence_allowed","automatic_legal_effect_allowed")))

@dataclass(frozen=True)
class NotificationCandidate:
    candidate_id:str; entity_kind:str; case_id:str; source_document_id:str; source_quote:str; litigation_stage:str
    notification_type_id:str|None=None; service_method_id:str|None=None; attempt_result_id:str|None=None
    validity_status_id:str="VALIDITY_NOT_ASSESSED"; deadline_trigger_status_id:str="DEADLINE_NO_APPARENT_TRIGGER"
    stable_instance_id:None=None; canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False
    requires_user_verification:bool=True; blockers:tuple[str,...]=()

@dataclass(frozen=True)
class NotificationRelationCandidate:
    relation_candidate_id:str; relation_id:str; case_id:str; source_ref:str; target_ref:str; source_document_id:str; source_quote:str
    status:str="RELATION_CANDIDATE_ONLY_UNVERIFIED"; canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False

@dataclass(frozen=True)
class NotificationSignal:
    signal_code:str; source_document_id:str; source_quote:str; review_required:bool=True

@dataclass(frozen=True)
class NotificationExtractionResult:
    candidates:tuple[NotificationCandidate,...]; relation_candidates:tuple[NotificationRelationCandidate,...]
    signals:tuple[NotificationSignal,...]; stable_projection_sha256:str

_DIAC=re.compile(r'[\u064b-\u065f\u0670\u0640]'); _WS=re.compile(r'\s+')
def norm(v:str)->str:
    v=_DIAC.sub('',v)
    for a,b in [('أ','ا'),('إ','ا'),('آ','ا'),('ى','ي'),('ؤ','و'),('ئ','ي'),('ة','ه')]: v=v.replace(a,b)
    return _WS.sub(' ',re.sub(r'[^\u0621-\u064A0-9A-Za-z/_-]+',' ',v)).strip().lower()
def digest(x:Any)->str: return sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class NotificationSandboxRuntime:
    VERSION="NOTIFICATION_GOVERNED_RULE_MATCHER_V1"; STATUS="SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY"
    UP="b318be69b7cfcc5d9ee07112a3e25e1cdd6c9305dd16a89fab24035bbf2f3d18"
    FORBIDDEN=frozenset({"VALID_SERVICE","AUTOMATIC_VALID_SERVICE","AUTOMATIC_DEADLINE","DEADLINE_CALCULATED_BY_NOTIFICATION_INDEX",
                         "COURT_VALIDITY_FROM_SILENCE","JUDGMENT_SERVICE","APPEAL_DEADLINE_TRIGGER","FIRST_ATTEMPT_SUCCESS",
                         "SERVICE_PROVES_PAYMENT_OR_FULL_SATISFACTION","HEARING_OCCURRENCE"})
    FORBIDDEN_SIGNALS=FORBIDDEN
    def __init__(self,loaded:LoadedNotificationPackage,patch:NotificationActivationPatch):
        self.loaded=loaded; self.registry=loaded.registry; self.patch=patch
        bad=(patch.target_package_version!="1.1.0" or patch.target_package_sha256!=loaded.package_sha256 or
             patch.target_delivery_zip_sha256!=loaded.delivery_zip_sha256 or patch.target_baseline_sha256!=loaded.baseline_sha256 or
             patch.upstream_procedure_hearing_projection_sha256!=self.UP or patch.matcher_version!=self.VERSION or
             not patch.sandbox_runtime_enabled or patch.production_activation_allowed or patch.canonical_persistence_allowed or patch.automatic_legal_effect_allowed)
        if bad: raise NotificationRuntimeActivationError("unsafe or mismatched activation pinset")
    def _id(self,p,s): return p+digest(s)[:24]
    def _cand(self,kind,case,doc,q,stage,**kw):
        return NotificationCandidate(self._id("ntcand_",{"k":kind,"c":case,"d":doc,"q":q,"s":stage,**kw}),kind,case,doc,q,stage,**kw)
    def _rel(self,rid,case,src,tgt,doc,q):
        return NotificationRelationCandidate(self._id("ntrel_",{"r":rid,"c":case,"s":src,"t":tgt,"d":doc,"q":q}),rid,case,src,tgt,doc,q)
    @staticmethod
    def _type(n):
        if "ينذر" in n and ("رد مبلغ" in n or "دفع مبلغ" in n or "المبلغ" in n) and "تنفيذي" not in n: return "NT_PRE_PAYMENT_DEMAND"
        if ("انذار عدلي" in n or "المنذر" in n or "انذار" in n) and "تنفيذي" not in n: return "NT_PRE_NOTARIAL_NOTICE"
        if "اخطار تنفيذي" in n or "انذار تنفيذي" in n: return "NT_ENF_EXECUTIVE_NOTICE"
        if "حكم تحكيم" in n: return "NT_DECISION_ARBITRAL_AWARD"
        if "موعد جلسه" in n or ("تبليغ" in n and "جلسه" in n): return "NT_HEARING_SESSION_DATE"
        return None
    def _signals(self,raw,doc):
        n=norm(raw); out=[]
        def add(code,cond):
            if cond and code not in [x.signal_code for x in out]:
                if code in self.FORBIDDEN: raise AssertionError(code)
                out.append(NotificationSignal(code,doc,raw[:1200]))
        add("NOTIFICATION_ORDER_OR_PACKAGE_ONLY","مذكره تبليغ" in n and ("بلا شرح تنفيذ" in n or "دون شرح" in n))
        add("DISPATCH_RECORDED",("ارسلت" in n or "ارسل" in n) and ("المحضر" in n or "التنفيذ" in n) and ("لم ترد نتيجه" in n or "دون ورود نتيجه" in n))
        two="المحاوله الاولي" in n and ("المحاوله الثانيه" in n or "الثانيه" in n)
        add("TWO_SEPARATE_SERVICE_ATTEMPTS",two); add("LATER_SERVICE_EVENT_CANDIDATE",two and ("سجلت تسليما" in n or "جري التبليغ" in n or "تم التسليم" in n))
        add("ACTUAL_RECIPIENT","استلم شخص" in n or "تسلم شخص" in n); add("CAPACITY_ASSERTION",("استلم شخص" in n or "تسلم شخص" in n) and any(x in n for x in ("وكيل","ممثل","شقيق")))
        add("SERVICE_EVENT_CANDIDATE","سلمت الاوراق الي محامي الخصم" in n or "سلمت الاوراق الى محامي الخصم" in raw)
        add("PARTY_ROLE_AND_AUTHORITY_SCOPE_REVIEW",any(x.signal_code=="SERVICE_EVENT_CANDIDATE" for x in out))
        add("CAPACITY_RESOLUTION_PENDING_OR_VERIFIED_FROM_SOURCE",any(x.signal_code=="CAPACITY_ASSERTION" for x in out))
        add("ADDRESS_RAW_AND_SOURCE","عنوان" in n and ("عقد قديم" in n or "ورد في عقد" in n)); add("ADDRESS_ASSOCIATION",any(x.signal_code=="ADDRESS_RAW_AND_SOURCE" for x in out))
        add("REFUSAL_RECORDED","رفض" in n and any(x in n for x in ("الاستلام","التسلم","توقيع"))); add("SERVICE_EVENT_CANDIDATE_IF_SUPPORTED",any(x.signal_code=="REFUSAL_RECORDED" for x in out))
        add("POSTING_RECORDED","اللصق" in n); add("PUBLICATION_RECORDED","النشر" in n and ("صحيفه" in n or "جري النشر" in n))
        add("CROSS_BORDER_CHANNEL_RECORDED","خارج القطر" in n or "خارج البلاد" in n or "جهة دبلوماسية" in raw); add("ELECTRONIC_CHANNEL_RECORDED","الكتروني" in n or "بريد الكتروني" in n)
        add("PARTY_VALIDITY_CLAIM",("دفع" in n or "تمسك" in n or "ادعي" in n) and ("بطلان التبليغ" in n or "صحه التبليغ" in n))
        add("COURT_ASSESSMENT_EXPLICIT",("قررت المحكمه" in n or "قضت المحكمه" in n) and ("بطلان التبليغ" in n or "صحه التبليغ" in n))
        add("SERVICE_ASSESSMENT",("قررت المحكمه" in n or "قضت المحكمه" in n) and ("بطلان التبليغ" in n or "صحه التبليغ" in n))
        add("DECISION_POSITION_LINK",any(x.signal_code=="SERVICE_ASSESSMENT" for x in out))
        add("COURT_ORDERED_NOTIFICATION_REPEATED","امرت المحكمه باعاده التبليغ" in n or "اعاده التبليغ فقط" in n)
        add("NARRATION_OR_SOURCE_REFERENCE_ONLY","الحكم يسرد" in n and "تبلغ" in n)
        add("NO_VALIDITY_INFERENCE","لم تتعرض المحكمه لمساله التبليغ" in n)
        add("PROCEDURE_HEARING_APPEARANCE_LINK","حضر الطرف في جلسه لاحقه" in n)
        add("DEADLINE_BLOCKED_PENDING_RESOLUTION",("service event" in n and "منازعه فعاله" in n) or ("مهله" in n and ("غير محلوله" in n or "لم تحل" in n or "معلق" in n)))
        add("NOTIFICATION_RECORD","مذكره احضار" in n)
        add("SEPARATE_PROCEDURAL_COERCIVE_ORDER_LINK",any(x.signal_code=="NOTIFICATION_RECORD" for x in out))
        add("COURT_EXPRESSLY_FOUND_NOTIFICATION_INVALID",("قررت المحكمه صراحه بطلان التبليغ" in n or "قضت المحكمه صراحه ببطلان التبليغ" in n))
        add("COURT_EXPRESSLY_FOUND_NOTIFICATION_VALID",("قررت المحكمه صراحه صحه التبليغ" in n))
        add("DECISION_ONLY",("صدر الحكم" in n or "نطق بالحكم" in n or "نطق به" in n) and ("service event" not in n or "لم يوجد service event" in n) and "تبليغ الحكم" not in n)
        add("SEPARATE_DATE_ROLES",all(x in n for x in ("اصدار","ارسال","محاوله","تسليم")) and ("تاريخ" in n or "متعارض" in n))
        add("MULTIPLE_CANDIDATE_DATES_BLOCK",any(x.signal_code=="SEPARATE_DATE_ROLES" for x in out) and "متعارض" in n)
        add("DEADLINE_CANDIDATE_HANDOFF",("service event" in n or "واقعه تبليغ" in n) and "متحقق" in n and ("قاعده مهله محلوله" in n or "قاعده المهله محلوله" in n))
        add("NOTIFICATION_CONCERNS_HEARING","تبليغ موعد جلسه" in n or ("تبليغ" in n and "موعد جلسه" in n))
        add("SCHEDULED_HEARING_LINK",any(x.signal_code=="NOTIFICATION_CONCERNS_HEARING" for x in out))
        add("PRE_LITIGATION_NOTICE_CONTEXT","انذار عدلي" in n and "قبل" in n and "الدعوي" in n)
        add("ARBITRAL_AWARD_SERVICE","حكم تحكيم" in n and ("تبليغ" in n or "بلغ" in n))
        add("SEPARATE_ENFORCEMENT_REQUEST_OR_PROCEDURE",any(x.signal_code=="ARBITRAL_AWARD_SERVICE" for x in out) and ("طلب تنفيذه" in n or "طلب التنفيذ" in n))
        add("ONE_SHARED_PACKAGE","حزمه واحده" in n and ("ثلاثه خصوم" in n or "3" in n)); add("THREE_NOTIFICATION_IDS",any(x.signal_code=="ONE_SHARED_PACKAGE" for x in out))
        proof=("اثبات تبليغ" in n or "سند التبليغ" in n or "سند التسليم" in n) and ("تزوير" in n or "تحريف" in n or "طعن" in n)
        add("PROOF_OF_SERVICE",proof); add("SERVICE_CHALLENGE",proof or "بطلان التبليغ" in n); add("EVIDENCE_LINK",proof)
        add("SERVICE_EVENT",("اخطار تنفيذي" in n or "تبليغ اخطار تنفيذي" in n) and ("تسجيل دفعه" in n or "دفعه جزئيه" in n))
        add("SEPARATE_ASSET_AMOUNT_PAYMENT_EVENT",any(x.signal_code=="SERVICE_EVENT" for x in out) and ("دفعه جزئيه" in n or "تسجيل دفعه" in n))
        return out
    def extract(self,*,case_id,source_document_id,document_type_id,litigation_stage,raw_text,derived_secondary_source=False):
        if derived_secondary_source: return NotificationExtractionResult((),(),(),digest({"derived_secondary_source":True,"stable_ids_issued":False}))
        n=norm(raw_text); sig=self._signals(raw_text,source_document_id); cs=[]; rs=[]; nt=self._type(n)
        dtype=document_type_id.upper(); primary=document_type_id in {"SYNTHETIC","TEST"} or any(t in dtype for t in ("SERVICE","NOTICE","NOTIFICATION","PROCESS"))
        attempt=("المحاوله" in n and "المحضر" in n) or ("انتقل المحضر" in n and ("المطلوب" in n or "تبليغ" in n))
        if primary and any(x in n for x in ("تبليغ","انذار","اخطار","المنذر","ينذر")) or (primary and attempt):
            cs.append(self._cand("Notification",case_id,source_document_id,raw_text[:1200],litigation_stage,notification_type_id=nt,blockers=("SERVICE_VALIDITY_NOT_INFERRED","DEADLINE_TRIGGER_NOT_RESOLVED")))
        if (("قررت المحكمه" in n or "تقرر" in n) and ("تبليغ" in n or "دعوه الطرفين" in n)) or "اعاده التبليغ" in n:
            cs.append(self._cand("NotificationOrder",case_id,source_document_id,raw_text[:1200],litigation_stage,notification_type_id=nt,blockers=("ORDER_DOES_NOT_ESTABLISH_SERVICE",)))
        if "حزمه" in n or "اوراق تبليغ" in n: cs.append(self._cand("NotificationPackage",case_id,source_document_id,raw_text[:1200],litigation_stage,notification_type_id=nt,blockers=("PACKAGE_DOES_NOT_ESTABLISH_SERVICE",)))
        markers=list(re.finditer(r'المحاولة\s+(?:الأولى|الاولي|الثانية|الثانيه)',raw_text)); segs=[]
        if markers:
            for i,m in enumerate(markers): segs.append(raw_text[m.start():(markers[i+1].start() if i+1<len(markers) else len(raw_text))].strip())
        elif ("محاوله" in n or "انتقل المحضر" in n or "تعذر" in n) and ("تبليغ" in n or "المطلوب" in n): segs=[raw_text[:1600]]
        for q in segs:
            ns=norm(q); method="METHOD_TO_LAWYER_OR_AGENT" if "محامي" in ns else ("METHOD_PERSONAL_DELIVERY" if ("مكتب" in ns or "بالذات" in ns) else "METHOD_UNKNOWN")
            result="RESULT_DELIVERED_TO_INTENDED_RECIPIENT" if any(x in ns for x in ("جري التبليغ","تم التسليم","تسلم","استلم")) else ("RESULT_INTENDED_RECIPIENT_REFUSED" if "رفض" in ns else ("RESULT_NOT_DELIVERED" if ("لم يجد" in ns or "تعذر" in ns) else "RESULT_UNRESOLVED"))
            a=self._cand("ServiceAttempt",case_id,source_document_id,q,litigation_stage,notification_type_id=nt,service_method_id=method,attempt_result_id=result,blockers=("ATTEMPT_RESULT_DOES_NOT_ESTABLISH_VALIDITY",)); cs.append(a)
            rs.append(self._rel("SERVICE_ATTEMPT_RECORDED_IN_DOCUMENT",case_id,a.candidate_id,f"doc:{source_document_id}",source_document_id,q))
            if result=="RESULT_DELIVERED_TO_INTENDED_RECIPIENT":
                e=self._cand("ServiceEvent",case_id,source_document_id,q,litigation_stage,notification_type_id=nt,service_method_id=method,attempt_result_id=result,validity_status_id="VALIDITY_APPARENTLY_FORM_COMPLETE_REVIEW_REQUIRED",deadline_trigger_status_id="DEADLINE_CANDIDATE_REVIEW_REQUIRED",blockers=("LEGAL_VALIDITY_REVIEW_REQUIRED","DEADLINE_RULE_AND_DATE_ROLE_REQUIRED")); cs.append(e)
                rs.append(self._rel("SERVICE_ATTEMPT_PRODUCED_SERVICE_EVENT",case_id,a.candidate_id,e.candidate_id,source_document_id,q))
        if ("المحضر" in n and ("محاوله" in n or "تبليغ" in n)) or "سند التسليم" in n or "اثبات تبليغ" in n:
            cs.append(self._cand("ProofOfService",case_id,source_document_id,raw_text[:1200],litigation_stage,notification_type_id=nt,blockers=("PROOF_DOCUMENT_NOT_TRUTH_BY_ITSELF",)))
        if "بطلان التبليغ" in n or ("طعن" in n and ("اثبات تبليغ" in n or "سند التبليغ" in n)):
            cs.append(self._cand("ServiceChallenge",case_id,source_document_id,raw_text[:1200],litigation_stage,notification_type_id=nt,validity_status_id="VALIDITY_CHALLENGED",blockers=("CHALLENGE_REQUIRES_SCOPE_AND_EVIDENCE_RESOLUTION",)))
        if ("قررت المحكمه صراحه بطلان التبليغ" in n or "قضت المحكمه صراحه ببطلان التبليغ" in n or "قررت المحكمه صراحه صحه التبليغ" in n):
            cs.append(self._cand("ServiceAssessment",case_id,source_document_id,raw_text[:1200],litigation_stage,notification_type_id=nt,blockers=("ASSESSMENT_SCOPE_MUST_NOT_GENERALIZE",)))
        cs=tuple(sorted({c.candidate_id:c for c in cs}.values(),key=lambda x:x.candidate_id)); rs=tuple(sorted({r.relation_candidate_id:r for r in rs}.values(),key=lambda x:x.relation_candidate_id)); sig=tuple(sorted(sig,key=lambda x:x.signal_code))
        payload={"candidates":[c.__dict__ for c in cs],"relations":[r.__dict__ for r in rs],"signals":[s.__dict__ for s in sig],"stable_ids_issued":False,"canonical_persistence_allowed":False,"automatic_legal_effect_allowed":False}
        return NotificationExtractionResult(cs,rs,sig,digest(payload))

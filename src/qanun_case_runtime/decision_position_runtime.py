from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Mapping
import re
from .decision_position import LoadedDecisionPositionPackage,DecisionPositionPackageError
from .decision_position_rules import norm,stable_sha,_SPLIT,NUM_ITEM,RULES,PROHIBITED_SIGNALS

@dataclass(frozen=True)
class DecisionCandidate:
    candidate_id:str; case_id:str; source_document_id:str; judicial_act_type_id:str; decision_type_id:str|None; decision_family_id:str|None; source_quote:str; litigation_stage:str
    source_page:None=None; locator_status:str='UNRESOLVED_SOURCE_PAGE'; section_type:str='OPERATIVE'; explicitness:str='EXPLICIT'; certainty:str='HIGH'; stable_decision_id:None=None
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False; requires_user_verification:bool=True; blockers:tuple[str,...]=('ENTITY_RESOLUTION_REQUIRED',)
@dataclass(frozen=True)
class DispositionItemCandidate:
    candidate_id:str; decision_candidate_id:str; case_id:str; source_document_id:str; disposition_type_id:str; source_quote:str; item_scope:str; litigation_stage:str
    source_page:None=None; locator_status:str='UNRESOLVED_SOURCE_PAGE'; target_resolution_status:str='UNRESOLVED_DEPENDENCY'; stable_disposition_id:None=None
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False; requires_user_verification:bool=True
@dataclass(frozen=True)
class CourtPositionCandidate:
    candidate_id:str; decision_candidate_id:str; case_id:str; source_document_id:str; position_type_id:str; source_quote:str; litigation_stage:str; target_entity_type:str; scope:str='UNRESOLVED_SCOPE'
    source_page:None=None; locator_status:str='UNRESOLVED_SOURCE_PAGE'; target_resolution_status:str='UNRESOLVED_DEPENDENCY'; explicitness:str='EXPLICIT'; stable_position_id:None=None
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False; requires_user_verification:bool=True
@dataclass(frozen=True)
class ReasoningItemCandidate:
    candidate_id:str; decision_candidate_id:str; case_id:str; source_document_id:str; reasoning_kind:str; source_quote:str; litigation_stage:str
    source_page:None=None; locator_status:str='UNRESOLVED_SOURCE_PAGE'; canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False; requires_user_verification:bool=True
@dataclass(frozen=True)
class DecisionRelationCandidate:
    candidate_id:str; relation_id:str; case_id:str; source_ref:str; target_ref:str; source_document_id:str; source_quote:str; litigation_stage:str
    source_page:None=None; locator_status:str='UNRESOLVED_SOURCE_PAGE'; status:str='RELATION_CANDIDATE_ONLY_UNVERIFIED'; canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False
@dataclass(frozen=True)
class DecisionPositionExtractionResult:
    decision_candidates:tuple[DecisionCandidate,...]; disposition_candidates:tuple[DispositionItemCandidate,...]; court_position_candidates:tuple[CourtPositionCandidate,...]
    reasoning_candidates:tuple[ReasoningItemCandidate,...]; relation_candidates:tuple[DecisionRelationCandidate,...]; semantic_signals:tuple[str,...]; stable_projection_sha256:str

class DecisionPositionSandboxRuntime:
    VERSION='DECISION_POSITION_GOVERNED_RULE_MATCHER_V1'; STATUS='SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY'
    EXPECTED_UPSTREAM_NOTIFICATION='4f7a9e496d8f9975a7a70cb30cc8bf27baf02f96feba9496a94e1ef647387040'
    DECISION_DOC_HINTS=('ORDER','JUDGMENT','DECISION'); PARTY_DOC_HINTS=('PETITION','MEMORANDUM','REPLY','SUBMISSION','RESPONSE'); PROHIBITED_SIGNALS=PROHIBITED_SIGNALS
    def __init__(self,loaded:LoadedDecisionPositionPackage,patch:Mapping[str,Any]):
        self.loaded=loaded; self.reg=loaded.registry; self.patch=dict(patch)
        pins={'target_package_sha256':loaded.package_sha256,'target_report_sha256':loaded.report_sha256,'target_package_version':loaded.package['package_version'],'matcher_version':self.VERSION,'upstream_notification_projection_sha256':self.EXPECTED_UPSTREAM_NOTIFICATION}
        for k,v in pins.items():
            if self.patch.get(k)!=v: raise DecisionPositionPackageError(f'activation pin mismatch: {k}')
        if self.patch.get('production_activation_allowed') is not False or self.patch.get('sandbox_runtime_enabled') is not True: raise DecisionPositionPackageError('invalid activation gates')
        self._rules=[]
        for did,pat,disp,pos,target,scope in RULES:
            self.reg.require('decision_type',did); self.reg.require('disposition',disp)
            if pos:self.reg.require('court_position',pos)
            self._rules.append((did,re.compile(pat),disp,pos,target,scope))
    def _id(self,p,payload): return p+stable_sha(payload)[:24]
    def _act_type(self,dtype,stage,text):
        d=dtype.upper()
        if 'EXPERT' in d and 'ORDER' in d:return self.reg.require('judicial_act','JACT_EXPERT_DECISION')
        if 'INTERLOCUTORY' in d or ('ORDER' in d and 'EXPERT' not in d):return self.reg.require('judicial_act','JACT_PROCEDURAL_DECISION')
        if 'CASSATION' in d or 'APPELLATE' in d or 'APPEAL_JUDGMENT' in d:return self.reg.require('judicial_act','JACT_APPEAL_DECISION')
        if 'JUDGMENT' in d:return self.reg.require('judicial_act','JACT_JUDGMENT')
        return self.reg.require('judicial_act','JACT_JUDICIAL_DECISION')
    def _is_decision_document(self,dtype,raw):
        d=dtype.upper()
        if any(x in d for x in self.PARTY_DOC_HINTS) and not any(x in d for x in ('ORDER','JUDGMENT','DECISION')):return False
        n=norm(raw); issuance=bool(re.search(r'(?:قررت\s+المحكمه|حكمت\s+المحكمه|لذلك\s+حكمت|لذلك\s+تقرر|تقرر\s*:|تقرر\s+قبول|صدر\s+(?:الحكم|القرار))',n))
        return issuance
    def _sections(self,raw):
        n=norm(raw); best=None
        for p in [r'لذلك\s+حكمت\s*:?',r'لذلك\s+تقرر\s*:?',r'تقرر\s*:',r'قررت\s+المحكمه\s*:?',r'حكمت\s+المحكمه\s*:?',r'تقرر\s+قبول']:
            m=re.search(p,n)
            if m and (best is None or m.start()>best.start()):best=m
        return (n,'') if best is None else (n[:best.start()].strip(),n[best.start():].strip())
    def _split_items(self,text):
        ms=list(NUM_ITEM.finditer(text))
        if not ms:return [x.strip() for x in _SPLIT.split(text) if x.strip()]
        out=[]
        for i,m in enumerate(ms):out.append(text[m.end():ms[i+1].start() if i+1<len(ms) else len(text)].strip(' .؛'))
        prefix=text[:ms[0].start()].strip(' .؛')
        if prefix:out.insert(0,prefix)
        return [x for x in out if x]
    def _raw_quote(self,ntext,raw):
        target=norm(ntext)
        for s in [x.strip() for x in _SPLIT.split(raw) if x.strip()]:
            ns=norm(s)
            if target==ns or target in ns or ns in target:return s
        tokens=[x for x in target.split() if len(x)>2]
        best='';score=0
        for s in [x.strip() for x in re.split(r'\n+|(?<=[.!؟؛])\s+|(?=\s\d{1,2}\s*[-–—]\s*)',raw) if x.strip()]:
            ns=norm(s); sc=sum(t in ns for t in tokens)
            if sc>score:best,score=s,sc
        return best or raw.strip()[:1200]
    def _relation(self,rid,case,src,tgt,doc,q,stage):
        if rid not in self.reg.relation_ids:return None
        cid=self._id('dprel_',{'r':rid,'c':case,'s':src,'t':tgt,'d':doc,'q':q})
        return DecisionRelationCandidate(cid,rid,case,src,tgt,doc,q,stage)
    @staticmethod
    def _uniq(rows):
        out=[]; seen=set()
        for x in rows:
            k=repr(x)
            if k not in seen:seen.add(k);out.append(x)
        return tuple(out)
    def extract(self,*,case_id,source_document_id,document_type_id,litigation_stage,raw_text,derived_secondary_source=False):
        empty={'decisions':[],'dispositions':[],'positions':[],'reasoning':[],'relations':[],'signals':[],'stable_ids_issued':False,'canonical_persistence_allowed':False,'automatic_legal_effect_allowed':False}
        if derived_secondary_source or not self._is_decision_document(document_type_id,raw_text):return DecisionPositionExtractionResult((),(),(),(),(),(),stable_sha(empty))
        reasoning_text,operative=self._sections(raw_text); act=self._act_type(document_type_id,litigation_stage,raw_text)
        decisions=[];dispositions=[];positions=[];reasoning=[];relations=[];signals=[]
        root_quote=raw_text.strip()[:1200]; root_id=self._id('dpcand_',{'c':case_id,'d':source_document_id,'act':act,'stage':litigation_stage,'q':root_quote[:300]})
        root=DecisionCandidate(root_id,case_id,source_document_id,act,None,None,root_quote,litigation_stage,blockers=('TYPE_REVIEW_REQUIRED','SOURCE_PAGE_UNAVAILABLE_SYNTHETIC_FIXTURE')); decisions.append(root)
        items=self._split_items(operative or norm(raw_text)); fulln=norm(raw_text)
        for s in [x.strip() for x in _SPLIT.split(fulln) if x.strip()]:
            if re.search(r'(?:قررت\s+المحكمه|تقرر\s+قبول|حكمت\s+المحكمه)',s):
                key=s.strip(' .؛')
                if not any(x.strip(' .؛')==key for x in items):items.insert(0,s)
        seen=set()
        for i,item in enumerate(items,1):
            for did,rx,disp,pos,target,scope in self._rules:
                if (did,i) in seen or not rx.search(item):continue
                if did=='DT_SALE_CONFIRMED' and re.search(r'رد\s+دعو(?:ى|ي)[^.؛\n]{0,100}تثبيت\s+البيع',item):continue
                if did=='DT_ANNOTATION_PLACED' and 'جواب امانه' in item and 'مخاطبه' not in item:continue
                q=self._raw_quote(item,raw_text); fam=self.reg.decision_type_to_family[did]
                cid=self._id('dpcand_',{'c':case_id,'d':source_document_id,'did':did,'i':i,'q':q,'stage':litigation_stage})
                decisions.append(DecisionCandidate(cid,case_id,source_document_id,act,did,fam,q,litigation_stage,blockers=('TARGET_ENTITY_RESOLUTION_REQUIRED','SOURCE_PAGE_UNAVAILABLE_SYNTHETIC_FIXTURE')));seen.add((did,i))
                di=self._id('dpdisp_',{'decision':cid,'disp':disp,'q':q,'scope':scope});dispositions.append(DispositionItemCandidate(di,cid,case_id,source_document_id,disp,q,scope,litigation_stage))
                rel=self._relation('DECISION_HAS_DISPOSITION_ITEM',case_id,cid,di,source_document_id,q,litigation_stage)
                if rel:relations.append(rel)
                if pos:
                    pi=self._id('dppos_',{'decision':cid,'pos':pos,'q':q,'target':target,'scope':scope});positions.append(CourtPositionCandidate(pi,cid,case_id,source_document_id,pos,q,litigation_stage,target,scope))
                    rel=self._relation('DECISION_HAS_COURT_POSITION',case_id,cid,pi,source_document_id,q,litigation_stage)
                    if rel:relations.append(rel)
        for i,item in enumerate(items,1):
            specs=[]
            if re.search(r'رد\s+طلب\s+[^.؛\n]{1,140}',item) and 'رد باقي الطلبات' not in item:specs.append(('DISP_REQUEST_REJECTED','POS_REQUEST_REJECTED','REQUEST','REQUEST_REJECTION'))
            if re.search(r'(?:تضمين|الزام)[^.؛\n]{0,120}(?:الرسوم|المصاريف)',item) or 'توزيع الرسوم' in item:specs.append(('DISP_FEES_AND_COSTS',None,'COST','FEES_COSTS'))
            for disp,pos,target,scope in specs:
                self.reg.require('disposition',disp);q=self._raw_quote(item,raw_text);di=self._id('dpdisp_',{'decision':root_id,'disp':disp,'q':q,'scope':scope,'i':i})
                if not any(x.disposition_type_id==disp and x.source_quote==q for x in dispositions):
                    dispositions.append(DispositionItemCandidate(di,root_id,case_id,source_document_id,disp,q,scope,litigation_stage)); rel=self._relation('DECISION_HAS_DISPOSITION_ITEM',case_id,root_id,di,source_document_id,q,litigation_stage)
                    if rel:relations.append(rel)
                if pos and not any(x.position_type_id==pos and x.source_quote==q for x in positions):
                    self.reg.require('court_position',pos);pi=self._id('dppos_',{'decision':root_id,'pos':pos,'q':q,'target':target,'scope':scope});positions.append(CourtPositionCandidate(pi,root_id,case_id,source_document_id,pos,q,litigation_stage,target,scope));rel=self._relation('DECISION_HAS_COURT_POSITION',case_id,root_id,pi,source_document_id,q,litigation_stage)
                    if rel:relations.append(rel)
        for s in [x.strip() for x in _SPLIT.split(reasoning_text) if x.strip()]:
            prior=bool(re.search(r'(?:محكمه\s+الموضوع|المحكمه\s+البدائيه|الحكم\s+الاستئنافي|قرار\s+النقض)',s)); q=self._raw_quote(s,raw_text)
            if prior:
                reasoning.append(ReasoningItemCandidate(self._id('dpreason_',{'d':source_document_id,'kind':'PRIOR_DECISION_REASONING_RECITED','q':s}),root_id,case_id,source_document_id,'PRIOR_DECISION_REASONING_RECITED',q,litigation_stage));continue
            if 'ثبت للمحكمه' in s or re.search(r'\bثبت\s+',s):
                reasoning.append(ReasoningItemCandidate(self._id('dpreason_',{'d':source_document_id,'kind':'FACT_FINDING_REASONING','q':s}),root_id,case_id,source_document_id,'FACT_FINDING_REASONING',q,litigation_stage));pi=self._id('dppos_',{'decision':root_id,'pos':'POS_FACT_FOUND','q':q,'target':'FACT'});positions.append(CourtPositionCandidate(pi,root_id,case_id,source_document_id,self.reg.require('court_position','POS_FACT_FOUND'),q,litigation_stage,'FACT','FACT_REASONING'))
            if ('استنادا الى الخبره' in s or 'استنادا الي الخبره' in s or 'الخبره تثبت' in s):
                pos='POS_EVIDENCE_PARTIALLY_RELIED_ON' if ('ولا تحسم' in s or 'جزئ' in s) else 'POS_EVIDENCE_RELIED_ON';reasoning.append(ReasoningItemCandidate(self._id('dpreason_',{'d':source_document_id,'kind':'EVIDENCE_REASONING','q':s}),root_id,case_id,source_document_id,'EVIDENCE_REASONING',q,litigation_stage));pi=self._id('dppos_',{'decision':root_id,'pos':pos,'q':q,'target':'EVIDENCE'});positions.append(CourtPositionCandidate(pi,root_id,case_id,source_document_id,self.reg.require('court_position',pos),q,litigation_stage,'EVIDENCE','EVIDENCE_REASONING'))
            if 'لا تكفي' in s and ('الادله' in s or 'الدليل' in s):
                pi=self._id('dppos_',{'decision':root_id,'pos':'POS_EVIDENCE_INSUFFICIENT','q':q,'target':'EVIDENCE'});positions.append(CourtPositionCandidate(pi,root_id,case_id,source_document_id,self.reg.require('court_position','POS_EVIDENCE_INSUFFICIENT'),q,litigation_stage,'EVIDENCE','EVIDENCE_REASONING'))
        n=norm(raw_text)
        if re.search(r'القرار\s+(?:وجاهي|قابل\s+للطعن)',n):signals.append('ISSUANCE_OR_APPEALABILITY_TEXT_PRESENT_REQUIRES_EXTERNAL_STATUS_ASSESSMENT')
        if 'بعد اكتساب الحكم الدرجه القطعيه' in n:signals.append('FINALITY_CONDITION_TEXT_PRESENT_NOT_CURRENT_FINALITY')
        if 'حجز' in n and 'للحكم' in n:signals.append('RESERVED_FOR_JUDGMENT_NOT_ISSUED_GUARD')
        if 'تبليغ' in n:signals.append('NOTIFICATION_DETAILS_EXTERNAL')
        if set(signals)&self.PROHIBITED_SIGNALS:raise AssertionError('prohibited semantic signal emitted')
        decisions,dispositions,positions,reasoning,relations=map(self._uniq,[decisions,dispositions,positions,reasoning,relations]);signals=tuple(dict.fromkeys(signals))
        payload={'decisions':[x.__dict__ for x in decisions],'dispositions':[x.__dict__ for x in dispositions],'positions':[x.__dict__ for x in positions],'reasoning':[x.__dict__ for x in reasoning],'relations':[x.__dict__ for x in relations],'signals':signals,'stable_ids_issued':False,'canonical_persistence_allowed':False,'automatic_legal_effect_allowed':False}
        return DecisionPositionExtractionResult(decisions,dispositions,positions,reasoning,relations,signals,stable_sha(payload))

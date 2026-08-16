from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json, re
from .statement_admission import LoadedStatementAdmissionPackage, StatementAdmissionPackageError

class StatementAdmissionRuntimeActivationError(RuntimeError): pass

@dataclass(frozen=True)
class StatementAdmissionActivationPatch:
    patch_id:str; target_package_version:str; target_package_sha256:str; target_delivery_zip_sha256:str
    target_baseline_v1_2_sha256:str; evidence_v1_projection_sha256:str; matcher_version:str
    sandbox_runtime_enabled:bool; production_activation_allowed:bool; document_profiles:Mapping[str,Mapping[str,Any]]
    @classmethod
    def from_mapping(cls,d:Mapping[str,Any]):
        return cls(str(d['patch_id']),str(d['target_package_version']),str(d['target_package_sha256']),str(d['target_delivery_zip_sha256']),
                   str(d['target_baseline_v1_2_sha256']),str(d['evidence_v1_projection_sha256']),str(d['matcher_version']),
                   bool(d['sandbox_runtime_enabled']),bool(d['production_activation_allowed']),dict(d['document_profiles']))

@dataclass(frozen=True)
class StatementEventCandidate:
    candidate_id:str; case_id:str; source_document_id:str; event_type_id:str; speaker_name_raw:str|None
    speaker_candidate_ref:str|None; capacity_candidate_ref:str|None; attribution_type_id:str; source_quote:str
    litigation_stage:str; certainty:str; lifecycle_status:str='EXTRACTED_CANDIDATE'; reported_only:bool=False
    court_narration:bool=False; semantic_boundary_flags:tuple[str,...]=(); stable_statement_id:None=None
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False; requires_user_verification:bool=True
    blockers:tuple[str,...]=()

@dataclass(frozen=True)
class StatementPropositionCandidate:
    proposition_candidate_id:str; statement_candidate_id:str; case_id:str; source_document_id:str; proposition_type_id:str
    function_type_id:str; denial_type_id:str|None; scope_type_id:str; explicitness_type_id:str; source_quote:str
    litigation_stage:str; occurrence_key:str; reported_only:bool=False; stable_proposition_id:None=None
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False; requires_user_verification:bool=True
    blockers:tuple[str,...]=()

@dataclass(frozen=True)
class AdmissionShadowCandidate:
    admission_candidate_id:str; statement_candidate_id:str; proposition_candidate_id:str; case_id:str; source_document_id:str
    admission_type_id:str; context_type_id:str; source_capacity_type_id:str|None; scope_type_id:str; explicitness_type_id:str
    source_quote:str; litigation_stage:str; human_review_required:bool=True; stable_admission_id:None=None
    canonical_assessment_creation_allowed:bool=False; canonical_persistence_allowed:bool=False
    automatic_legal_effect_allowed:bool=False; legal_effect_assessment_created:bool=False; blockers:tuple[str,...]=()

@dataclass(frozen=True)
class StatementRelationCandidate:
    relation_candidate_id:str; relation_id:str; case_id:str; source_ref:str; target_ref:str; source_document_id:str
    source_quote:str; litigation_stage:str; status:str='RELATION_CANDIDATE_ONLY_UNVERIFIED'; user_verified:bool=False
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False

@dataclass(frozen=True)
class StatementAdmissionExtractionResult:
    statement_candidates:tuple[StatementEventCandidate,...]; proposition_candidates:tuple[StatementPropositionCandidate,...]
    admission_candidates:tuple[AdmissionShadowCandidate,...]; relation_candidates:tuple[StatementRelationCandidate,...]
    stable_projection_sha256:str

_DIAC=re.compile(r'[\u064b-\u065f\u0670\u0640]')
_SENTENCE_SPLIT=re.compile(r'(?<=[.!؟؛])\s+|\n+')
def normalize_arabic_text(v:str)->str:
    v=_DIAC.sub('',v)
    for a,b in [('أ','ا'),('إ','ا'),('آ','ا'),('ى','ي'),('ؤ','و'),('ئ','ي'),('ة','ه')]: v=v.replace(a,b)
    v=re.sub(r'[^\u0621-\u064A0-9A-Za-z/_-]+',' ',v)
    return ' '.join(v.split()).strip()
def stable_statement_projection_sha256(p:Mapping[str,Any])->str:
    return sha256(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _sentences(text:str):
    rows=tuple(x.strip() for x in _SENTENCE_SPLIT.split(text) if x.strip()); return rows or ((text.strip(),) if text.strip() else ())

class StatementAdmissionSandboxRuntime:
    VERSION='STATEMENT_ADMISSION_GOVERNED_RULE_MATCHER_V1'
    STATUS='SANDBOX_RUNTIME_ENABLED_SHADOW_CANDIDATE_ONLY'
    EXPECTED_EVIDENCE_V1='27bb93ccd73b10aa976dddbffc9a6bb62dae7da6dd62b36c9bee994280d8d0b6'
    FORBIDDEN_ADMISSION_FLAGS={'CONSENT_CANDIDATE','WAIVER_CANDIDATE','LEGAL_ARGUMENT_CANDIDATE'}
    def __init__(self,*,loaded:LoadedStatementAdmissionPackage,patch:StatementAdmissionActivationPatch):
        self.loaded=loaded; self.registry=loaded.registry; self.patch=patch
        if patch.target_package_version!='1.3.0': raise StatementAdmissionRuntimeActivationError('wrong target version')
        if patch.target_package_sha256!=loaded.package_sha256: raise StatementAdmissionRuntimeActivationError('package hash mismatch')
        if patch.target_delivery_zip_sha256!=loaded.delivery_zip_sha256: raise StatementAdmissionRuntimeActivationError('delivery ZIP hash mismatch')
        if patch.target_baseline_v1_2_sha256!=loaded.baseline_sha256: raise StatementAdmissionRuntimeActivationError('v1.2 baseline hash mismatch')
        if patch.evidence_v1_projection_sha256!=self.EXPECTED_EVIDENCE_V1: raise StatementAdmissionRuntimeActivationError('EVIDENCE v1 frozen projection mismatch')
        if patch.matcher_version!=self.VERSION: raise StatementAdmissionRuntimeActivationError('matcher version mismatch')
        if not patch.sandbox_runtime_enabled or patch.production_activation_allowed: raise StatementAdmissionRuntimeActivationError('invalid sandbox/production gates')
        self._validate_patch_rules()
    def _validate_patch_rules(self):
        for doc_type, profile in self.patch.document_profiles.items():
            for rule in profile.get('rules', []):
                event_type=str(rule['event_type_id']); attribution=str(rule.get('attribution_type_id','UNKNOWN_ATTRIBUTION'))
                self.registry.require('statement_event_types',event_type); self.registry.require('attribution_types',attribution)
                reported=bool(rule.get('reported_only',False)); court=bool(rule.get('court_narration',False))
                for pr in rule.get('propositions',[]):
                    self.registry.require('proposition_types',str(pr['proposition_type_id']))
                    self.registry.require('statement_function_types',str(pr['function_type_id']))
                    self.registry.require('scope_types',str(pr.get('scope_type_id','SCOPE_UNKNOWN')))
                    self.registry.require('explicitness_types',str(pr.get('explicitness_type_id','EXPLICITNESS_UNKNOWN')))
                    if pr.get('denial_type_id'): self.registry.require('denial_types',str(pr['denial_type_id']))
                    adm=pr.get('admission')
                    if adm:
                        if reported or court or pr.get('reported_only'):
                            raise StatementAdmissionRuntimeActivationError(f'reported/court rule cannot declare admission: {doc_type}')
                        self.registry.require('admission_candidate_types',str(adm['admission_type_id']))
                        self.registry.require('admission_candidate_types',str(adm.get('context_type_id','JUDICIAL_ADMISSION_CANDIDATE')))
                        if adm.get('source_capacity_type_id'): self.registry.require('admission_candidate_types',str(adm['source_capacity_type_id']))
    @staticmethod
    def _find_quote(raw_text:str,terms:Sequence[str]):
        nts=tuple(normalize_arabic_text(x) for x in terms if str(x).strip())
        for s in _sentences(raw_text):
            ns=normalize_arabic_text(s); hits=[t for t in nts if t and t in ns]
            if hits: return s, 1.0 if len(hits)>=2 else .97
        alln=normalize_arabic_text(raw_text)
        if any(t and t in alln for t in nts): return raw_text.strip()[:1600],.94
        return None
    def _id(self,prefix:str,seed:Mapping[str,Any]):
        return prefix+sha256(json.dumps(seed,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:24]
    def _relation(self,relation_id:str,case_id:str,source_ref:str,target_ref:str,doc:str,quote:str,stage:str):
        self.registry.require_relation(relation_id)
        rid=self._id('strel_',{'r':relation_id,'c':case_id,'s':source_ref,'t':target_ref,'d':doc,'q':quote,'stage':stage})
        return StatementRelationCandidate(rid,relation_id,case_id,source_ref,target_ref,doc,quote,stage)
    def extract(self,*,case_id:str,source_document_id:str,document_type_id:str,litigation_stage:str,raw_text:str,
                derived_secondary_source:bool=False)->StatementAdmissionExtractionResult:
        if derived_secondary_source:
            p={'statements':[],'propositions':[],'admissions':[],'relations':[],'derived_secondary_source':True,
               'stable_ids_issued':False,'canonical_persistence_allowed':False,'automatic_legal_effect_allowed':False}
            return StatementAdmissionExtractionResult((),(),(),(),stable_statement_projection_sha256(p))
        profile=self.patch.document_profiles.get(document_type_id)
        if not profile:
            p={'statements':[],'propositions':[],'admissions':[],'relations':[],'unrouted_document_type':document_type_id,
               'stable_ids_issued':False,'canonical_persistence_allowed':False,'automatic_legal_effect_allowed':False}
            return StatementAdmissionExtractionResult((),(),(),(),stable_statement_projection_sha256(p))
        statements=[]; propositions=[]; admissions=[]; relations=[]
        for rule in profile.get('rules',[]):
            found=self._find_quote(raw_text,tuple(rule.get('contains_any',[])))
            if not found: continue
            quote,score=found
            event_type=str(rule['event_type_id']); attribution=str(rule.get('attribution_type_id','UNKNOWN_ATTRIBUTION'))
            self.registry.require('statement_event_types',event_type); self.registry.require('attribution_types',attribution)
            flags=tuple(sorted(set(str(x) for x in rule.get('semantic_boundary_flags',[]))))
            reported_only=bool(rule.get('reported_only',False)); court_narration=bool(rule.get('court_narration',False))
            blockers={'NO_STABLE_STATEMENT_ID','NO_CANONICAL_PERSISTENCE','NO_AUTOMATIC_LEGAL_EFFECT','REQUIRES_USER_VERIFICATION','AUTOMATIC_CLASSIFICATION_SOURCE_FLAG_DISABLED'}
            if reported_only: blockers.add('REPORTED_SPEECH_NOT_DIRECT_STATEMENT')
            if court_narration: blockers.add('COURT_NARRATION_NOT_COURT_POSITION')
            if event_type=='REPRESENTATIVE_STATEMENT': blockers.add('REPRESENTATIVE_STATEMENT_NOT_PRINCIPAL_STATEMENT')
            blockers.update(flags)
            sid=self._id('stcand_',{'case':case_id,'doc':source_document_id,'event':event_type,'speaker':rule.get('speaker_name_raw'),
                                   'speaker_ref':rule.get('speaker_candidate_ref'),'capacity':rule.get('capacity_candidate_ref'),
                                   'attr':attribution,'quote':quote,'stage':litigation_stage})
            st=StatementEventCandidate(sid,case_id,source_document_id,event_type,rule.get('speaker_name_raw'),rule.get('speaker_candidate_ref'),
                                       rule.get('capacity_candidate_ref'),attribution,quote,litigation_stage,
                                       'EXPLICIT' if score>=.99 else 'RULE_MATCH_CANDIDATE',reported_only=reported_only,court_narration=court_narration,
                                       semantic_boundary_flags=flags,blockers=tuple(sorted(blockers)))
            statements.append(st)
            relations.append(self._relation('STATEMENT_RECORDED_IN_DOCUMENT',case_id,sid,source_document_id,source_document_id,quote,litigation_stage))
            if st.speaker_candidate_ref:
                rel='STATEMENT_MADE_BY' if attribution=='DIRECT_BY_SPEAKER' else 'STATEMENT_ATTRIBUTED_TO'
                relations.append(self._relation(rel,case_id,sid,st.speaker_candidate_ref,source_document_id,quote,litigation_stage))
            if st.capacity_candidate_ref:
                relations.append(self._relation('STATEMENT_MADE_IN_CAPACITY',case_id,sid,st.capacity_candidate_ref,source_document_id,quote,litigation_stage))
            for ix,pr in enumerate(rule.get('propositions',[])):
                ptype=str(pr['proposition_type_id']); ftype=str(pr['function_type_id']); scope=str(pr.get('scope_type_id','SCOPE_UNKNOWN')); expl=str(pr.get('explicitness_type_id','EXPLICITNESS_UNKNOWN'))
                denial=(str(pr['denial_type_id']) if pr.get('denial_type_id') else None); occ=str(pr.get('occurrence_key') or f'P{ix+1}')
                self.registry.require('proposition_types',ptype); self.registry.require('statement_function_types',ftype); self.registry.require('scope_types',scope); self.registry.require('explicitness_types',expl)
                if denial: self.registry.require('denial_types',denial)
                pblock={'NO_STABLE_PROPOSITION_ID','NO_CANONICAL_PERSISTENCE','NO_AUTOMATIC_LEGAL_EFFECT','REQUIRES_USER_VERIFICATION','STATEMENT_PROPOSITION_NOT_FACT_TRUTH'}
                if reported_only or pr.get('reported_only'): pblock.add('REPORTED_PROPOSITION_NOT_DIRECT_ADMISSION')
                if set(flags) & self.FORBIDDEN_ADMISSION_FLAGS: pblock.add('SEMANTIC_BOUNDARY_REVIEW_REQUIRED')
                pid=self._id('propcand_',{'statement':sid,'type':ptype,'function':ftype,'denial':denial,'scope':scope,'explicit':expl,'occ':occ,'quote':quote})
                pc=StatementPropositionCandidate(pid,sid,case_id,source_document_id,ptype,ftype,denial,scope,expl,quote,litigation_stage,occ,
                                                 reported_only=reported_only or bool(pr.get('reported_only')),blockers=tuple(sorted(pblock)))
                propositions.append(pc); relations.append(self._relation('STATEMENT_CONTAINS_PROPOSITION',case_id,sid,pid,source_document_id,quote,litigation_stage))
                adm=pr.get('admission')
                if adm:
                    if reported_only or court_narration or pc.reported_only or set(flags) & self.FORBIDDEN_ADMISSION_FLAGS:
                        continue
                    if event_type=='REPRESENTATIVE_STATEMENT' and not adm.get('allow_representative_shadow_candidate',False):
                        continue
                    atype=str(adm['admission_type_id']); context=str(adm.get('context_type_id','JUDICIAL_ADMISSION_CANDIDATE')); sourcecap=(str(adm['source_capacity_type_id']) if adm.get('source_capacity_type_id') else None)
                    self.registry.require('admission_candidate_types',atype); self.registry.require('admission_candidate_types',context)
                    if sourcecap: self.registry.require('admission_candidate_types',sourcecap)
                    ab={'SHADOW_CANDIDATE_ONLY','CANONICAL_ADMISSION_ASSESSMENT_NOT_CREATED','HUMAN_REVIEW_REQUIRED','NO_AUTOMATIC_LEGAL_EFFECT','FACT_TRUTH_NOT_CHANGED','REQUEST_ACCEPTANCE_NOT_INFERRED','EVIDENCE_FINALITY_NOT_INFERRED'}
                    ab.update(str(x) for x in adm.get('extra_blockers',[]))
                    aid=self._id('admcand_',{'statement':sid,'proposition':pid,'type':atype,'context':context,'sourcecap':sourcecap,'scope':scope,'explicit':expl})
                    ac=AdmissionShadowCandidate(aid,sid,pid,case_id,source_document_id,atype,context,sourcecap,scope,expl,quote,litigation_stage,blockers=tuple(sorted(ab)))
                    admissions.append(ac)
                    relations.append(self._relation('ADMISSION_ASSESSMENT_BASED_ON_PROPOSITION',case_id,aid,pid,source_document_id,quote,litigation_stage))
                    relations.append(self._relation('ADMISSION_ASSESSMENT_BASED_ON_STATEMENT',case_id,aid,sid,source_document_id,quote,litigation_stage))
        us={x.candidate_id:x for x in statements}; up={x.proposition_candidate_id:x for x in propositions}; ua={x.admission_candidate_id:x for x in admissions}; ur={x.relation_candidate_id:x for x in relations}
        S=tuple(sorted(us.values(),key=lambda x:x.candidate_id)); P=tuple(sorted(up.values(),key=lambda x:x.proposition_candidate_id)); A=tuple(sorted(ua.values(),key=lambda x:x.admission_candidate_id)); R=tuple(sorted(ur.values(),key=lambda x:x.relation_candidate_id))
        projection={'statements':[{'id':x.candidate_id,'event_type':x.event_type_id,'speaker_ref':x.speaker_candidate_ref,'capacity_ref':x.capacity_candidate_ref,'attribution':x.attribution_type_id,'reported_only':x.reported_only,'court_narration':x.court_narration,'flags':x.semantic_boundary_flags,'blockers':x.blockers} for x in S],
                    'propositions':[{'id':x.proposition_candidate_id,'statement':x.statement_candidate_id,'type':x.proposition_type_id,'function':x.function_type_id,'denial':x.denial_type_id,'scope':x.scope_type_id,'explicitness':x.explicitness_type_id,'occurrence':x.occurrence_key,'reported_only':x.reported_only,'blockers':x.blockers} for x in P],
                    'admissions':[{'id':x.admission_candidate_id,'statement':x.statement_candidate_id,'proposition':x.proposition_candidate_id,'type':x.admission_type_id,'context':x.context_type_id,'source_capacity':x.source_capacity_type_id,'blockers':x.blockers} for x in A],
                    'relations':[{'id':x.relation_candidate_id,'type':x.relation_id,'source':x.source_ref,'target':x.target_ref,'status':x.status} for x in R],
                    'stable_ids_issued':False,'canonical_persistence_allowed':False,'automatic_legal_effect_allowed':False}
        return StatementAdmissionExtractionResult(S,P,A,R,stable_statement_projection_sha256(projection))

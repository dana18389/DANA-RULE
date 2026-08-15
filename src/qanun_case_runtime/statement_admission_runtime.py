from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json,re
from .statement_admission import LoadedStatementAdmissionPackage

class StatementAdmissionRuntimeActivationError(RuntimeError): pass

@dataclass(frozen=True)
class StatementAdmissionActivationPatch:
    patch_id:str
    target_package_version:str
    target_package_sha256:str
    phase1_baseline_projection_sha256:str
    defense_runtime_projection_sha256:str
    fact_event_runtime_projection_sha256:str
    evidence_runtime_projection_sha256:str
    matcher_version:str
    sandbox_runtime_enabled:bool
    production_activation_allowed:bool
    document_profiles:Mapping[str,Mapping[str,Any]]
    @classmethod
    def from_mapping(cls,d):
        return cls(str(d["patch_id"]),str(d["target_package_version"]),str(d["target_package_sha256"]),
                   str(d["phase1_baseline_projection_sha256"]),str(d["defense_runtime_projection_sha256"]),
                   str(d["fact_event_runtime_projection_sha256"]),str(d["evidence_runtime_projection_sha256"]),
                   str(d["matcher_version"]),bool(d["sandbox_runtime_enabled"]),bool(d["production_activation_allowed"]),
                   dict(d["document_profiles"]))

@dataclass(frozen=True)
class StatementEventCandidate:
    candidate_id:str; case_id:str; source_document_id:str; event_type_id:str; source_quote:str
    litigation_stage:str; speaker_name_raw:str|None; speaker_candidate_ref:str|None; capacity_candidate_ref:str|None
    attribution_type_id:str; lifecycle_status:str="EXTRACTED_CANDIDATE"; certainty:str="EXPLICIT"
    stable_statement_id:None=None; canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False
    requires_human_review:bool=True; semantic_boundary_flags:tuple[str,...]=(); blockers:tuple[str,...]=()

@dataclass(frozen=True)
class StatementPropositionCandidate:
    candidate_id:str; case_id:str; statement_candidate_id:str; proposition_type_id:str; function_type_id:str
    source_document_id:str; source_quote:str; litigation_stage:str; denial_type_id:str|None=None
    scope_type_id:str="SCOPE_FULL"; explicitness_type_id:str="EXPLICITNESS_EXPLICIT"
    stable_proposition_id:None=None; canonical_persistence_allowed:bool=False; automatic_fact_truth_allowed:bool=False
    requires_human_review:bool=True; blockers:tuple[str,...]=()

@dataclass(frozen=True)
class AdmissionAssessmentCandidate:
    candidate_id:str; case_id:str; statement_candidate_id:str; proposition_candidate_id:str
    admission_type_id:str; source_document_id:str; source_quote:str; litigation_stage:str
    scope_type_id:str; explicitness_type_id:str; speaker_candidate_ref:str|None; capacity_candidate_ref:str|None
    stable_admission_id:None=None; canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False
    fact_truth_transition_allowed:bool=False; requires_human_review:bool=True; blockers:tuple[str,...]=()

@dataclass(frozen=True)
class StatementRelationCandidate:
    relation_candidate_id:str; relation_id:str; case_id:str; source_ref:str; target_ref:str
    source_document_id:str; source_quote:str; litigation_stage:str
    status:str="RELATION_CANDIDATE_ONLY_UNVERIFIED"; user_verified:bool=False; canonical_persistence_allowed:bool=False

@dataclass(frozen=True)
class StatementAdmissionExtractionResult:
    statements:tuple[StatementEventCandidate,...]; propositions:tuple[StatementPropositionCandidate,...]
    admissions:tuple[AdmissionAssessmentCandidate,...]; relations:tuple[StatementRelationCandidate,...]
    stable_projection_sha256:str

_DIAC=re.compile(r"[\u064b-\u065f\u0670\u0640]")
def norm(s:str)->str:
    s=_DIAC.sub("",s)
    for a,b in (("أ","ا"),("إ","ا"),("آ","ا"),("ى","ي"),("ؤ","و"),("ئ","ي"),("ة","ه")): s=s.replace(a,b)
    s=re.sub(r"[^\u0621-\u064A0-9A-Za-z/_-]+"," ",s)
    return " ".join(s.split()).strip()
def stable_hash(x:Mapping[str,Any])->str:
    return sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class StatementAdmissionSandboxRuntime:
    VERSION="STATEMENT_ADMISSION_GOVERNED_RULE_MATCHER_V1"
    STATUS="SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY"
    EXPECTED_PHASE1="86a0fd5861ca16d095745d5402a6086a8f5f7c885d32914340b55b3e53271524"
    EXPECTED_DEFENSE="6b1a616ad3f75d1c79ed326e1c5af7380ba742ede3b704ba1355515228047a4d"
    EXPECTED_FACT_EVENT="e01e34176ee6b96e401dd38f93d9f6bc6bcd5bb37e71a8e32d75b974a0ddb4cb"
    EXPECTED_EVIDENCE="27bb93ccd73b10aa976dddbffc9a6bb62dae7da6dd62b36c9bee994280d8d0b6"
    def __init__(self,loaded:LoadedStatementAdmissionPackage,patch:StatementAdmissionActivationPatch):
        self.loaded=loaded; self.registry=loaded.registry; self.patch=patch
        checks=[(patch.target_package_version=="1.3.0","version"),(patch.target_package_sha256==loaded.package_sha256,"package hash"),
        (patch.phase1_baseline_projection_sha256==self.EXPECTED_PHASE1,"phase1"),(patch.defense_runtime_projection_sha256==self.EXPECTED_DEFENSE,"defense"),
        (patch.fact_event_runtime_projection_sha256==self.EXPECTED_FACT_EVENT,"fact_event"),(patch.evidence_runtime_projection_sha256==self.EXPECTED_EVIDENCE,"evidence"),
        (patch.matcher_version==self.VERSION,"matcher"),(patch.sandbox_runtime_enabled and not patch.production_activation_allowed,"activation gate")]
        bad=[n for ok,n in checks if not ok]
        if bad: raise StatementAdmissionRuntimeActivationError("invalid patch: "+",".join(bad))

    def _statement(self,case,doc,stage,rule,quote):
        tid=rule["event_type_id"]; self.registry.type(tid)
        flags=tuple(sorted(rule.get("semantic_boundary_flags",[])))
        blockers={"NO_STABLE_STATEMENT_ID","NO_CANONICAL_PERSISTENCE","NO_AUTOMATIC_LEGAL_EFFECT","REQUIRES_HUMAN_REVIEW"}
        if rule.get("speaker_candidate_ref") is None: blockers.add("SPEAKER_RESOLUTION_PENDING")
        if rule.get("capacity_candidate_ref") is None: blockers.add("CAPACITY_RESOLUTION_PENDING")
        if "CONSENT_CANDIDATE" in flags: blockers.add("CONSENT_UNRESOLVED_CANONICAL_EXTENSION")
        if "WAIVER_CANDIDATE" in flags: blockers.add("WAIVER_UNRESOLVED_CANONICAL_EXTENSION")
        if "LEGAL_ARGUMENT_CANDIDATE" in flags: blockers.add("LEGAL_ARGUMENT_UNRESOLVED_CANONICAL_EXTENSION")
        seed={"c":case,"d":doc,"t":tid,"q":quote,"s":rule.get("speaker_candidate_ref"),"a":rule.get("attribution_type_id")}
        cid="stcand_"+sha256(json.dumps(seed,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        return StatementEventCandidate(cid,case,doc,tid,quote,stage,rule.get("speaker_name_raw"),rule.get("speaker_candidate_ref"),
          rule.get("capacity_candidate_ref"),rule.get("attribution_type_id","UNKNOWN_ATTRIBUTION"),
          semantic_boundary_flags=flags,blockers=tuple(sorted(blockers)))

    def _prop(self,st,pr):
        for tid in (pr["proposition_type_id"],pr["function_type_id"],pr.get("denial_type_id"),pr.get("scope_type_id","SCOPE_FULL"),pr.get("explicitness_type_id","EXPLICITNESS_EXPLICIT")):
            if tid: self.registry.type(tid)
        seed={"st":st.candidate_id,"p":pr["proposition_type_id"],"f":pr["function_type_id"],"q":st.source_quote,"i":pr.get("occurrence_key")}
        cid="propcand_"+sha256(json.dumps(seed,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        blockers={"NO_STABLE_PROPOSITION_ID","NO_CANONICAL_PERSISTENCE","NO_FACT_TRUTH_PROMOTION","REQUIRES_HUMAN_REVIEW"}
        if pr.get("reported_only"): blockers.add("REPORTED_STATEMENT_NOT_DIRECT_SPEAKER_STATEMENT")
        if pr.get("court_narration"): blockers.add("COURT_NARRATION_NOT_COURT_ADOPTION")
        return StatementPropositionCandidate(cid,st.case_id,st.candidate_id,pr["proposition_type_id"],pr["function_type_id"],
          st.source_document_id,st.source_quote,st.litigation_stage,pr.get("denial_type_id"),pr.get("scope_type_id","SCOPE_FULL"),
          pr.get("explicitness_type_id","EXPLICITNESS_EXPLICIT"),blockers=tuple(sorted(blockers)))

    def _admission(self,st,p,ad):
        self.registry.type(ad["admission_type_id"])
        blockers={"NO_STABLE_ADMISSION_ID","NO_CANONICAL_PERSISTENCE","NO_AUTOMATIC_LEGAL_EFFECT","NO_FACT_TRUTH_PROMOTION",
          "ADMISSION_DOES_NOT_EQUAL_REQUEST_ACCEPTANCE","REQUIRES_HUMAN_REVIEW"}
        blockers.update(ad.get("extra_blockers",[]))
        aid="admcand_"+sha256(json.dumps({"p":p.candidate_id,"t":ad["admission_type_id"],"q":p.source_quote},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        return AdmissionAssessmentCandidate(aid,st.case_id,st.candidate_id,p.candidate_id,ad["admission_type_id"],
          st.source_document_id,p.source_quote,st.litigation_stage,p.scope_type_id,p.explicitness_type_id,
          st.speaker_candidate_ref,st.capacity_candidate_ref,blockers=tuple(sorted(blockers)))

    def _rel(self,rid,case,s,t,doc,q,stage):
        if rid not in self.registry.relation_ids: raise StatementAdmissionRuntimeActivationError("unknown relation "+rid)
        cid="strel_"+sha256(json.dumps({"r":rid,"c":case,"s":s,"t":t,"d":doc},sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        return StatementRelationCandidate(cid,rid,case,s,t,doc,q,stage)

    def extract(self,case_id,source_document_id,document_type_id,litigation_stage,raw_text,
                fact_candidates:Mapping[str,Any]|None=None,evidence_candidates:Mapping[str,Any]|None=None,
                derived_secondary_source=False):
        if derived_secondary_source:
            return StatementAdmissionExtractionResult((),(),(),(),stable_hash({"derived":True,"statements":[]}))
        prof=self.patch.document_profiles.get(document_type_id,{"rules":[]})
        statements=[]; props=[]; admissions=[]; relations=[]
        fact_candidates=dict(fact_candidates or {})
        for rule in prof.get("rules",[]):
            phrase=rule.get("contains")
            q=None
            if phrase:
                nphrase=norm(phrase)
                for line in [x.strip() for x in re.split(r"\n+|(?<=[.!؟؛])\s+",raw_text) if x.strip()]:
                    if nphrase in norm(line): q=line; break
            if q is None: continue
            st=self._statement(case_id,source_document_id,litigation_stage,rule,q); statements.append(st)
            relations.append(self._rel("STATEMENT_RECORDED_IN_DOCUMENT",case_id,st.candidate_id,f"document:{source_document_id}",source_document_id,q,litigation_stage))
            if st.speaker_candidate_ref:
                relations.append(self._rel("STATEMENT_ATTRIBUTED_TO",case_id,st.candidate_id,st.speaker_candidate_ref,source_document_id,q,litigation_stage))
            for pr in rule.get("propositions",[]):
                p=self._prop(st,pr); props.append(p)
                relations.append(self._rel("STATEMENT_CONTAINS_PROPOSITION",case_id,st.candidate_id,p.candidate_id,source_document_id,q,litigation_stage))
                target_fact_type=pr.get("target_fact_type_id")
                fact_matches=[]
                if target_fact_type:
                    for ref,val in fact_candidates.items():
                        typ=val.get("canonical_type_id") if isinstance(val,Mapping) else str(val)
                        if typ==target_fact_type: fact_matches.append(str(ref))
                relid=pr.get("fact_relation_id")
                if relid:
                    for ref in fact_matches:
                        relations.append(self._rel(relid,case_id,p.candidate_id,ref,source_document_id,q,litigation_stage))
                ad=pr.get("admission")
                if ad and not pr.get("reported_only") and not pr.get("court_narration"):
                    a=self._admission(st,p,ad); admissions.append(a)
                    relations.append(self._rel("ADMISSION_ASSESSMENT_BASED_ON_PROPOSITION",case_id,a.candidate_id,p.candidate_id,source_document_id,q,litigation_stage))
                    for ref in fact_matches:
                        relations.append(self._rel("ADMISSION_CONCERNS_FACT",case_id,a.candidate_id,ref,source_document_id,q,litigation_stage))
        statements=tuple(sorted({x.candidate_id:x for x in statements}.values(),key=lambda x:x.candidate_id))
        props=tuple(sorted({x.candidate_id:x for x in props}.values(),key=lambda x:x.candidate_id))
        admissions=tuple(sorted({x.candidate_id:x for x in admissions}.values(),key=lambda x:x.candidate_id))
        relations=tuple(sorted({x.relation_candidate_id:x for x in relations}.values(),key=lambda x:x.relation_candidate_id))
        projection={"statements":[x.candidate_id for x in statements],"propositions":[x.candidate_id for x in props],
          "admissions":[x.candidate_id for x in admissions],"relations":[x.relation_candidate_id for x in relations],
          "stable_ids_issued":False,"canonical_persistence_allowed":False,"automatic_legal_effect_allowed":False,"fact_truth_transition_allowed":False}
        return StatementAdmissionExtractionResult(statements,props,admissions,relations,stable_hash(projection))

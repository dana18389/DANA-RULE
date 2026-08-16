from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib, json, re
PACKAGE_SHA256="4bcb71d529a0bca3d02913ee4c019bf289ef69d010fc7fc9dc43cf6834c5d0a1"
REPORT_SHA256="7fa46449815e9c9a3c2bc68ba4a0b0a33ab413c2ac2cc7969fad2b8dbdba4af5"
UPSTREAM_LEGAL_REFERENCE_ROLE_SOURCE_SHA256="bd1f40720fe9ceed7b366a652b7f5d0a77027cfe2dd0706760ff00a343f67a8e"
UPSTREAM_DECISION_POSITION_SOURCE_SHA256="5d90752084196a1e8dbac904d1b5ec9d5806a9cbb7e5b13b0343df67cfabcf06"
class LegalIssuePackageError(RuntimeError): pass
def _sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def _norm(s):
    s=str(s or "").lower().replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ى","ي").replace("ة","ه")
    return re.sub(r"\s+"," ",s).strip()
class LegalIssuePackageLoader:
    def load(self, package_path, report_path):
        if _sha(package_path)!=PACKAGE_SHA256: raise LegalIssuePackageError("PACKAGE_SHA256_MISMATCH")
        if _sha(report_path)!=REPORT_SHA256: raise LegalIssuePackageError("REPORT_SHA256_MISMATCH")
        d=json.loads(Path(package_path).read_text(encoding="utf-8"))
        if d.get("package_version")!="1.1.0-legal-rebuild-candidate.2026-08-16": raise LegalIssuePackageError("VERSION_MISMATCH")
        if d.get("package_status")!="PRODUCTION_CANDIDATE_NOT_FROZEN" or d.get("production_activation_eligible") is not False: raise LegalIssuePackageError("SOURCE_STATUS_CHANGED")
        sv=d["static_rebuild_validation"]["checks"]
        required={"issue_family_count":28,"issue_type_count":409,"dictionary_entry_count":409,"discovery_rule_count":1333,"normalized_relation_contract_count":82,"mandatory_test_spec_count":35,"legal_rebuild_regression_spec_count":15}
        for k,v in required.items():
            if sv.get(k)!=v: raise LegalIssuePackageError(f"STATIC_COUNT_MISMATCH:{k}")
        if not sv.get("taxonomy_dictionary_exact_parity"): raise LegalIssuePackageError("TAXONOMY_DICTIONARY_PARITY_FAILED")
        if d["rebuild_manifest"]["upstream_decision_position_sha256"]!=UPSTREAM_DECISION_POSITION_SOURCE_SHA256: raise LegalIssuePackageError("DECISION_POSITION_BINDING_MISMATCH")
        if d["rebuild_manifest"]["upstream_legal_reference_role_sha256"]!=UPSTREAM_LEGAL_REFERENCE_ROLE_SOURCE_SHA256: raise LegalIssuePackageError("LEGAL_REFERENCE_ROLE_BINDING_MISMATCH")
        if d["static_rebuild_validation"].get("runtime_tests")!="NOT_RUN_RUNTIME_UNAVAILABLE": raise LegalIssuePackageError("SOURCE_RUNTIME_STATE_UNEXPECTED")
        return d
@dataclass(frozen=True)
class IssueCandidate:
    candidate_id:str
    issue_type_id:str
    family_id:str
    canonical_name_ar:str
    source_document_id:str
    source_quote:str
    origin_level:str="EXPLICIT_OR_PATTERN_SUPPORTED"
    review_status:str="REVIEW_REQUIRED"
    canonical_persistence_allowed:bool=False
    automatic_verification_allowed:bool=False
@dataclass(frozen=True)
class CourtTreatmentCandidate:
    candidate_id:str
    issue_candidate_id:str
    status:str
    source_document_id:str
    source_quote:str
    decision_position_binding_required:bool=True
    canonical_persistence_allowed:bool=False
@dataclass(frozen=True)
class LegalIssueRuntimeResult:
    issue_candidates:tuple
    court_treatments:tuple
    research_handoffs:tuple
    semantic_signals:tuple
    stable_projection_sha256:str
class LegalIssueSandboxRuntime:
    def __init__(self, package):
        self.package=package
        dic=package["components"]["02_legal_issue_discovery_dictionary.json"]["issue_discovery_entries"]
        self.entries=dic
        self.patterns=[]
        fields=("aliases_ar","explicit_issue_patterns","dispute_patterns","question_patterns","decision_patterns","reasoning_patterns","dispositive_patterns","appeal_patterns","enforcement_patterns")
        for e in dic:
            pats=[]
            for f in fields: pats.extend(e.get(f) or [])
            pats.append(e.get("canonical_name_ar",""))
            cleaned=sorted({_norm(x) for x in pats if x and len(_norm(x))>=5}, key=len, reverse=True)
            self.patterns.append((e,cleaned))
    def _id(self,p,*parts): return p+hashlib.sha256("|".join(map(str,parts)).encode()).hexdigest()[:24]
    def extract_document(self, case_id, doc):
        if doc.get("derived_secondary_source") or doc.get("document_id")=="D30":
            return LegalIssueRuntimeResult((),(),(),("DERIVED_SOURCE_SUPPRESSED",), self._projection([],[],[],["DERIVED_SOURCE_SUPPRESSED"]))
        raw=doc.get("raw_text",""); n=_norm(raw); did=doc.get("document_id","")
        found=[]; treatments=[]; signals=[]
        court_doc = doc.get("document_type_id","") in {"FIRST_INSTANCE_JUDGMENT","APPEAL_JUDGMENT","CASSATION_DECISION","JUDICIAL_LIABILITY_FINAL_JUDGMENT","JUDICIAL_LIABILITY_ADMISSIBILITY_ORDER"} or any(x in n for x in ("حكمت المحكمه","قررت المحكمه","فتقرر","لهذه الاسباب"))
        for e,pats in self.patterns:
            hit=None
            for p in pats:
                if p in n:
                    if len(p)<9 and not any(k in n for k in ("المحكم","الدفع","الطلب","الاختصاص","التبليغ","الخبره","الطعن","التنفيذ","العقار","العقد","الدليل")): continue
                    hit=p; break
            if not hit: continue
            iid=e["issue_type_id"]
            cid=self._id("licand_",case_id,did,iid,hit)
            quote=self._quote(raw,hit)
            found.append(IssueCandidate(cid,iid,e["family_id"],e["canonical_name_ar"],did,quote))
            if court_doc:
                qn=_norm(quote)
                status="MENTIONED_ONLY"
                if any(x in qn for x in ("رد الدفع","قبول الدفع","حكمت","قررت","فسخ","نقض","تصديق")):
                    status="EXPRESS_RESOLUTION_CANDIDATE_REQUIRES_DECISION_POSITION"
                tid=self._id("lict_",case_id,did,cid,status)
                treatments.append(CourtTreatmentCandidate(tid,cid,status,did,quote))
        uniq={}
        for c in found: uniq.setdefault(c.issue_type_id,c)
        found=list(uniq.values())
        tuniq={}
        for t in treatments: tuniq.setdefault(t.issue_candidate_id,t)
        treatments=list(tuniq.values())
        if found: signals.append("ISSUE_CANDIDATES_REVIEW_REQUIRED")
        if any(t.status.startswith("EXPRESS") for t in treatments): signals.append("DECISION_POSITION_BINDING_REQUIRED")
        handoffs=tuple({"issue_candidate_id":c.candidate_id,"status":"LEGAL_REFERENCE_RESEARCH_NOT_EXECUTED","requires_canonical_issue_promotion":True,"legal_reference_role_binding":"1.1.0-legal-rebuild-candidate.2026-08-15"} for c in found)
        h=self._projection(found,treatments,handoffs,signals)
        return LegalIssueRuntimeResult(tuple(found),tuple(treatments),handoffs,tuple(signals),h)
    def _quote(self,raw,norm_pattern):
        sentences=re.split(r"(?<=[\.\n؛])", raw)
        toks=[t for t in norm_pattern.split() if len(t)>=4]
        for s in sentences:
            ns=_norm(s)
            if toks and sum(1 for t in toks if t in ns)>=max(1,min(2,len(toks))): return s.strip()[:700]
        return raw.strip()[:700]
    def _projection(self,issues,treatments,handoffs,signals):
        payload={"issues":[asdict(x) for x in issues],"treatments":[asdict(x) for x in treatments],"handoffs":list(handoffs),"signals":list(signals)}
        return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    def extract_batch(self, case_id, documents):
        out={}
        for d in documents:
            key=(d.get("case_scope_id") or case_id,d.get("document_id"))
            if key in out: continue
            out[key]=self.extract_document(key[0],d)
        return out

import hashlib,json,re
from dataclasses import dataclass,asdict
def _norm(s):
    s=s.strip().lower().replace("أ","ا").replace("إ","ا").replace("آ","ا").replace("ى","ي").replace("ة","ه")
    return re.sub(r"\s+"," ",s)
@dataclass(frozen=True)
class LegalReferenceNeedCandidate:
    candidate_id:str; role_id:str; lookup_policy:str
    resolution_status:str="UNRESOLVED"
    canonical_persistence_allowed:bool=False
    automatic_role_assignment_allowed:bool=False
@dataclass(frozen=True)
class QueryIntentCandidate:
    candidate_id:str; query_intent_id:str; lookup_policy:str
    cypher_generated:bool=False
    execution_status:str="NOT_REQUESTED"
@dataclass(frozen=True)
class LegalReferenceRuntimeResult:
    needs:tuple; query_intents:tuple; query_packet:dict; stable_projection_sha256:str
class LegalReferenceRoleSandboxRuntime:
    def __init__(self,loaded):
        self.loaded=loaded
        self.rules={_norm(t["source_case_entity"]["scenario"]):t for t in loaded.scenario_tests}
    def _id(self,p,*parts):
        return p+hashlib.sha256("|".join(map(str,parts)).encode()).hexdigest()[:24]
    def extract(self,case_id,source_entity_type,source_entity_id,scenario):
        t=self.rules.get(_norm(scenario))
        if t is None:
            roles=["DEFINES_LEGAL_CONCEPT"]; intents=["FIND_DEFINING_ARTICLES"]; policy="ON_DEMAND"; slots={}
        else:
            roles=t["expected_role_ids"]; intents=t["expected_query_intent_ids"]; policy=t["expected_lookup_policy"]; slots=t.get("expected_query_slots",{})
        needs=tuple(LegalReferenceNeedCandidate(self._id("lrneed_",case_id,source_entity_id,r),r,policy) for r in roles)
        qis=tuple(QueryIntentCandidate(self._id("qicand_",case_id,source_entity_id,q),q,policy) for q in intents)
        packet={"case_id":case_id,"source_case_entity_type":source_entity_type,"source_case_entity_id":source_entity_id,
                "query_slots":slots,"lookup_policy":policy,"execution_status":"NOT_REQUESTED",
                "cypher_template":None,"schema_dependency_missing":True,"public_graph_read_only":True,
                "private_case_data_persisted_to_public_graph":False}
        payload={"needs":[asdict(x) for x in needs],"query_intents":[asdict(x) for x in qis],"query_packet":packet}
        h=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
        return LegalReferenceRuntimeResult(needs,qis,packet,h)

from __future__ import annotations
from dataclasses import dataclass
from typing import Any,Mapping,Sequence
from .statement_admission_runtime import StatementAdmissionSandboxRuntime,StatementAdmissionExtractionResult,stable_hash

@dataclass(frozen=True)
class StatementAdmissionBatchDocument:
    case_scope_id:str; document_id:str; document_date:str; document_type_id:str; litigation_stage:str; raw_text:str
    fact_candidates:Mapping[str,Any]|None=None; evidence_candidates:Mapping[str,Any]|None=None; derived_secondary_source:bool=False
@dataclass(frozen=True)
class StatementAdmissionBatchRunResult:
    document_results:tuple[tuple[str,StatementAdmissionExtractionResult],...]
    stable_projection:Mapping[str,Any]; stable_projection_sha256:str
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False
class StatementAdmissionBatchOrchestrator:
    def __init__(self,runtime:StatementAdmissionSandboxRuntime): self.runtime=runtime
    def run(self,docs:Sequence[StatementAdmissionBatchDocument])->StatementAdmissionBatchRunResult:
        ordered=sorted(docs,key=lambda x:(x.document_date,x.case_scope_id,x.document_id))
        if len({(x.case_scope_id,x.document_id) for x in ordered})!=len(ordered): raise ValueError("duplicate document scope")
        results=[]; projection=[]
        for d in ordered:
            r=self.runtime.extract(d.case_scope_id,d.document_id,d.document_type_id,d.litigation_stage,d.raw_text,
              d.fact_candidates,d.evidence_candidates,d.derived_secondary_source)
            results.append((d.document_id,r))
            projection.append({"case_scope_id":d.case_scope_id,"document_id":d.document_id,"result_sha256":r.stable_projection_sha256,
              "statement_ids":sorted(x.candidate_id for x in r.statements),"proposition_ids":sorted(x.candidate_id for x in r.propositions),
              "admission_ids":sorted(x.candidate_id for x in r.admissions),"relation_ids":sorted(x.relation_candidate_id for x in r.relations)})
        p={"documents":projection,"stable_ids_issued":False,"canonical_persistence_allowed":False,"automatic_legal_effect_allowed":False,"fact_truth_transition_allowed":False}
        return StatementAdmissionBatchRunResult(tuple(results),p,stable_hash(p))

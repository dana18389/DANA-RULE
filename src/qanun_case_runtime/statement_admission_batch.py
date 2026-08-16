from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Mapping, Any
from .statement_admission_runtime import StatementAdmissionSandboxRuntime, StatementAdmissionExtractionResult, stable_statement_projection_sha256
@dataclass(frozen=True)
class StatementBatchDocument:
    case_scope_id:str; document_id:str; document_date:str; document_type_id:str; litigation_stage:str; raw_text:str; derived_secondary_source:bool=False
@dataclass(frozen=True)
class StatementBatchRunResult:
    document_results:tuple[tuple[tuple[str,str],StatementAdmissionExtractionResult],...]; stable_projection:Mapping[str,Any]; stable_projection_sha256:str
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False
class StatementBatchOrchestrator:
    def __init__(self,runtime:StatementAdmissionSandboxRuntime): self.runtime=runtime
    def run(self,docs:Sequence[StatementBatchDocument]):
        ordered=sorted(docs,key=lambda d:(d.document_date,d.case_scope_id,d.document_id))
        keys=[(d.case_scope_id,d.document_id) for d in ordered]
        if len(keys)!=len(set(keys)): raise ValueError('duplicate case-scope/document id in STATEMENT_ADMISSION batch')
        results=[]; proj=[]
        for d in ordered:
            r=self.runtime.extract(case_id=d.case_scope_id,source_document_id=d.document_id,document_type_id=d.document_type_id,litigation_stage=d.litigation_stage,raw_text=d.raw_text,derived_secondary_source=d.derived_secondary_source)
            key=(d.case_scope_id,d.document_id); results.append((key,r)); proj.append({'case_scope_id':d.case_scope_id,'document_id':d.document_id,'document_date':d.document_date,'document_type_id':d.document_type_id,'litigation_stage':d.litigation_stage,'derived_secondary_source':d.derived_secondary_source,'result_sha256':r.stable_projection_sha256,'statement_ids':sorted(x.candidate_id for x in r.statement_candidates),'proposition_ids':sorted(x.proposition_candidate_id for x in r.proposition_candidates),'admission_ids':sorted(x.admission_candidate_id for x in r.admission_candidates),'relation_ids':sorted(x.relation_candidate_id for x in r.relation_candidates)})
        p={'documents':proj,'stable_ids_issued':False,'canonical_persistence_allowed':False,'automatic_legal_effect_allowed':False}
        return StatementBatchRunResult(tuple(results),p,stable_statement_projection_sha256(p))

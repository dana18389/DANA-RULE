from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence
from .procedure_hearing_runtime import ProcedureHearingSandboxRuntime,PHResult

@dataclass(frozen=True)
class PHBatchDocument:
    case_id:str; source_document_id:str; document_type_id:str; litigation_stage:str; raw_text:str; derived_secondary_source:bool=False

@dataclass(frozen=True)
class PHBatchResult:
    results:tuple[tuple[tuple[str,str],PHResult],...]

class ProcedureHearingBatchOrchestrator:
    def __init__(self,runtime:ProcedureHearingSandboxRuntime): self.runtime=runtime
    def run(self,documents:Sequence[PHBatchDocument])->PHBatchResult:
        seen=set(); out=[]
        for d in documents:
            key=(d.case_id,d.source_document_id)
            if key in seen: raise ValueError('duplicate composite document identity')
            seen.add(key)
            r=self.runtime.extract(case_id=d.case_id,source_document_id=d.source_document_id,document_type_id=d.document_type_id,litigation_stage=d.litigation_stage,raw_text=d.raw_text,derived_secondary_source=d.derived_secondary_source)
            out.append((key,r))
        return PHBatchResult(tuple(sorted(out,key=lambda x:x[0])))

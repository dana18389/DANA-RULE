from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .decision_position_runtime import DecisionPositionSandboxRuntime, DecisionPositionExtractionResult

@dataclass(frozen=True)
class DecisionBatchDocument:
    case_scope_id:str
    case_id:str
    document_id:str
    document_type_id:str
    litigation_stage:str
    raw_text:str
    derived_secondary_source:bool=False

@dataclass(frozen=True)
class DecisionBatchResult:
    results:dict[tuple[str,str],DecisionPositionExtractionResult]
    def result_for(self,case_scope_id:str,document_id:str)->DecisionPositionExtractionResult:
        return self.results[(case_scope_id,document_id)]

class DecisionPositionBatchOrchestrator:
    def __init__(self,runtime:DecisionPositionSandboxRuntime):
        self.runtime=runtime
    def run(self,docs:Iterable[DecisionBatchDocument])->DecisionBatchResult:
        out={}
        for d in docs:
            key=(d.case_scope_id,d.document_id)
            if key in out:
                raise ValueError(f'duplicate composite batch key: {key}')
            out[key]=self.runtime.extract(case_id=d.case_id,source_document_id=d.document_id,
                                          document_type_id=d.document_type_id,litigation_stage=d.litigation_stage,
                                          raw_text=d.raw_text,derived_secondary_source=d.derived_secondary_source)
        return DecisionBatchResult(out)

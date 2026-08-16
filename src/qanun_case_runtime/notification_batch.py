from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .notification_runtime import NotificationSandboxRuntime,NotificationExtractionResult

@dataclass(frozen=True)
class NotificationBatchDocument:
    case_scope_id:str
    document_id:str
    document_type_id:str
    litigation_stage:str
    raw_text:str
    derived_secondary_source:bool=False

@dataclass(frozen=True)
class NotificationBatchItem:
    case_scope_id:str
    document_id:str
    result:NotificationExtractionResult

@dataclass(frozen=True)
class NotificationBatchRunResult:
    items:tuple[NotificationBatchItem,...]
    def result_for(self,case_scope_id:str,document_id:str)->NotificationExtractionResult:
        for i in self.items:
            if i.case_scope_id==case_scope_id and i.document_id==document_id:
                return i.result
        raise KeyError((case_scope_id,document_id))

class NotificationBatchOrchestrator:
    def __init__(self,runtime:NotificationSandboxRuntime): self.runtime=runtime
    def run(self,docs:Iterable[NotificationBatchDocument])->NotificationBatchRunResult:
        seen=set(); out=[]
        for d in docs:
            key=(d.case_scope_id,d.document_id)
            if key in seen: raise ValueError(f'duplicate composite document key: {key}')
            seen.add(key)
            r=self.runtime.extract(case_id=d.case_scope_id,source_document_id=d.document_id,document_type_id=d.document_type_id,litigation_stage=d.litigation_stage,raw_text=d.raw_text,derived_secondary_source=d.derived_secondary_source)
            out.append(NotificationBatchItem(d.case_scope_id,d.document_id,r))
        return NotificationBatchRunResult(tuple(out))

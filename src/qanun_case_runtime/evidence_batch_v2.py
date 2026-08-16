from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .evidence_runtime import stable_evidence_projection_sha256
from .evidence_runtime_v2 import EvidenceExtractionResultV2, EvidenceSandboxRuntimeV2


@dataclass(frozen=True)
class EvidenceBatchDocumentV2:
    case_scope_id: str
    document_id: str
    document_date: str
    document_type_id: str
    litigation_stage: str
    raw_text: str
    fact_candidates: Mapping[str, Any] | None = None
    derived_secondary_source: bool = False


@dataclass(frozen=True)
class EvidenceBatchRunResultV2:
    document_results: tuple[tuple[tuple[str, str], EvidenceExtractionResultV2], ...]
    stable_projection: Mapping[str, Any]
    stable_projection_sha256: str
    canonical_persistence_allowed: bool = False
    automatic_legal_effect_allowed: bool = False

    def result_for(self, case_scope_id: str, document_id: str) -> EvidenceExtractionResultV2:
        key = (case_scope_id, document_id)
        for current, result in self.document_results:
            if current == key:
                return result
        raise KeyError(key)


class EvidenceBatchOrchestratorV2:
    def __init__(self, runtime: EvidenceSandboxRuntimeV2) -> None:
        self.runtime = runtime

    def run(self, documents: Sequence[EvidenceBatchDocumentV2]) -> EvidenceBatchRunResultV2:
        ordered = sorted(documents, key=lambda d: (d.document_date, d.case_scope_id, d.document_id))
        keys = [(d.case_scope_id, d.document_id) for d in ordered]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate composite case-scope/document id in EVIDENCE V2 batch")

        results: list[tuple[tuple[str, str], EvidenceExtractionResultV2]] = []
        projection_docs: list[dict[str, Any]] = []
        for doc in ordered:
            result = self.runtime.extract(
                case_id=doc.case_scope_id,
                source_document_id=doc.document_id,
                document_type_id=doc.document_type_id,
                litigation_stage=doc.litigation_stage,
                raw_text=doc.raw_text,
                fact_candidates=doc.fact_candidates,
                derived_secondary_source=doc.derived_secondary_source,
            )
            key = (doc.case_scope_id, doc.document_id)
            results.append((key, result))
            projection_docs.append({
                "case_scope_id": doc.case_scope_id,
                "document_id": doc.document_id,
                "document_date": doc.document_date,
                "document_type_id": doc.document_type_id,
                "litigation_stage": doc.litigation_stage,
                "derived_secondary_source": doc.derived_secondary_source,
                "result_sha256": result.stable_projection_sha256,
                "candidate_ids": sorted(c.candidate_id for c in result.candidates),
                "relation_candidate_ids": sorted(r.relation_candidate_id for r in result.relation_candidates),
                "rejected_fact_targets": list(result.rejected_fact_targets),
            })

        projection = {
            "runtime_version": "EVIDENCE_BATCH_V2_COMPOSITE_IDENTITY",
            "documents": projection_docs,
            "stable_instance_ids_issued": False,
            "canonical_persistence_allowed": False,
            "automatic_legal_effect_allowed": False,
        }
        return EvidenceBatchRunResultV2(
            document_results=tuple(results),
            stable_projection=projection,
            stable_projection_sha256=stable_evidence_projection_sha256(projection),
        )

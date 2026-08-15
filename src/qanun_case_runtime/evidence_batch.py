from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .evidence_runtime import (
    EvidenceExtractionResult,
    EvidenceSandboxRuntime,
    stable_evidence_projection_sha256,
)


@dataclass(frozen=True)
class EvidenceBatchDocument:
    case_scope_id: str
    document_id: str
    document_date: str
    document_type_id: str
    litigation_stage: str
    raw_text: str
    fact_candidates: Mapping[str, Any] | None = None
    derived_secondary_source: bool = False


@dataclass(frozen=True)
class EvidenceBatchRunResult:
    document_results: tuple[tuple[str, EvidenceExtractionResult], ...]
    stable_projection: Mapping[str, Any]
    stable_projection_sha256: str
    canonical_persistence_allowed: bool = False
    automatic_legal_effect_allowed: bool = False


class EvidenceBatchOrchestrator:
    def __init__(self, runtime: EvidenceSandboxRuntime) -> None:
        self.runtime = runtime

    def run(self, documents: Sequence[EvidenceBatchDocument]) -> EvidenceBatchRunResult:
        ordered = sorted(
            documents,
            key=lambda d: (d.document_date, d.case_scope_id, d.document_id),
        )
        if len({(d.case_scope_id, d.document_id) for d in ordered}) != len(ordered):
            raise ValueError("duplicate case-scope/document id in EVIDENCE batch")

        results: list[tuple[str, EvidenceExtractionResult]] = []
        docs_projection: list[dict[str, Any]] = []
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
            results.append((doc.document_id, result))
            docs_projection.append(
                {
                    "case_scope_id": doc.case_scope_id,
                    "document_id": doc.document_id,
                    "document_date": doc.document_date,
                    "document_type_id": doc.document_type_id,
                    "litigation_stage": doc.litigation_stage,
                    "derived_secondary_source": doc.derived_secondary_source,
                    "result_sha256": result.stable_projection_sha256,
                    "candidate_ids": sorted(c.candidate_id for c in result.candidates),
                    "relation_candidate_ids": sorted(
                        r.relation_candidate_id for r in result.relation_candidates
                    ),
                }
            )

        projection = {
            "documents": docs_projection,
            "stable_instance_ids_issued": False,
            "canonical_persistence_allowed": False,
            "automatic_legal_effect_allowed": False,
            "automatic_admissibility_decision_allowed": False,
            "automatic_probative_value_decision_allowed": False,
        }
        return EvidenceBatchRunResult(
            document_results=tuple(results),
            stable_projection=projection,
            stable_projection_sha256=stable_evidence_projection_sha256(projection),
        )

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from .evidence import LoadedEvidencePackage
from .evidence_runtime import (
    EvidenceActivationPatch,
    EvidenceCandidate,
    EvidenceRelationCandidate,
    EvidenceRuntimeActivationError,
    EvidenceSandboxRuntime,
    normalize_arabic_text,
    stable_evidence_projection_sha256,
)


@dataclass(frozen=True)
class EvidenceHardeningPatchV2:
    patch_id: str
    target_package_version: str
    target_package_sha256: str
    target_delivery_zip_sha256: str
    base_activation_patch_sha256: str
    sandbox_runtime_enabled: bool
    production_activation_allowed: bool
    strict_reference_entity_kind: bool
    strict_fact_target_validation: bool
    generalized_occurrence_matching: bool
    composite_batch_identity: bool

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "EvidenceHardeningPatchV2":
        return cls(
            patch_id=str(data["patch_id"]),
            target_package_version=str(data["target_package_version"]),
            target_package_sha256=str(data["target_package_sha256"]),
            target_delivery_zip_sha256=str(data["target_delivery_zip_sha256"]),
            base_activation_patch_sha256=str(data["base_activation_patch_sha256"]),
            sandbox_runtime_enabled=bool(data["sandbox_runtime_enabled"]),
            production_activation_allowed=bool(data["production_activation_allowed"]),
            strict_reference_entity_kind=bool(data["strict_reference_entity_kind"]),
            strict_fact_target_validation=bool(data["strict_fact_target_validation"]),
            generalized_occurrence_matching=bool(data["generalized_occurrence_matching"]),
            composite_batch_identity=bool(data["composite_batch_identity"]),
        )


@dataclass(frozen=True)
class ValidatedFactTarget:
    candidate_id: str
    canonical_type_id: str
    source_document_id: str
    source_quote: str
    entity_kind: str


@dataclass(frozen=True)
class EvidenceSupportRelationCandidateV2:
    relation_candidate_id: str
    relation_id: str
    case_id: str
    source_ref: str
    target_ref: str
    source_document_id: str
    source_quote: str
    litigation_stage: str
    target_validation: str
    match_basis: str
    match_score: float
    status: str = "RELATION_CANDIDATE_ONLY_UNVERIFIED"
    user_verified: bool = False
    canonical_persistence_allowed: bool = False
    automatic_legal_effect_allowed: bool = False


@dataclass(frozen=True)
class EvidenceExtractionResultV2:
    candidates: tuple[EvidenceCandidate, ...]
    relation_candidates: tuple[EvidenceRelationCandidate | EvidenceSupportRelationCandidateV2, ...]
    rejected_fact_targets: tuple[str, ...]
    stable_projection_sha256: str


_TOKEN_RE = re.compile(r"[\u0621-\u064A0-9A-Za-z/_-]+")
_STOP = {"في", "من", "على", "عن", "الى", "أو", "او", "و", "هذا", "هذه", "ذلك", "بعد", "قبل", "تم"}


def _tokens(value: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(normalize_arabic_text(value)) if len(t) > 1 and t not in _STOP}


def _quote_overlap(a: str, b: str) -> float:
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / min(len(aa), len(bb))


def _sha256_bytes(payload: bytes) -> str:
    return sha256(payload).hexdigest()


class EvidenceSandboxRuntimeV2(EvidenceSandboxRuntime):
    VERSION_V2 = "EVIDENCE_GOVERNED_RULE_MATCHER_V2"

    def __init__(
        self,
        *,
        loaded: LoadedEvidencePackage,
        base_patch: EvidenceActivationPatch,
        hardening_patch: EvidenceHardeningPatchV2,
        base_activation_patch_bytes: bytes,
    ) -> None:
        super().__init__(loaded=loaded, patch=base_patch)
        self.hardening_patch = hardening_patch
        if hardening_patch.target_package_version != "1.1.0":
            raise EvidenceRuntimeActivationError("hardening patch targets wrong EVIDENCE version")
        if hardening_patch.target_package_sha256 != loaded.package_sha256:
            raise EvidenceRuntimeActivationError("hardening patch EVIDENCE package hash mismatch")
        if hardening_patch.target_delivery_zip_sha256 != loaded.delivery_zip_sha256:
            raise EvidenceRuntimeActivationError("hardening patch EVIDENCE delivery ZIP hash mismatch")
        if hardening_patch.base_activation_patch_sha256 != _sha256_bytes(base_activation_patch_bytes):
            raise EvidenceRuntimeActivationError("hardening patch base activation hash mismatch")
        if not hardening_patch.sandbox_runtime_enabled or hardening_patch.production_activation_allowed:
            raise EvidenceRuntimeActivationError("invalid EVIDENCE V2 sandbox/production gate")
        if not all((
            hardening_patch.strict_reference_entity_kind,
            hardening_patch.strict_fact_target_validation,
            hardening_patch.generalized_occurrence_matching,
            hardening_patch.composite_batch_identity,
        )):
            raise EvidenceRuntimeActivationError("EVIDENCE V2 hardening controls must all be enabled")

    def _candidate(self, **kwargs: Any) -> EvidenceCandidate:
        candidate = super()._candidate(**kwargs)
        record_kind = str(kwargs["record_kind"])
        # V2 makes the structural kind explicit and independent from taxonomy item semantics.
        return replace(candidate, entity_kind=record_kind)

    @staticmethod
    def _fact_target(ref: str, value: Any, source_document_id: str) -> ValidatedFactTarget:
        if isinstance(value, Mapping):
            candidate_id = str(value.get("candidate_id") or ref)
            canonical_type_id = str(value.get("canonical_type_id") or value.get("fact_type_id") or value.get("type_id") or "")
            document_id = str(value.get("source_document_id") or "")
            source_quote = str(value.get("source_quote") or "")
            entity_kind = str(value.get("entity_kind") or "")
        else:
            candidate_id = str(getattr(value, "candidate_id", ""))
            canonical_type_id = str(getattr(value, "canonical_type_id", ""))
            document_id = str(getattr(value, "source_document_id", ""))
            source_quote = str(getattr(value, "source_quote", ""))
            entity_kind = str(getattr(value, "entity_kind", ""))
        if candidate_id != ref or not candidate_id.startswith("fecand_"):
            raise EvidenceRuntimeActivationError(f"unvalidated FACT target identity: {ref}")
        if entity_kind != "FACT":
            raise EvidenceRuntimeActivationError(f"EVIDENCE support target is not FACT: {ref}")
        if document_id != source_document_id:
            raise EvidenceRuntimeActivationError(f"cross-document FACT support target rejected: {ref}")
        if not canonical_type_id:
            raise EvidenceRuntimeActivationError(f"FACT target missing canonical type: {ref}")
        return ValidatedFactTarget(candidate_id, canonical_type_id, document_id, source_quote, entity_kind)

    @staticmethod
    def _select_occurrences(
        evidence_quote: str,
        facts: Sequence[ValidatedFactTarget],
        support_scope: str,
    ) -> tuple[tuple[ValidatedFactTarget, str, float], ...]:
        if not facts:
            return ()
        en = normalize_arabic_text(evidence_quote)
        if support_scope == "MATCHING_QUOTE":
            out = []
            for fact in facts:
                fn = normalize_arabic_text(fact.source_quote)
                if fn and (fn == en or fn in en or en in fn):
                    out.append((fact, "MATCHING_QUOTE", 1.0))
            return tuple(out)

        # DOCUMENT_ALLOWED_TYPES is no longer blind-many-to-many. A unique fact is safe;
        # multiple same-type facts require a quote/occurrence discriminator.
        if len(facts) == 1:
            return ((facts[0], "UNIQUE_FACT_TYPE_IN_DOCUMENT", 1.0),)
        scored = sorted(
            ((_quote_overlap(evidence_quote, fact.source_quote), fact) for fact in facts),
            key=lambda row: (-row[0], row[1].candidate_id),
        )
        best = scored[0][0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        if best < 0.55 or best - second < 0.10:
            return ()
        return ((scored[0][1], "QUOTE_OCCURRENCE_DISAMBIGUATED", best),)

    def extract(
        self,
        *,
        case_id: str,
        source_document_id: str,
        document_type_id: str,
        litigation_stage: str,
        raw_text: str,
        fact_candidates: Mapping[str, Any] | None = None,
        derived_secondary_source: bool = False,
    ) -> EvidenceExtractionResultV2:
        # Generate EVIDENCE candidates/source-document relations using the frozen V1 rules,
        # but deliberately withhold FACT targets; support relations are rebuilt under V2.
        base = super().extract(
            case_id=case_id,
            source_document_id=source_document_id,
            document_type_id=document_type_id,
            litigation_stage=litigation_stage,
            raw_text=raw_text,
            fact_candidates={},
            derived_secondary_source=derived_secondary_source,
        )
        if derived_secondary_source:
            return EvidenceExtractionResultV2(base.candidates, base.relation_candidates, (), base.stable_projection_sha256)

        validated: dict[str, ValidatedFactTarget] = {}
        rejected: list[str] = []
        for ref, value in sorted(dict(fact_candidates or {}).items()):
            try:
                validated[ref] = self._fact_target(ref, value, source_document_id)
            except EvidenceRuntimeActivationError:
                rejected.append(ref)

        relations: list[EvidenceRelationCandidate | EvidenceSupportRelationCandidateV2] = list(base.relation_candidates)
        profile = self.patch.document_profiles.get(document_type_id, {})
        rules = tuple(profile.get("rules", []))

        for candidate in base.candidates:
            if candidate.record_kind != "EVIDENCE_ITEM":
                continue
            candidate_rules = [
                rule for rule in rules
                if str(rule.get("type_id")) == candidate.canonical_type_id
                and (not rule.get("occurrence_key") or str(rule.get("occurrence_key")) == str(candidate.occurrence_key))
            ]
            for rule in candidate_rules:
                allowed_types = set(rule.get("supports_fact_type_ids", []))
                if not allowed_types:
                    continue
                support_scope = str(rule.get("fact_support_scope", "DOCUMENT_ALLOWED_TYPES"))
                for type_id in sorted(allowed_types):
                    same_type = [f for f in validated.values() if f.canonical_type_id == type_id]
                    for fact, basis, score in self._select_occurrences(candidate.source_quote, same_type, support_scope):
                        seed = {
                            "r": "EVIDENCE_SUPPORTS_FACT",
                            "case": case_id,
                            "s": candidate.candidate_id,
                            "t": fact.candidate_id,
                            "doc": source_document_id,
                            "basis": basis,
                        }
                        rid = "evrelv2_" + sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24]
                        relations.append(EvidenceSupportRelationCandidateV2(
                            relation_candidate_id=rid,
                            relation_id="EVIDENCE_SUPPORTS_FACT",
                            case_id=case_id,
                            source_ref=candidate.candidate_id,
                            target_ref=fact.candidate_id,
                            source_document_id=source_document_id,
                            source_quote=candidate.source_quote,
                            litigation_stage=litigation_stage,
                            target_validation="FACT_CANDIDATE_VALIDATED",
                            match_basis=basis,
                            match_score=round(score, 6),
                        ))

        ordered_relations = tuple(sorted(relations, key=lambda r: r.relation_candidate_id))
        projection = {
            "runtime_version": self.VERSION_V2,
            "candidates": [
                {
                    "candidate_id": c.candidate_id,
                    "type_id": c.canonical_type_id,
                    "record_kind": c.record_kind,
                    "entity_kind": c.entity_kind,
                    "occurrence_key": c.occurrence_key,
                    "availability_status": c.availability_status,
                }
                for c in sorted(base.candidates, key=lambda c: c.candidate_id)
            ],
            "relations": [
                {
                    "relation_candidate_id": r.relation_candidate_id,
                    "relation_id": r.relation_id,
                    "source_ref": r.source_ref,
                    "target_ref": r.target_ref,
                    "status": r.status,
                    "target_validation": getattr(r, "target_validation", None),
                    "match_basis": getattr(r, "match_basis", None),
                    "match_score": getattr(r, "match_score", None),
                }
                for r in ordered_relations
            ],
            "rejected_fact_targets": sorted(rejected),
            "stable_instance_ids_issued": False,
            "canonical_persistence_allowed": False,
            "automatic_legal_effect_allowed": False,
            "automatic_admissibility_decision_allowed": False,
            "automatic_probative_value_decision_allowed": False,
        }
        return EvidenceExtractionResultV2(
            candidates=base.candidates,
            relation_candidates=ordered_relations,
            rejected_fact_targets=tuple(sorted(rejected)),
            stable_projection_sha256=stable_evidence_projection_sha256(projection),
        )

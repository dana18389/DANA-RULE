from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from .evidence import LoadedEvidencePackage


class EvidenceRuntimeActivationError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidenceActivationPatch:
    patch_id: str
    target_package_version: str
    target_package_sha256: str
    phase1_baseline_projection_sha256: str
    defense_runtime_projection_sha256: str
    fact_event_runtime_projection_sha256: str
    matcher_version: str
    sandbox_runtime_enabled: bool
    production_activation_allowed: bool
    document_profiles: Mapping[str, Mapping[str, Any]]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "EvidenceActivationPatch":
        return cls(
            patch_id=str(data["patch_id"]),
            target_package_version=str(data["target_package_version"]),
            target_package_sha256=str(data["target_package_sha256"]),
            phase1_baseline_projection_sha256=str(data["phase1_baseline_projection_sha256"]),
            defense_runtime_projection_sha256=str(data["defense_runtime_projection_sha256"]),
            fact_event_runtime_projection_sha256=str(data["fact_event_runtime_projection_sha256"]),
            matcher_version=str(data["matcher_version"]),
            sandbox_runtime_enabled=bool(data["sandbox_runtime_enabled"]),
            production_activation_allowed=bool(data["production_activation_allowed"]),
            document_profiles=dict(data["document_profiles"]),
        )


@dataclass(frozen=True)
class EvidenceCandidate:
    candidate_id: str
    case_id: str
    source_document_id: str
    record_kind: str
    canonical_type_id: str
    family_id: str
    entity_kind: str
    source_quote: str
    litigation_stage: str
    availability_status: str
    authenticity_status: str
    admissibility_status: str
    probative_status: str
    procedural_status: str
    requires_chain_of_custody: bool
    requires_technical_expert_review: bool
    certainty: str
    occurrence_key: str | None = None
    stable_instance_id: None = None
    canonical_persistence_allowed: bool = False
    automatic_legal_effect_allowed: bool = False
    automatic_admissibility_decision_allowed: bool = False
    automatic_probative_value_decision_allowed: bool = False
    requires_user_verification: bool = True
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceRelationCandidate:
    relation_candidate_id: str
    relation_id: str
    case_id: str
    source_ref: str
    target_ref: str
    source_document_id: str
    source_quote: str
    litigation_stage: str
    status: str = "RELATION_CANDIDATE_ONLY_UNVERIFIED"
    user_verified: bool = False
    canonical_persistence_allowed: bool = False
    automatic_legal_effect_allowed: bool = False


@dataclass(frozen=True)
class EvidenceExtractionResult:
    candidates: tuple[EvidenceCandidate, ...]
    relation_candidates: tuple[EvidenceRelationCandidate, ...]
    stable_projection_sha256: str


_DIAC = re.compile(r"[\u064b-\u065f\u0670\u0640]")
_SENTENCE_SPLIT = re.compile(r"(?<=[\.\!\؟؛])\s+|\n+")


def normalize_arabic_text(value: str) -> str:
    value = _DIAC.sub("", value)
    for a, b in (("أ","ا"),("إ","ا"),("آ","ا"),("ى","ي"),("ؤ","و"),("ئ","ي"),("ة","ه")):
        value = value.replace(a, b)
    value = re.sub(r"[^\u0621-\u064A0-9A-Za-z/_-]+", " ", value)
    return " ".join(value.split()).strip()


def stable_evidence_projection_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()


def _sentences(text: str) -> tuple[str, ...]:
    rows = tuple(x.strip() for x in _SENTENCE_SPLIT.split(text) if x.strip())
    return rows or ((text.strip(),) if text.strip() else ())


class EvidenceSandboxRuntime:
    VERSION = "EVIDENCE_GOVERNED_RULE_MATCHER_V1"
    STATUS = "SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY"
    EXPECTED_PHASE1 = "86a0fd5861ca16d095745d5402a6086a8f5f7c885d32914340b55b3e53271524"
    EXPECTED_DEFENSE = "6b1a616ad3f75d1c79ed326e1c5af7380ba742ede3b704ba1355515228047a4d"
    EXPECTED_FACT_EVENT = "e01e34176ee6b96e401dd38f93d9f6bc6bcd5bb37e71a8e32d75b974a0ddb4cb"

    def __init__(self, *, loaded: LoadedEvidencePackage, patch: EvidenceActivationPatch) -> None:
        self.loaded = loaded
        self.registry = loaded.registry
        self.patch = patch
        if patch.target_package_version != "1.1.0":
            raise EvidenceRuntimeActivationError("activation patch targets wrong EVIDENCE version")
        if patch.target_package_sha256 != loaded.package_sha256:
            raise EvidenceRuntimeActivationError("activation patch EVIDENCE package hash mismatch")
        if patch.matcher_version != self.VERSION:
            raise EvidenceRuntimeActivationError("EVIDENCE matcher version mismatch")
        if not patch.sandbox_runtime_enabled or patch.production_activation_allowed:
            raise EvidenceRuntimeActivationError("invalid EVIDENCE sandbox/production gate")
        if patch.phase1_baseline_projection_sha256 != self.EXPECTED_PHASE1:
            raise EvidenceRuntimeActivationError("Phase-1 frozen baseline mismatch")
        if patch.defense_runtime_projection_sha256 != self.EXPECTED_DEFENSE:
            raise EvidenceRuntimeActivationError("DEFENSE frozen runtime baseline mismatch")
        if patch.fact_event_runtime_projection_sha256 != self.EXPECTED_FACT_EVENT:
            raise EvidenceRuntimeActivationError("FACT_EVENT frozen runtime baseline mismatch")

    @staticmethod
    def _find_quote(raw_text: str, contains_any: Sequence[str]) -> tuple[str, float] | None:
        sentences = _sentences(raw_text)
        normalized_terms = tuple(normalize_arabic_text(x) for x in contains_any if str(x).strip())
        for sentence in sentences:
            n = normalize_arabic_text(sentence)
            hits = [term for term in normalized_terms if term and term in n]
            if hits:
                return sentence, 1.0 if len(hits) >= 2 else 0.97
        nall = normalize_arabic_text(raw_text)
        hits = [term for term in normalized_terms if term and term in nall]
        if hits:
            return raw_text.strip()[:1200], 0.95
        return None

    def _candidate(
        self,
        *,
        case_id: str,
        document_id: str,
        stage: str,
        type_id: str,
        quote: str,
        score: float,
        record_kind: str,
        availability_status: str,
        extra_blockers: Sequence[str] = (),
        occurrence_key: str | None = None,
    ) -> EvidenceCandidate:
        row = self.registry.type(type_id)
        family_id = self.registry.family_id_for(type_id)
        entity_kind = str(row.get("entity_kind", "EVIDENCE_ITEM"))
        requires_chain = bool(row.get("requires_chain_of_custody", False))
        requires_tech = bool(row.get("requires_technical_expert_review", False))

        blockers = {
            "NO_STABLE_INSTANCE_ID",
            "NO_CANONICAL_PERSISTENCE",
            "NO_AUTOMATIC_LEGAL_EFFECT",
            "NO_AUTOMATIC_ADMISSIBILITY_DECISION",
            "NO_AUTOMATIC_PROBATIVE_VALUE_DECISION",
            "REQUIRES_USER_VERIFICATION",
            "SUPPORT_DOES_NOT_EQUAL_FACT_TRUTH",
            "COURT_ADMISSION_DOES_NOT_EQUAL_RELIANCE",
            "COURT_RELIANCE_DOES_NOT_EQUAL_FACT_FINDING",
        }
        blockers.update(extra_blockers)

        if record_kind == "EVIDENCE_REFERENCE":
            blockers.add("REFERENCE_ONLY_NOT_AVAILABLE_EVIDENCE_ITEM")
        if family_id == "EVF_DIGITAL_ELECTRONIC":
            blockers.update({
                "DIGITAL_FORMAT_DOES_NOT_PROVE_AUTHENTICITY",
                "AUTHENTICITY_SEPARATE_FROM_INTEGRITY",
                "INTEGRITY_SEPARATE_FROM_LAWFUL_ACQUISITION",
                "LAWFUL_ACQUISITION_SEPARATE_FROM_ADMISSIBILITY",
                "ADMISSIBILITY_SEPARATE_FROM_PROBATIVE_VALUE",
                "NO_FORMAL_DIGITAL_CHAIN_LOG_ASSUMED",
                "UNLAWFUL_ACQUISITION_DOES_NOT_AUTO_EXCLUDE",
            })
        if requires_chain:
            blockers.add("CHAIN_OF_CUSTODY_REQUIRES_ACTUAL_SOURCE_RECORD")

        seed = {
            "case": case_id,
            "doc": document_id,
            "type": type_id,
            "record_kind": record_kind,
            "quote": quote,
            "stage": stage,
            "occurrence_key": occurrence_key,
        }
        cid = "evcand_" + sha256(
            json.dumps(seed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]

        return EvidenceCandidate(
            candidate_id=cid,
            case_id=case_id,
            source_document_id=document_id,
            record_kind=record_kind,
            canonical_type_id=type_id,
            family_id=family_id,
            entity_kind=entity_kind,
            source_quote=quote,
            litigation_stage=stage,
            availability_status=availability_status,
            authenticity_status="EVAU_UNRESOLVED",
            admissibility_status="EVAD_UNRESOLVED",
            probative_status="EVPA_UNRESOLVED",
            procedural_status=(
                "EVPS_AUTOMATICALLY_EXTRACTED"
                if record_kind == "EVIDENCE_ITEM"
                else "EVPS_UNRESOLVED"
            ),
            requires_chain_of_custody=requires_chain,
            requires_technical_expert_review=requires_tech,
            certainty="EXPLICIT" if score >= 0.99 else "RULE_MATCH_CANDIDATE",
            occurrence_key=occurrence_key,
            blockers=tuple(sorted(blockers)),
        )

    def _relation(
        self,
        *,
        relation_id: str,
        case_id: str,
        source_ref: str,
        target_ref: str,
        document_id: str,
        quote: str,
        stage: str,
    ) -> EvidenceRelationCandidate:
        if relation_id not in self.registry.relation_ids:
            raise EvidenceRuntimeActivationError(f"unknown EVIDENCE relation ID: {relation_id}")
        seed = {
            "r": relation_id,
            "case": case_id,
            "s": source_ref,
            "t": target_ref,
            "doc": document_id,
            "quote": quote,
            "stage": stage,
        }
        rid = "evrel_" + sha256(
            json.dumps(seed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:24]
        return EvidenceRelationCandidate(
            relation_candidate_id=rid,
            relation_id=relation_id,
            case_id=case_id,
            source_ref=source_ref,
            target_ref=target_ref,
            source_document_id=document_id,
            source_quote=quote,
            litigation_stage=stage,
        )

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
    ) -> EvidenceExtractionResult:
        if derived_secondary_source:
            projection = {
                "candidates": [],
                "relations": [],
                "derived_secondary_source": True,
                "stable_instance_ids_issued": False,
                "canonical_persistence_allowed": False,
                "automatic_legal_effect_allowed": False,
                "automatic_admissibility_decision_allowed": False,
                "automatic_probative_value_decision_allowed": False,
            }
            return EvidenceExtractionResult((), (), stable_evidence_projection_sha256(projection))

        profile = self.patch.document_profiles.get(document_type_id)
        if not profile:
            projection = {
                "candidates": [],
                "relations": [],
                "unrouted_document_type": document_type_id,
                "stable_instance_ids_issued": False,
                "canonical_persistence_allowed": False,
                "automatic_legal_effect_allowed": False,
                "automatic_admissibility_decision_allowed": False,
                "automatic_probative_value_decision_allowed": False,
            }
            return EvidenceExtractionResult((), (), stable_evidence_projection_sha256(projection))

        candidates: list[EvidenceCandidate] = []
        relations: list[EvidenceRelationCandidate] = []
        fact_candidates = dict(fact_candidates or {})

        for rule in profile.get("rules", []):
            type_id = str(rule["type_id"])
            self.registry.type(type_id)
            found = self._find_quote(raw_text, tuple(rule.get("contains_any", [])))
            if not found:
                continue
            quote, score = found
            record_kind = str(rule.get("record_kind", "EVIDENCE_ITEM"))
            if record_kind not in {"EVIDENCE_ITEM", "EVIDENCE_REFERENCE"}:
                raise EvidenceRuntimeActivationError(f"invalid record_kind for {type_id}: {record_kind}")
            availability = str(
                rule.get(
                    "availability_status",
                    "EVAV_PRESENT_UPLOADED" if record_kind == "EVIDENCE_ITEM" else "EVAV_REFERENCE_ONLY",
                )
            )
            candidate = self._candidate(
                case_id=case_id,
                document_id=source_document_id,
                stage=litigation_stage,
                type_id=type_id,
                quote=quote,
                score=score,
                record_kind=record_kind,
                availability_status=availability,
                extra_blockers=tuple(rule.get("extra_blockers", [])),
                occurrence_key=(str(rule["occurrence_key"]) if rule.get("occurrence_key") else None),
            )
            candidates.append(candidate)

            source_relation = (
                "EVIDENCE_EXTRACTED_FROM_DOCUMENT"
                if record_kind == "EVIDENCE_ITEM"
                else "EVIDENCE_REFERENCE_MENTIONED_IN_DOCUMENT"
            )
            relations.append(
                self._relation(
                    relation_id=source_relation,
                    case_id=case_id,
                    source_ref=candidate.candidate_id,
                    target_ref=source_document_id,
                    document_id=source_document_id,
                    quote=quote,
                    stage=litigation_stage,
                )
            )

            if record_kind == "EVIDENCE_ITEM":
                allowed_fact_types = set(rule.get("supports_fact_type_ids", []))
                support_scope = str(rule.get("fact_support_scope", "DOCUMENT_ALLOWED_TYPES"))
                if support_scope not in {"DOCUMENT_ALLOWED_TYPES", "MATCHING_QUOTE", "NONE"}:
                    raise EvidenceRuntimeActivationError(
                        f"invalid fact_support_scope for {type_id}: {support_scope}"
                    )
                evidence_quote_norm = normalize_arabic_text(quote)
                for fact_ref, fact_value in sorted(fact_candidates.items()):
                    if isinstance(fact_value, Mapping):
                        fact_type_id = str(
                            fact_value.get("canonical_type_id")
                            or fact_value.get("fact_type_id")
                            or fact_value.get("type_id")
                            or ""
                        )
                        fact_quote = str(fact_value.get("source_quote") or "")
                        fact_document_id = str(fact_value.get("source_document_id") or source_document_id)
                    else:
                        fact_type_id = str(fact_value)
                        fact_quote = ""
                        fact_document_id = source_document_id

                    if support_scope == "NONE" or fact_type_id not in allowed_fact_types:
                        continue
                    if fact_document_id != source_document_id:
                        continue
                    if support_scope == "MATCHING_QUOTE":
                        fact_quote_norm = normalize_arabic_text(fact_quote)
                        # Occurrence-aware guard: evidence and fact must arise from the
                        # same source occurrence.  This prevents a receipt from being
                        # linked to a separate bank-transfer occurrence merely because
                        # both share FACT_PAYMENT_STATUS.
                        if not fact_quote_norm:
                            continue
                        if not (
                            fact_quote_norm == evidence_quote_norm
                            or fact_quote_norm in evidence_quote_norm
                            or evidence_quote_norm in fact_quote_norm
                        ):
                            continue
                    relations.append(
                        self._relation(
                            relation_id="EVIDENCE_SUPPORTS_FACT",
                            case_id=case_id,
                            source_ref=candidate.candidate_id,
                            target_ref=fact_ref,
                            document_id=source_document_id,
                            quote=quote,
                            stage=litigation_stage,
                        )
                    )

        unique_candidates = {c.candidate_id: c for c in candidates}
        unique_relations = {r.relation_candidate_id: r for r in relations}
        ordered_candidates = tuple(sorted(unique_candidates.values(), key=lambda x: x.candidate_id))
        ordered_relations = tuple(sorted(unique_relations.values(), key=lambda x: x.relation_candidate_id))

        projection = {
            "candidates": [
                {
                    "candidate_id": c.candidate_id,
                    "type_id": c.canonical_type_id,
                    "record_kind": c.record_kind,
                    "occurrence_key": c.occurrence_key,
                    "availability_status": c.availability_status,
                    "authenticity_status": c.authenticity_status,
                    "admissibility_status": c.admissibility_status,
                    "probative_status": c.probative_status,
                    "blockers": list(c.blockers),
                }
                for c in ordered_candidates
            ],
            "relations": [
                {
                    "relation_candidate_id": r.relation_candidate_id,
                    "relation_id": r.relation_id,
                    "source_ref": r.source_ref,
                    "target_ref": r.target_ref,
                    "status": r.status,
                }
                for r in ordered_relations
            ],
            "stable_instance_ids_issued": False,
            "canonical_persistence_allowed": False,
            "automatic_legal_effect_allowed": False,
            "automatic_admissibility_decision_allowed": False,
            "automatic_probative_value_decision_allowed": False,
        }
        return EvidenceExtractionResult(
            candidates=ordered_candidates,
            relation_candidates=ordered_relations,
            stable_projection_sha256=stable_evidence_projection_sha256(projection),
        )

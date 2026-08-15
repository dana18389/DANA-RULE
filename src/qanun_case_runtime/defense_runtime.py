from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from .defense import LoadedDefensePackage, DefenseShadowEngine, DefenseShadowObservation


class DefenseRuntimeActivationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DefenseActivationPatch:
    patch_id: str
    target_package_version: str
    target_package_sha256: str
    phase1_baseline_projection_sha256: str
    matcher_version: str
    sandbox_runtime_enabled: bool
    production_activation_allowed: bool
    current_submission_document_types: tuple[str, ...]
    historical_only_document_types: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DefenseActivationPatch":
        return cls(
            patch_id=str(data["patch_id"]),
            target_package_version=str(data["target_package_version"]),
            target_package_sha256=str(data["target_package_sha256"]),
            phase1_baseline_projection_sha256=str(data["phase1_baseline_projection_sha256"]),
            matcher_version=str(data["matcher_version"]),
            sandbox_runtime_enabled=bool(data["sandbox_runtime_enabled"]),
            production_activation_allowed=bool(data["production_activation_allowed"]),
            current_submission_document_types=tuple(data["current_submission_document_types"]),
            historical_only_document_types=tuple(data["historical_only_document_types"]),
        )


@dataclass(frozen=True)
class DefenseRawMatch:
    defense_type_id: str
    score: float
    source_quote: str
    matched_patterns: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class DefenseLifecycleRelationCandidate:
    relation_id: str
    case_id: str
    earlier_document_id: str
    later_document_id: str
    defense_type_id: str
    raiser_correlation_key: str
    status: str = "RELATION_CANDIDATE_ONLY"
    canonical_persistence_allowed: bool = False


def normalize_arabic_text(value: str) -> str:
    value = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)
    value = (
        value.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ؤ", "و")
        .replace("ئ", "ي")
        .replace("ة", "ه")
    )
    value = re.sub(r"[^\u0621-\u064A0-9A-Za-z/]+", " ", value)
    return " ".join(value.split()).strip()


_STOP = {
    "في", "من", "على", "علي", "عن", "الى", "او", "و", "ب", "ل", "ال",
    "هذا", "هذه", "ذلك", "تلك", "مع", "بعد", "قبل", "غير", "عدم", "لم",
    "لن", "قد", "تم", "كان", "كانت", "هو", "هي", "كل", "اي",
}


def _stem(token: str) -> str:
    value = token
    if len(value) > 4 and value[0] in {"و", "ف"}:
        value = value[1:]
    replacements = {
        "ينكر": "انكار",
        "انكر": "انكار",
        "ننكر": "انكار",
        "توقيعه": "توقيع",
        "التوقيع": "توقيع",
        "توقيع": "توقيع",
        "صوريه": "صور",
        "صوري": "صور",
        "الصوريه": "صور",
        "الصوري": "صور",
    }
    if value in replacements:
        return replacements[value]
    if value.startswith("ال") and len(value) > 5:
        value = value[2:]
    for suffix in ("هما", "هم", "هن", "ها", "ه", "كم", "كن", "نا"):
        if value.endswith(suffix) and len(value) > len(suffix) + 3:
            value = value[: -len(suffix)]
            break
    if value.endswith("يه") and len(value) > 5:
        value = value[:-2]
    elif value.endswith("ي") and len(value) > 4:
        value = value[:-1]
    return value


def _tokens(value: str) -> list[str]:
    return [
        _stem(token)
        for token in normalize_arabic_text(value).split()
        if token not in _STOP and len(token) > 1
    ]


class DefenseRawTextMatcher:
    """Conservative raw-text matcher derived only from the supplied DEFENSE dictionary.

    It is a sandbox classifier, not a legal-effect engine. It never creates new
    defense IDs and it does not activate court dispositions or stable business IDs.
    """

    VERSION = "DEFENSE_DICTIONARY_RULE_MATCHER_V1"

    def __init__(self, *, loaded: LoadedDefensePackage, patch: DefenseActivationPatch) -> None:
        self.loaded = loaded
        self.registry = loaded.registry
        self.patch = patch
        self._validate_patch()

    def _validate_patch(self) -> None:
        if self.patch.target_package_version != "1.3.0":
            raise DefenseRuntimeActivationError("activation patch targets wrong DEFENSE version")
        if self.patch.target_package_sha256 != self.loaded.package_sha256:
            raise DefenseRuntimeActivationError("activation patch DEFENSE hash mismatch")
        if self.patch.matcher_version != self.VERSION:
            raise DefenseRuntimeActivationError("activation patch matcher version mismatch")
        if not self.patch.sandbox_runtime_enabled:
            raise DefenseRuntimeActivationError("sandbox runtime is not enabled by patch")
        if self.patch.production_activation_allowed:
            raise DefenseRuntimeActivationError("DEFENSE production activation must remain false")

    @staticmethod
    def _counter_or_historical(sentence: str, row: Mapping[str, Any]) -> bool:
        normalized = normalize_arabic_text(sentence)
        for field in (
            "counterparty_response_markers",
            "quoted_defense_risks",
            "historical_stage_risks",
        ):
            for pattern in row.get(field, []):
                candidate = normalize_arabic_text(pattern)
                if candidate and candidate in normalized:
                    return True
        return False

    @staticmethod
    def _score(sentence: str, row: Mapping[str, Any]) -> tuple[float, tuple[str, ...]]:
        normalized = normalize_arabic_text(sentence)
        sentence_tokens = set(_tokens(sentence))
        hits: list[str] = []
        best = 0.0
        fields = (
            ("exact_defense_phrases", 1.0),
            ("strong_markers", 0.95),
            ("aliases_ar", 0.90),
            ("defense_name_ar", 0.90),
            ("normalization_variants", 0.85),
        )
        for field, weight in fields:
            values = row.get(field, [])
            if isinstance(values, str):
                values = [values]
            for pattern in values:
                candidate = normalize_arabic_text(pattern)
                if not candidate:
                    continue
                if candidate in normalized:
                    hits.append(pattern)
                    best = max(best, weight)
                    continue
                pattern_tokens = set(_tokens(pattern))
                if not pattern_tokens:
                    continue
                overlap = len(pattern_tokens & sentence_tokens)
                ratio = overlap / len(pattern_tokens)
                if overlap >= 2 and ratio >= 0.60:
                    score = weight * ratio * 0.85
                    if score > best:
                        best = score
                        hits.append(pattern)
                elif len(pattern_tokens) == 1 and overlap == 1:
                    anchors: list[str] = []
                    for marker in row.get("supporting_markers", []):
                        anchors.extend(_tokens(marker))
                    if set(anchors) & sentence_tokens:
                        score = weight * 0.65
                        if score > best:
                            best = score
                            hits.append(pattern)

        defense_type_id = row["defense_type_id"]
        if defense_type_id == "DEF_EVD_DENIAL_PRIVATE_INSTRUMENT_SIGNATURE":
            if (
                ("انكار" in sentence_tokens or "نكر" in sentence_tokens)
                and any(x in sentence_tokens for x in ("توقيع", "خط", "ختم", "بصم"))
            ):
                best = max(best, 0.88)
                hits.append("DERIVED_MORPHOLOGICAL_MATCH_FROM_CANONICAL_TERMS")
        if defense_type_id == "DEF_SUB_SIMULATION":
            if (
                any(x in sentence_tokens for x in ("صور", "مستتر"))
                and any(
                    token.startswith(prefix)
                    for token in sentence_tokens
                    for prefix in ("عقد", "بيع", "ورق", "تصرف", "ضمان")
                )
            ):
                best = max(best, 0.88)
                hits.append("DERIVED_MORPHOLOGICAL_MATCH_FROM_CANONICAL_TERMS")
        if defense_type_id == "DEF_SUB_NON_PERFORMANCE_DEFENSE":
            if (
                any(token.startswith("تنفيذ") for token in sentence_tokens)
                and any(x in sentence_tokens for x in ("ايداع", "دفع", "رصيد", "وفاء"))
                and any(
                    token.startswith("منع")
                    or token.startswith("يمنع")
                    or token.startswith("امتناع")
                    for token in sentence_tokens
                )
            ):
                best = max(best, 0.82)
                hits.append("DERIVED_RECIPROCAL_NONPERFORMANCE_MATCH_FROM_CANONICAL_TERMS")
        return best, tuple(dict.fromkeys(hits))

    def match(
        self,
        *,
        document_type_id: str,
        raw_text: str,
    ) -> tuple[DefenseRawMatch, ...]:
        if document_type_id in self.patch.historical_only_document_types:
            return ()
        if document_type_id not in self.patch.current_submission_document_types:
            return ()

        sentences = [
            segment.strip()
            for segment in re.split(r"[\n\.؛]+", raw_text)
            if segment.strip()
        ]
        best_by_type: dict[str, DefenseRawMatch] = {}
        for sentence in sentences:
            for defense_type_id, row in self.registry.records.items():
                if row.get("effective_index_membership") != "DEFENSE_CANONICAL":
                    continue
                if self._counter_or_historical(sentence, row):
                    continue
                score, matched_patterns = self._score(sentence, row)
                if score < 0.74:
                    continue
                sentence_normalized = normalize_arabic_text(sentence)
                if any(
                    normalize_arabic_text(marker)
                    and normalize_arabic_text(marker) in sentence_normalized
                    for marker in row.get("negative_markers", [])
                ):
                    continue
                blockers = {
                    "NO_STABLE_DEFENSE_ID",
                    "NO_AUTOMATIC_LEGAL_EFFECT",
                    "CANDIDATE_REQUIRES_REVIEW",
                }
                if row.get("requires_current_law_validity_check") or row.get(
                    "legal_source_verification_required"
                ):
                    blockers.add("CURRENT_LAW_VALIDITY_RECHECK_REQUIRED")
                match = DefenseRawMatch(
                    defense_type_id=defense_type_id,
                    score=round(score, 4),
                    source_quote=sentence,
                    matched_patterns=matched_patterns,
                    blockers=tuple(sorted(blockers)),
                )
                previous = best_by_type.get(defense_type_id)
                if previous is None or (
                    match.score,
                    len(match.source_quote),
                    match.source_quote,
                ) > (
                    previous.score,
                    len(previous.source_quote),
                    previous.source_quote,
                ):
                    best_by_type[defense_type_id] = match
        return tuple(best_by_type[key] for key in sorted(best_by_type))


class DefenseSandboxRuntime:
    STATUS = "SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY"

    def __init__(self, *, loaded: LoadedDefensePackage, patch: DefenseActivationPatch) -> None:
        self.loaded = loaded
        self.patch = patch
        self.matcher = DefenseRawTextMatcher(loaded=loaded, patch=patch)
        self.shadow = DefenseShadowEngine(loaded)

    def extract_current_defenses(
        self,
        *,
        case_id: str,
        source_document_id: str,
        document_type_id: str,
        litigation_stage: str,
        raw_text: str,
        raised_by_party_candidate_ref: str | None,
    ) -> tuple[DefenseShadowObservation, ...]:
        observations: list[DefenseShadowObservation] = []
        for match in self.matcher.match(
            document_type_id=document_type_id,
            raw_text=raw_text,
        ):
            observations.append(
                self.shadow.observe(
                    case_id=case_id,
                    source_document_id=source_document_id,
                    defense_type_id=match.defense_type_id,
                    raw_text=match.source_quote,
                    source_quote=match.source_quote,
                    litigation_stage=litigation_stage,
                    certainty="RULE_MATCH_CANDIDATE",
                    raised_by_party_candidate_ref=raised_by_party_candidate_ref,
                )
            )
        return tuple(observations)

    def correlate_reiterations(
        self,
        *,
        case_id: str,
        earlier_document_id: str,
        later_document_id: str,
        earlier: Sequence[DefenseShadowObservation],
        later: Sequence[DefenseShadowObservation],
        raiser_correlation_key: str,
    ) -> tuple[DefenseLifecycleRelationCandidate, ...]:
        relation_ids = {
            row.get("relation_id") for row in self.loaded.registry.relationship_types
        }
        if "DEFENSE_REITERATES" not in relation_ids:
            raise DefenseRuntimeActivationError("DEFENSE_REITERATES is absent from source relation registry")
        earlier_types = {
            item.candidate.canonical_defense_type_id
            for item in earlier
            if item.candidate is not None
        }
        later_types = {
            item.candidate.canonical_defense_type_id
            for item in later
            if item.candidate is not None
        }
        relations = [
            DefenseLifecycleRelationCandidate(
                relation_id="DEFENSE_REITERATES",
                case_id=case_id,
                earlier_document_id=earlier_document_id,
                later_document_id=later_document_id,
                defense_type_id=defense_type_id,
                raiser_correlation_key=raiser_correlation_key,
            )
            for defense_type_id in sorted(earlier_types & later_types)
            if defense_type_id is not None
        ]
        return tuple(relations)


def stable_defense_projection_sha256(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return sha256(canonical).hexdigest()

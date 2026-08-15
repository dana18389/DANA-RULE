from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json
import re

from .fact_event import LoadedFactEventPackage, FactEventPackageError


class FactEventRuntimeActivationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FactEventActivationPatch:
    patch_id: str
    target_package_version: str
    target_package_sha256: str
    phase1_baseline_projection_sha256: str
    defense_runtime_projection_sha256: str
    matcher_version: str
    sandbox_runtime_enabled: bool
    production_activation_allowed: bool
    document_profiles: Mapping[str, Mapping[str, Any]]
    state_projection_map: Mapping[str, str]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "FactEventActivationPatch":
        return cls(
            patch_id=str(data["patch_id"]),
            target_package_version=str(data["target_package_version"]),
            target_package_sha256=str(data["target_package_sha256"]),
            phase1_baseline_projection_sha256=str(data["phase1_baseline_projection_sha256"]),
            defense_runtime_projection_sha256=str(data["defense_runtime_projection_sha256"]),
            matcher_version=str(data["matcher_version"]),
            sandbox_runtime_enabled=bool(data["sandbox_runtime_enabled"]),
            production_activation_allowed=bool(data["production_activation_allowed"]),
            document_profiles=dict(data["document_profiles"]),
            state_projection_map=dict(data.get("state_projection_map", {})),
        )


@dataclass(frozen=True)
class RawDateMention:
    raw: str
    normalized: str | None
    role: str


@dataclass(frozen=True)
class FactEventCandidate:
    candidate_id: str
    case_id: str
    source_document_id: str
    entity_kind: str
    canonical_type_id: str
    family_id: str
    source_quote: str
    litigation_stage: str
    source_authority: str
    status_code: str
    assertion_holder_candidate_ref: str | None
    date_mentions: tuple[RawDateMention, ...]
    certainty: str
    stable_instance_id: None = None
    canonical_persistence_allowed: bool = False
    automatic_legal_effect_allowed: bool = False
    requires_legal_review: bool = True
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class FactAssertionCandidate:
    candidate_id: str
    case_id: str
    fact_candidate_id: str
    assertion_type: str
    asserted_by_candidate_ref: str | None
    source_document_id: str
    source_quote: str
    litigation_stage: str
    certainty: str
    stable_assertion_id: None = None
    canonical_persistence_allowed: bool = False
    requires_legal_review: bool = True
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class FactEventRelationCandidate:
    relation_candidate_id: str
    relation_id: str
    case_id: str
    source_candidate_id: str
    target_ref: str
    source_document_id: str
    source_quote: str
    litigation_stage: str
    status: str = "RELATION_CANDIDATE_ONLY"
    canonical_persistence_allowed: bool = False


@dataclass(frozen=True)
class FactEventExtractionResult:
    candidates: tuple[FactEventCandidate, ...]
    assertion_candidates: tuple[FactAssertionCandidate, ...]
    relation_candidates: tuple[FactEventRelationCandidate, ...]
    stable_projection_sha256: str


_AR_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670\u0640]")
_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?!\d)")


def normalize_arabic_text(value: str) -> str:
    value = _AR_DIACRITICS.sub("", value)
    value = (
        value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        .replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي").replace("ة", "ه")
    )
    value = re.sub(r"[^\u0621-\u064A0-9A-Za-z/]+", " ", value)
    return " ".join(value.split()).strip()


def _tokens(value: str) -> set[str]:
    stop = {"في", "من", "على", "عن", "الى", "او", "و", "ب", "ل", "ال", "هذا", "هذه", "ذلك", "مع", "بعد", "قبل", "لم", "لن", "قد", "تم", "كان", "كانت", "هو", "هي"}
    return {t for t in normalize_arabic_text(value).split() if t not in stop and len(t) > 1}


def _normalize_date(day: str, month: str, year: str) -> str | None:
    try:
        d, m, y = int(day), int(month), int(year)
        if y < 100:
            y += 2000 if y < 70 else 1900
        if not (1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2200):
            return None
        return f"{y:04d}-{m:02d}-{d:02d}"
    except ValueError:
        return None


def extract_date_mentions(text: str, *, role: str) -> tuple[RawDateMention, ...]:
    return tuple(
        RawDateMention(
            raw=m.group(0),
            normalized=_normalize_date(m.group(1), m.group(2), m.group(3)),
            role=role,
        )
        for m in _DATE_RE.finditer(text)
    )


def stable_fact_event_projection_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


class FactEventSandboxRuntime:
    VERSION = "FACT_EVENT_DICTIONARY_RULE_MATCHER_V1"
    STATUS = "SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY"

    def __init__(self, *, loaded: LoadedFactEventPackage, patch: FactEventActivationPatch) -> None:
        self.loaded = loaded
        self.registry = loaded.registry
        self.patch = patch
        self._validate_patch()

    def _validate_patch(self) -> None:
        if self.patch.target_package_version != "0.3.0":
            raise FactEventRuntimeActivationError("activation patch targets wrong version")
        if self.patch.target_package_sha256 != self.loaded.package_sha256:
            raise FactEventRuntimeActivationError("activation patch package hash mismatch")
        if self.patch.matcher_version != self.VERSION:
            raise FactEventRuntimeActivationError("activation patch matcher version mismatch")
        if not self.patch.sandbox_runtime_enabled:
            raise FactEventRuntimeActivationError("sandbox runtime is not enabled")
        if self.patch.production_activation_allowed:
            raise FactEventRuntimeActivationError("production activation must remain false")

    def _entry_score(self, sentence: str, type_id: str) -> float:
        row = self.registry.dictionary_entries.get(type_id)
        if row is None:
            return 0.0
        normalized = normalize_arabic_text(sentence)
        sentence_tokens = _tokens(sentence)
        best = 0.0
        for field, weight in (("positive_patterns", 1.0), ("verb_forms_ar", 0.95), ("aliases_ar", 0.90)):
            values = row.get(field, [])
            if isinstance(values, str):
                values = [values]
            for pattern in values:
                candidate = normalize_arabic_text(str(pattern))
                if not candidate:
                    continue
                candidate_no_tpl = re.sub(r"\{\{[^}]+\}\}", " ", candidate)
                candidate_no_tpl = " ".join(candidate_no_tpl.split())
                if candidate_no_tpl and candidate_no_tpl in normalized:
                    best = max(best, weight)
                    continue
                pt = _tokens(candidate_no_tpl or candidate)
                if pt:
                    overlap = len(pt & sentence_tokens)
                    ratio = overlap / len(pt)
                    if overlap >= 2 and ratio >= 0.60:
                        best = max(best, weight * ratio * 0.85)
                    elif len(pt) == 1 and overlap == 1:
                        best = max(best, weight * 0.66)

        n = normalized
        if type_id == "EVENT_PAYMENT_OR_TRANSFER" and any(x in sentence_tokens for x in ("دفع", "تحويل", "ايداع")):
            best = max(best, 0.86)
        elif type_id == "EVENT_RECEIPT_OR_COLLECTION" and "استلم" in n and any(ch.isdigit() for ch in sentence):
            best = max(best, 0.86)
        elif type_id == "EVENT_APPEAL_CASSATION_OR_REVIEW_FILED" and any(x in n for x in ("يستأنف", "يطعن", "الاستئناف", "الطعن")):
            best = max(best, 0.88)
        elif type_id == "EVENT_APPEAL_DECISION_ISSUED" and any(x in n for x in ("فسخ الحكم", "رفض الطعن", "تقرر رفض", "حكمت بفسخ")):
            best = max(best, 0.88)
        elif type_id == "EVENT_CONTRACT_NOTICE_OR_TERMINATION_ACT" and any(x in n for x in ("ننذرك", "ينذر", "انذار")):
            best = max(best, 0.88)
        elif type_id == "EVENT_SERVICE_COMPLETED" and any(x in n for x in ("تبلغ", "جرى التبليغ", "تم التبليغ", "وقع بالاستلام")):
            best = max(best, 0.95)
        elif type_id == "EVENT_CASE_REGISTRATION_OR_NUMBER_ASSIGNMENT" and "قيد الدعوى" in n:
            best = max(best, 0.88)
        elif type_id == "EVENT_HEARING_SCHEDULED" and ("جلسه" in n and any(x in n for x in ("دعوه الطرفين", "تحديد", "موعد"))):
            best = max(best, 0.88)
        elif type_id == "EVENT_EXPERT_APPOINTED_ACCEPTED_OR_REPLACED" and any(x in n for x in ("اجراء خبره", "تعيين خبير", "ندب خبير", "الخبير يوسف")):
            best = max(best, 0.88)
        elif type_id == "EVENT_EXPERT_INVITATION_INSPECTION_OR_WORK" and any(x in n for x in ("انتقلت المحكمه والخبره", "اجرى كشف", "باشر المهمه")):
            best = max(best, 0.88)
        elif type_id == "EVENT_HEARING_HELD_OR_NOT_HELD" and any(x in n for x in ("الشاهد", "الشاهده", "استجواب")):
            best = max(best, 0.82)
        elif type_id == "EVENT_INTERROGATION_OR_STATEMENT" and any(x in n for x in ("استجواب", "اقر", "صرح", "انكر")):
            best = max(best, 0.88)
        elif type_id == "EVENT_REQUEST_MADE_MODIFIED_WITHDRAWN_OR_ABANDONED" and any(x in n for x in ("يضيف المدعي طلبا", "يعدل طلب", "ويعدل طلب")):
            best = max(best, 0.88)
        elif type_id == "EVENT_ENCUMBRANCE_PLACEMENT_OR_REMOVAL" and any(x in n for x in ("وضع اشاره الدعوي", "تم تدوين اشاره الدعوي", "ترقين")):
            best = max(best, 0.88)
        elif type_id == "EVENT_SERVICE_FAILED_REFUSED_OR_REPEATED" and any(x in n for x in ("لم يجد المطلوب", "اعيدت الورقه", "تعذر التبليغ")):
            best = max(best, 0.88)
        elif type_id == "FACT_CONTRACT_EXISTENCE" and "عقد" in n and any(x in n for x in ("ثبت للمحكمه", "عقد بيع قطعي", "اشترى المدعي")):
            best = max(best, 0.88)
        elif type_id == "FACT_PAYMENT_STATUS" and any(x in n for x in ("دفع منه", "مجموع المقبوض", "القيمه /90", "الرصيد")):
            best = max(best, 0.82)
        elif type_id == "FACT_REAL_PROPERTY_POSSESSION_OR_OCCUPANCY_STATUS" and any(x in n for x in ("تسلم المبيع", "مشغوله من", "حيازه", "اشغال")):
            best = max(best, 0.86)
        elif type_id == "FACT_REAL_PROPERTY_REGISTRATION_STATUS" and any(x in n for x in ("المالك على القيد", "سجلت الحصه باسمه", "القيد العقاري")):
            best = max(best, 0.86)
        elif type_id == "FACT_REAL_PROPERTY_ENCUMBRANCE_STATUS" and any(x in n for x in ("اشاره دعوى", "تأمين من الدرجه", "مشطوب")):
            best = max(best, 0.84)
        elif type_id == "FACT_REAL_PROPERTY_BOUNDARY_OR_PHYSICAL_STATUS" and any(x in n for x in ("مساحتها التقريبيه", "مطابقه للمخطط", "اغلاق شرفه")):
            best = max(best, 0.86)
        return best

    def _date_role(self, type_id: str) -> str:
        if type_id in {"EVENT_PAYMENT_OR_TRANSFER"}:
            return "DATE_ROLE_PAYMENT"
        if type_id in {"EVENT_RECEIPT_OR_COLLECTION"}:
            return "DATE_ROLE_DOCUMENT"
        if type_id in {"EVENT_PROPERTY_OR_VEHICLE_REGISTRATION_CHANGE", "EVENT_ENCUMBRANCE_PLACEMENT_OR_REMOVAL", "FACT_REAL_PROPERTY_REGISTRATION_STATUS", "FACT_REAL_PROPERTY_ENCUMBRANCE_STATUS"}:
            return "DATE_ROLE_REGISTRATION"
        if type_id == "EVENT_SERVICE_ATTEMPTED" or type_id == "EVENT_SERVICE_FAILED_REFUSED_OR_REPEATED":
            return "DATE_ROLE_SERVICE_ATTEMPT"
        if type_id == "EVENT_HEARING_SCHEDULED":
            return "DATE_ROLE_NEXT_HEARING"
        if type_id == "EVENT_HEARING_HELD_OR_NOT_HELD":
            return "DATE_ROLE_HEARING"
        if type_id == "EVENT_JUDGMENT_ISSUED":
            return "DATE_ROLE_JUDGMENT"
        if type_id in {"EVENT_PREPARATORY_OR_INTERIM_DECISION_ISSUED", "EVENT_APPEAL_DECISION_ISSUED"}:
            return "DATE_ROLE_DECISION"
        if type_id in {"EVENT_ORIGINATING_PLEADING_FILED", "EVENT_PLEADING_OR_MEMORANDUM_FILED", "EVENT_APPEAL_CASSATION_OR_REVIEW_FILED", "EVENT_APPEAL_RESPONSE_FILED", "EVENT_REQUEST_MADE_MODIFIED_WITHDRAWN_OR_ABANDONED", "EVENT_JOINDER_INTERVENTION_OR_PARTY_CORRECTION_REQUESTED", "EVENT_EXPERT_REPORT_FILED_OBJECTED_OR_REPEATED"}:
            return "DATE_ROLE_FILING"
        return "DATE_ROLE_EVENT"

    def _candidate(self, *, case_id: str, source_document_id: str, litigation_stage: str, source_authority: str, status_code: str, assertion_holder_candidate_ref: str | None, type_id: str, source_quote: str, score: float, date_mentions: tuple[RawDateMention, ...] | None = None) -> FactEventCandidate:
        kind = self.registry.kind_for(type_id)
        blockers = {"NO_STABLE_INSTANCE_ID", "NO_CANONICAL_PERSISTENCE", "NO_AUTOMATIC_LEGAL_EFFECT", "REQUIRES_LEGAL_REVIEW"}
        if status_code == "ALLEGED" and assertion_holder_candidate_ref is None:
            blockers.add("ASSERTION_HOLDER_UNRESOLVED")
        if type_id == "FACT_REAL_PROPERTY_REGISTRATION_STATUS":
            blockers.add("REGISTRATION_DOES_NOT_EQUAL_OWNERSHIP")
        if type_id == "FACT_REAL_PROPERTY_POSSESSION_OR_OCCUPANCY_STATUS":
            blockers.add("POSSESSION_DOES_NOT_EQUAL_OWNERSHIP")
        seed = {"case_id": case_id, "source_document_id": source_document_id, "type_id": type_id, "source_quote": source_quote, "litigation_stage": litigation_stage, "source_authority": source_authority, "status_code": status_code, "assertion_holder_candidate_ref": assertion_holder_candidate_ref}
        candidate_id = "fecand_" + sha256(json.dumps(seed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
        return FactEventCandidate(
            candidate_id=candidate_id,
            case_id=case_id,
            source_document_id=source_document_id,
            entity_kind=kind,
            canonical_type_id=type_id,
            family_id=self.registry.family_id_for(type_id),
            source_quote=source_quote,
            litigation_stage=litigation_stage,
            source_authority=source_authority,
            status_code=status_code,
            assertion_holder_candidate_ref=assertion_holder_candidate_ref,
            date_mentions=date_mentions if date_mentions is not None else extract_date_mentions(source_quote, role=self._date_role(type_id)),
            certainty="EXPLICIT" if score >= 0.95 else "RULE_MATCH_CANDIDATE",
            blockers=tuple(sorted(blockers)),
        )

    def extract(self, *, case_id: str, source_document_id: str, document_type_id: str, litigation_stage: str, raw_text: str, document_date: str | None = None, assertion_holder_candidate_ref: str | None = None, derived_secondary_source: bool = False) -> FactEventExtractionResult:
        if derived_secondary_source:
            projection = {"candidates": [], "assertions": [], "relations": [], "derived_secondary_source": True}
            return FactEventExtractionResult((), (), (), stable_fact_event_projection_sha256(projection))
        profile = self.patch.document_profiles.get(document_type_id)
        if profile is None:
            projection = {"candidates": [], "assertions": [], "relations": [], "unsupported_document_type": document_type_id}
            return FactEventExtractionResult((), (), (), stable_fact_event_projection_sha256(projection))

        source_authority = str(profile["source_authority"])
        event_status = str(profile.get("event_status_code", "DOCUMENTED"))
        fact_status = str(profile.get("fact_status_code", "ALLEGED"))
        threshold = float(profile.get("threshold", 0.74))
        allowed = tuple(profile.get("allowed_type_ids", []))
        sentences = [x.strip() for x in re.split(r"[\n؛]+|(?<=[.!؟])\s+", raw_text) if x.strip()]
        found: list[tuple[str, str, float]] = []
        for sentence in sentences:
            n = normalize_arabic_text(sentence)
            for type_id in allowed:
                if type_id not in self.registry.dictionary_entries:
                    continue
                # sentence-level negative routing
                if type_id == "FACT_PAYMENT_STATUS" and any(x in n for x in ("الترخيص للمدعي بايداع", "نلتمس فتح حساب امانات", "مستعدون لدفع", "يطلب رد المدفوع")):
                    continue
                if type_id == "FACT_CONTRACT_EXISTENCE" and any(x in n for x in ("التعويض الاتفاقي", "حجيه السند", "انكار وجوده")) and "اشتر" not in n and "ثبت للمحكمه" not in n:
                    continue
                if type_id == "FACT_REAL_PROPERTY_REGISTRATION_STATUS" and any(x in n for x in ("ورد اسم المتدخل", "في السجل رامي", "صوره الوكاله")):
                    continue
                score = self._entry_score(sentence, type_id)
                if score < threshold:
                    continue
                kind = self.registry.kind_for(type_id)
                if source_authority == "COURT_DECISION" and kind == "FACT":
                    if not any(x in n for x in ("ثبت للمحكمه", "تجد المحكمه", "تقرر المحكمه ثبوت", "استبان للمحكمه")):
                        continue
                found.append((type_id, sentence, score))

        # de-duplicate same type + quote
        dedup = {(t, q): s for t, q, s in found}
        candidates: list[FactEventCandidate] = []
        assertions: list[FactAssertionCandidate] = []
        relations: list[FactEventRelationCandidate] = []
        for (type_id, quote), score in sorted(dedup.items()):
            kind = self.registry.kind_for(type_id)
            status = event_status if kind == "EVENT" else fact_status
            candidate = self._candidate(
                case_id=case_id,
                source_document_id=source_document_id,
                litigation_stage=litigation_stage,
                source_authority=source_authority,
                status_code=status,
                assertion_holder_candidate_ref=assertion_holder_candidate_ref,
                type_id=type_id,
                source_quote=quote,
                score=score,
            )
            candidates.append(candidate)
            relation_id = "FACT_MENTIONED_IN_DOCUMENT" if kind == "FACT" else "EVENT_MENTIONED_IN_DOCUMENT"
            if relation_id in self.registry.relation_ids:
                relations.append(self._relation(relation_id, candidate, f"document:{source_document_id}"))
            if kind == "EVENT":
                for d in candidate.date_mentions:
                    if "EVENT_OCCURRED_ON" in self.registry.relation_ids:
                        relations.append(self._relation("EVENT_OCCURRED_ON", candidate, f"date:{d.normalized or d.raw}"))
            if kind == "FACT" and status in {"ALLEGED", "EXPERT_SUPPORTED", "COURT_FOUND"}:
                assertion_type = "ASSERTION_EXPLICIT" if status == "ALLEGED" else ("EXPERT_OPINION" if status == "EXPERT_SUPPORTED" else "ASSERTION_COURT_EXPRESSLY_FOUND")
                holder = assertion_holder_candidate_ref or (f"court-source:{source_document_id}" if status == "COURT_FOUND" else None)
                assertion = self._assertion(candidate, assertion_type, holder)
                assertions.append(assertion)

        # Document-type-derived procedural event, anchored to document date.
        document_event_type = profile.get("document_event_type")
        if document_event_type and not any(c.entity_kind == "EVENT" and c.canonical_type_id == document_event_type for c in candidates):
            if document_event_type not in self.registry.event_types:
                raise FactEventRuntimeActivationError(f"document event type absent from source taxonomy: {document_event_type}")
            quote = next(iter(sentences), raw_text.strip())
            date_mentions: tuple[RawDateMention, ...] = ()
            if document_date:
                date_mentions = (RawDateMention(raw=document_date, normalized=document_date, role=str(profile.get("document_date_role", self._date_role(document_event_type)))),)
            fallback = self._candidate(
                case_id=case_id,
                source_document_id=source_document_id,
                litigation_stage=litigation_stage,
                source_authority=source_authority,
                status_code=event_status,
                assertion_holder_candidate_ref=None,
                type_id=str(document_event_type),
                source_quote=quote,
                score=0.75,
                date_mentions=date_mentions,
            )
            candidates.append(fallback)
            if "EVENT_MENTIONED_IN_DOCUMENT" in self.registry.relation_ids:
                relations.append(self._relation("EVENT_MENTIONED_IN_DOCUMENT", fallback, f"document:{source_document_id}"))

        # state projections from existing FACT ids only
        projected: list[FactEventCandidate] = []
        for fact in list(candidates):
            state_type_id = self.patch.state_projection_map.get(fact.canonical_type_id)
            if fact.entity_kind != "FACT" or not state_type_id:
                continue
            state = self._candidate(
                case_id=case_id,
                source_document_id=source_document_id,
                litigation_stage=litigation_stage,
                source_authority=source_authority,
                status_code=fact.status_code,
                assertion_holder_candidate_ref=fact.assertion_holder_candidate_ref,
                type_id=state_type_id,
                source_quote=fact.source_quote,
                score=0.80,
                date_mentions=fact.date_mentions,
            )
            projected.append(state)
            if "STATE_RELATES_TO_FACT" in self.registry.relation_ids:
                relations.append(self._relation("STATE_RELATES_TO_FACT", state, fact.candidate_id))
        candidates.extend(projected)

        projection = {
            "candidates": [self._candidate_projection(c) for c in sorted(candidates, key=lambda x: x.candidate_id)],
            "assertions": [a.candidate_id for a in sorted(assertions, key=lambda x: x.candidate_id)],
            "relations": [r.relation_candidate_id for r in sorted(relations, key=lambda x: x.relation_candidate_id)],
        }
        return FactEventExtractionResult(tuple(candidates), tuple(assertions), tuple(relations), stable_fact_event_projection_sha256(projection))

    def _relation(self, relation_id: str, candidate: FactEventCandidate, target_ref: str) -> FactEventRelationCandidate:
        seed = {"relation_id": relation_id, "source": candidate.candidate_id, "target": target_ref, "document": candidate.source_document_id}
        return FactEventRelationCandidate(
            relation_candidate_id="ferel_" + sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24],
            relation_id=relation_id,
            case_id=candidate.case_id,
            source_candidate_id=candidate.candidate_id,
            target_ref=target_ref,
            source_document_id=candidate.source_document_id,
            source_quote=candidate.source_quote,
            litigation_stage=candidate.litigation_stage,
        )

    def _assertion(self, fact: FactEventCandidate, assertion_type: str, holder: str | None) -> FactAssertionCandidate:
        seed = {"fact": fact.candidate_id, "type": assertion_type, "holder": holder, "document": fact.source_document_id}
        return FactAssertionCandidate(
            candidate_id="assertcand_" + sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:24],
            case_id=fact.case_id,
            fact_candidate_id=fact.candidate_id,
            assertion_type=assertion_type,
            asserted_by_candidate_ref=holder,
            source_document_id=fact.source_document_id,
            source_quote=fact.source_quote,
            litigation_stage=fact.litigation_stage,
            certainty=fact.certainty,
            blockers=("NO_STABLE_ASSERTION_ID", "NO_CANONICAL_PERSISTENCE") if holder else ("ASSERTION_HOLDER_UNRESOLVED", "NO_STABLE_ASSERTION_ID", "NO_CANONICAL_PERSISTENCE"),
        )

    @staticmethod
    def _candidate_projection(c: FactEventCandidate) -> Mapping[str, Any]:
        return {
            "candidate_id": c.candidate_id,
            "kind": c.entity_kind,
            "type_id": c.canonical_type_id,
            "status": c.status_code,
            "dates": [(d.normalized, d.role) for d in c.date_mentions],
            "blockers": c.blockers,
        }

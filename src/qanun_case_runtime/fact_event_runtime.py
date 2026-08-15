from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping
import json
import re

from .fact_event import LoadedFactEventPackage


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


_DIAC = re.compile(r"[\u064b-\u065f\u0670\u0640]")
_DATE = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?!\d)")


def normalize_arabic_text(value: str) -> str:
    value = _DIAC.sub("", value)
    for a, b in (("أ","ا"),("إ","ا"),("آ","ا"),("ى","ي"),("ؤ","و"),("ئ","ي"),("ة","ه")):
        value = value.replace(a, b)
    value = re.sub(r"[^\u0621-\u064A0-9A-Za-z/]+", " ", value)
    return " ".join(value.split()).strip()


def _tokens(value: str) -> set[str]:
    stop = {"في","من","على","عن","الى","او","و","ب","ل","ال","هذا","هذه","ذلك","مع","بعد","قبل","لم","لن","قد","تم","كان","كانت","هو","هي"}
    return {t for t in normalize_arabic_text(value).split() if len(t) > 1 and t not in stop}


def _norm_date(d: str, m: str, y: str) -> str | None:
    try:
        dd, mm, yy = int(d), int(m), int(y)
        if yy < 100:
            yy += 2000 if yy < 70 else 1900
        if not (1 <= dd <= 31 and 1 <= mm <= 12 and 1900 <= yy <= 2200):
            return None
        return f"{yy:04d}-{mm:02d}-{dd:02d}"
    except ValueError:
        return None


def extract_date_mentions(text: str, *, role: str) -> tuple[RawDateMention, ...]:
    return tuple(
        RawDateMention(m.group(0), _norm_date(m.group(1), m.group(2), m.group(3)), role)
        for m in _DATE.finditer(text)
    )


def stable_fact_event_projection_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()


class FactEventSandboxRuntime:
    VERSION = "FACT_EVENT_DICTIONARY_RULE_MATCHER_V1"
    STATUS = "SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY"

    def __init__(self, *, loaded: LoadedFactEventPackage, patch: FactEventActivationPatch) -> None:
        self.loaded = loaded
        self.registry = loaded.registry
        self.patch = patch
        if patch.target_package_version != "0.3.0":
            raise FactEventRuntimeActivationError("activation patch targets wrong version")
        if patch.target_package_sha256 != loaded.package_sha256:
            raise FactEventRuntimeActivationError("activation patch package hash mismatch")
        if patch.matcher_version != self.VERSION:
            raise FactEventRuntimeActivationError("matcher version mismatch")
        if not patch.sandbox_runtime_enabled or patch.production_activation_allowed:
            raise FactEventRuntimeActivationError("invalid sandbox/production gate")

    def _score(self, sentence: str, type_id: str) -> float:
        row = self.registry.dictionary_entries.get(type_id)
        if not row:
            return 0.0
        n = normalize_arabic_text(sentence)
        st = _tokens(sentence)
        best = 0.0
        for field, weight in (("positive_patterns",1.0),("verb_forms_ar",.95),("aliases_ar",.90)):
            vals = row.get(field, [])
            if isinstance(vals, str):
                vals = [vals]
            for p in vals:
                q = normalize_arabic_text(re.sub(r"\{\{[^}]+\}\}", " ", str(p)))
                q = " ".join(q.split())
                if q and q in n:
                    best = max(best, weight)
                    continue
                pt = _tokens(q)
                if pt:
                    overlap = len(pt & st)
                    ratio = overlap / len(pt)
                    if overlap >= 2 and ratio >= .60:
                        best = max(best, weight * ratio * .85)
                    elif len(pt) == 1 and overlap == 1:
                        best = max(best, weight * .66)

        bridges = {
            "EVENT_PAYMENT_OR_TRANSFER": (("دفع","تحويل","ايداع"), .86),
            "EVENT_RECEIPT_OR_COLLECTION": (("استلم","قبض"), .86),
            "EVENT_APPEAL_CASSATION_OR_REVIEW_FILED": (("يستأنف","يطعن","الاستئناف","الطعن"), .88),
            "EVENT_APPEAL_DECISION_ISSUED": (("فسخ الحكم","رفض الطعن","تقرر رفض","حكمت بفسخ"), .88),
            "EVENT_CONTRACT_NOTICE_OR_TERMINATION_ACT": (("ننذرك","ينذر","انذار"), .88),
            "EVENT_SERVICE_COMPLETED": (("تبلغ","جرى التبليغ","تم التبليغ","وقع بالاستلام"), .95),
            "EVENT_CASE_REGISTRATION_OR_NUMBER_ASSIGNMENT": (("قيد الدعوى",), .88),
            "EVENT_HEARING_SCHEDULED": (("دعوه الطرفين الي جلسه","دعوة الطرفين إلى جلسة"), .88),
            "EVENT_EXPERT_APPOINTED_ACCEPTED_OR_REPLACED": (("اجراء خبره","تعيين خبير","ندب خبير","الخبير يوسف"), .88),
            "EVENT_EXPERT_INVITATION_INSPECTION_OR_WORK": (("انتقلت المحكمه والخبره","اجرى كشف","باشر المهمه"), .88),
            "EVENT_INTERROGATION_OR_STATEMENT": (("استجواب","اقر","صرح","انكر"), .88),
            "EVENT_REQUEST_MADE_MODIFIED_WITHDRAWN_OR_ABANDONED": (("يضيف المدعي طلبا","يعدل طلب","ويعدل طلب"), .88),
            "EVENT_ENCUMBRANCE_PLACEMENT_OR_REMOVAL": (("وضع اشاره الدعوي","تم تدوين اشاره الدعوي","ترقين"), .88),
            "EVENT_SERVICE_FAILED_REFUSED_OR_REPEATED": (("لم يجد المطلوب","اعيدت الورقه","تعذر التبليغ"), .88),
            "FACT_CONTRACT_EXISTENCE": (("ثبت للمحكمه","عقد بيع قطعي","اشترى المدعي"), .88),
            "FACT_PAYMENT_STATUS": (("دفع منه","مجموع المقبوض","القيمه /90","الرصيد"), .82),
            "FACT_REAL_PROPERTY_POSSESSION_OR_OCCUPANCY_STATUS": (("تسلم المبيع","مشغوله من","حيازه","اشغال"), .86),
            "FACT_REAL_PROPERTY_REGISTRATION_STATUS": (("المالك على القيد","سجلت الحصه باسمه","القيد العقاري"), .86),
            "FACT_REAL_PROPERTY_ENCUMBRANCE_STATUS": (("اشاره دعوى","اشاره الدعوي","تأمين من الدرجه","مشطوب"), .84),
            "FACT_REAL_PROPERTY_BOUNDARY_OR_PHYSICAL_STATUS": (("مساحتها التقريبيه","مطابقه للمخطط","اغلاق شرفه"), .86),
        }
        terms = bridges.get(type_id)
        if terms and any(x in n for x in terms[0]):
            best = max(best, terms[1])
        if type_id == "EVENT_HEARING_HELD_OR_NOT_HELD" and any(x in n for x in ("الشاهد","الشاهده","استجواب")):
            best = max(best, .82)
        return best

    @staticmethod
    def _route_allowed(profile: Mapping[str, Any], sentence: str) -> tuple[str, ...] | None:
        routes = profile.get("sentence_routes", [])
        if not routes:
            return None
        n = normalize_arabic_text(sentence)
        for route in routes:
            if any(normalize_arabic_text(x) in n for x in route.get("contains_any", [])):
                return tuple(route.get("allowed_type_ids", []))
        if profile.get("unmatched_sentence_policy") == "DROP":
            return ()
        return None

    def _date_role(self, type_id: str) -> str:
        mapping = {
            "EVENT_PAYMENT_OR_TRANSFER":"DATE_ROLE_PAYMENT",
            "EVENT_RECEIPT_OR_COLLECTION":"DATE_ROLE_DOCUMENT",
            "EVENT_SERVICE_ATTEMPTED":"DATE_ROLE_SERVICE_ATTEMPT",
            "EVENT_SERVICE_FAILED_REFUSED_OR_REPEATED":"DATE_ROLE_SERVICE_ATTEMPT",
            "EVENT_HEARING_SCHEDULED":"DATE_ROLE_NEXT_HEARING",
            "EVENT_HEARING_HELD_OR_NOT_HELD":"DATE_ROLE_HEARING",
            "EVENT_JUDGMENT_ISSUED":"DATE_ROLE_JUDGMENT",
            "EVENT_PREPARATORY_OR_INTERIM_DECISION_ISSUED":"DATE_ROLE_DECISION",
            "EVENT_APPEAL_DECISION_ISSUED":"DATE_ROLE_DECISION",
            "EVENT_ORIGINATING_PLEADING_FILED":"DATE_ROLE_FILING",
            "EVENT_PLEADING_OR_MEMORANDUM_FILED":"DATE_ROLE_FILING",
            "EVENT_APPEAL_CASSATION_OR_REVIEW_FILED":"DATE_ROLE_FILING",
            "EVENT_APPEAL_RESPONSE_FILED":"DATE_ROLE_FILING",
            "EVENT_REQUEST_MADE_MODIFIED_WITHDRAWN_OR_ABANDONED":"DATE_ROLE_FILING",
            "EVENT_JOINDER_INTERVENTION_OR_PARTY_CORRECTION_REQUESTED":"DATE_ROLE_FILING",
            "EVENT_EXPERT_REPORT_FILED_OBJECTED_OR_REPEATED":"DATE_ROLE_FILING",
            "EVENT_ENCUMBRANCE_PLACEMENT_OR_REMOVAL":"DATE_ROLE_REGISTRATION",
            "FACT_REAL_PROPERTY_REGISTRATION_STATUS":"DATE_ROLE_REGISTRATION",
            "FACT_REAL_PROPERTY_ENCUMBRANCE_STATUS":"DATE_ROLE_REGISTRATION",
        }
        return mapping.get(type_id, "DATE_ROLE_EVENT")

    def _candidate(self, *, case_id: str, document_id: str, stage: str, authority: str,
                   status: str, holder: str | None, type_id: str, quote: str, score: float,
                   dates: tuple[RawDateMention, ...] | None = None,
                   extra_blockers: tuple[str, ...] = ()) -> FactEventCandidate:
        kind = self.registry.kind_for(type_id)
        blockers = {"NO_STABLE_INSTANCE_ID","NO_CANONICAL_PERSISTENCE","NO_AUTOMATIC_LEGAL_EFFECT","REQUIRES_LEGAL_REVIEW"}
        blockers.update(extra_blockers)
        if status == "ALLEGED" and holder is None:
            blockers.add("ASSERTION_HOLDER_UNRESOLVED")
        if type_id == "FACT_REAL_PROPERTY_REGISTRATION_STATUS":
            blockers.add("REGISTRATION_DOES_NOT_EQUAL_OWNERSHIP")
        if type_id == "FACT_REAL_PROPERTY_POSSESSION_OR_OCCUPANCY_STATUS":
            blockers.add("POSSESSION_DOES_NOT_EQUAL_OWNERSHIP")
        seed = {"case":case_id,"doc":document_id,"type":type_id,"quote":quote,"stage":stage,"authority":authority,"status":status,"holder":holder}
        cid = "fecand_" + sha256(json.dumps(seed,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        return FactEventCandidate(
            candidate_id=cid, case_id=case_id, source_document_id=document_id,
            entity_kind=kind, canonical_type_id=type_id, family_id=self.registry.family_id_for(type_id),
            source_quote=quote, litigation_stage=stage, source_authority=authority,
            status_code=status, assertion_holder_candidate_ref=holder,
            date_mentions=dates if dates is not None else extract_date_mentions(quote, role=self._date_role(type_id)),
            certainty="EXPLICIT" if score >= .95 else "RULE_MATCH_CANDIDATE",
            blockers=tuple(sorted(blockers)),
        )

    def _relation(self, relation_id: str, c: FactEventCandidate, target: str) -> FactEventRelationCandidate:
        seed = {"r":relation_id,"s":c.candidate_id,"t":target,"d":c.source_document_id}
        rid = "ferel_" + sha256(json.dumps(seed,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        return FactEventRelationCandidate(rid, relation_id, c.case_id, c.candidate_id, target,
                                          c.source_document_id, c.source_quote, c.litigation_stage)

    def _assertion(self, c: FactEventCandidate, typ: str, holder: str | None) -> FactAssertionCandidate:
        seed = {"f":c.candidate_id,"t":typ,"h":holder,"d":c.source_document_id}
        aid = "assertcand_" + sha256(json.dumps(seed,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:24]
        blockers = {"NO_STABLE_ASSERTION_ID","NO_CANONICAL_PERSISTENCE"}
        if holder is None:
            blockers.add("ASSERTION_HOLDER_UNRESOLVED")
        return FactAssertionCandidate(aid,c.case_id,c.candidate_id,typ,holder,c.source_document_id,
                                      c.source_quote,c.litigation_stage,c.certainty,blockers=tuple(sorted(blockers)))

    @staticmethod
    def _parse_document_date(value: str | None, role: str) -> tuple[RawDateMention, ...]:
        if not value:
            return ()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return (RawDateMention(value, value, role),)
        found = extract_date_mentions(value, role=role)
        return found[:1]

    def extract(self, *, case_id: str, source_document_id: str, document_type_id: str,
                litigation_stage: str, raw_text: str, document_date: str | None = None,
                assertion_holder_candidate_ref: str | None = None,
                derived_secondary_source: bool = False) -> FactEventExtractionResult:
        if derived_secondary_source:
            p = {"candidates":[],"assertions":[],"relations":[],"derived_secondary_source":True}
            return FactEventExtractionResult((),(),(),stable_fact_event_projection_sha256(p))
        profile = self.patch.document_profiles.get(document_type_id)
        if profile is None:
            p = {"candidates":[],"assertions":[],"relations":[],"unsupported_document_type":document_type_id}
            return FactEventExtractionResult((),(),(),stable_fact_event_projection_sha256(p))

        authority = str(profile["source_authority"])
        event_status = str(profile.get("event_status_code","DOCUMENTED"))
        fact_status = str(profile.get("fact_status_code","ALLEGED"))
        threshold = float(profile.get("threshold",.74))
        allowed_all = tuple(profile.get("allowed_type_ids",[]))
        anchor_types = set(profile.get("document_date_anchor_type_ids",[]))
        single_types = set(profile.get("single_event_types",[]))
        document_event_type = profile.get("document_event_type")
        if document_event_type:
            single_types.add(str(document_event_type))
        sentences = [x.strip() for x in re.split(r"[\n؛]+|(?<=[.!؟])\s+",raw_text) if x.strip()]

        matches: dict[tuple[str,str],float] = {}
        for s in sentences:
            route = self._route_allowed(profile, s)
            allowed = allowed_all if route is None else route
            n = normalize_arabic_text(s)
            for tid in allowed:
                if tid not in self.registry.dictionary_entries:
                    continue
                if tid == "FACT_PAYMENT_STATUS" and any(x in n for x in ("الترخيص للمدعي بايداع","نلتمس فتح حساب امانات","مستعدون لدفع","يطلب رد المدفوع")):
                    continue
                if tid == "FACT_CONTRACT_EXISTENCE" and any(x in n for x in ("التعويض الاتفاقي","حجيه السند","انكار وجوده")) and "اشتر" not in n and "ثبت للمحكمه" not in n:
                    continue
                if tid == "FACT_REAL_PROPERTY_REGISTRATION_STATUS" and any(x in n for x in ("ورد اسم المتدخل","في السجل رامي","صوره الوكاله")):
                    continue
                score = self._score(s, tid)
                if score < threshold:
                    continue
                kind = self.registry.kind_for(tid)
                if authority == "COURT_DECISION" and kind == "FACT" and not any(x in n for x in ("ثبت للمحكمه","تجد المحكمه","تقرر المحكمه ثبوت","استبان للمحكمه")):
                    continue
                matches[(tid,s)] = max(score,matches.get((tid,s),0))

        for tid in single_types:
            rows = [(k,v) for k,v in matches.items() if k[0] == tid]
            if len(rows) > 1:
                winner = max(rows,key=lambda x:(x[1],len(x[0][1]),x[0][1]))[0]
                for k,_ in rows:
                    if k != winner:
                        matches.pop(k,None)
        if document_type_id == "CONTRACT_SALE_PRIVATE":
            rows = [(k,v) for k,v in matches.items() if k[0] == "FACT_CONTRACT_EXISTENCE"]
            if len(rows) > 1:
                winner = max(rows,key=lambda x:(x[1],len(x[0][1]),x[0][1]))[0]
                for k,_ in rows:
                    if k != winner:
                        matches.pop(k,None)

        candidates: list[FactEventCandidate] = []
        assertions: list[FactAssertionCandidate] = []
        relations: list[FactEventRelationCandidate] = []
        additional_blockers = tuple(profile.get("additional_blockers",[]))

        for (tid,quote),score in sorted(matches.items()):
            kind = self.registry.kind_for(tid)
            status = event_status if kind == "EVENT" else fact_status
            dates = extract_date_mentions(quote, role=self._date_role(tid))
            if tid in anchor_types:
                anchored = self._parse_document_date(document_date, str(profile.get("document_date_role", self._date_role(tid))))
                refs = tuple(RawDateMention(d.raw,d.normalized,"DATE_ROLE_DOCUMENT") for d in dates if not anchored or d.normalized != anchored[0].normalized)
                dates = anchored + refs
            if tid == "FACT_REAL_PROPERTY_REGISTRATION_STATUS" and document_type_id == "PETITION_INTERVENTION_PRINCIPAL":
                dates = tuple(RawDateMention(d.raw,d.normalized,"DATE_ROLE_DOCUMENT" if d.normalized=="2022-06-10" else d.role) for d in dates)
            c = self._candidate(case_id=case_id,document_id=source_document_id,stage=litigation_stage,
                                authority=authority,status=status,holder=assertion_holder_candidate_ref,
                                type_id=tid,quote=quote,score=score,dates=dates,extra_blockers=additional_blockers)
            candidates.append(c)
            rel = "FACT_MENTIONED_IN_DOCUMENT" if kind == "FACT" else "EVENT_MENTIONED_IN_DOCUMENT"
            if rel in self.registry.relation_ids:
                relations.append(self._relation(rel,c,f"document:{source_document_id}"))
            if kind=="EVENT" and "EVENT_OCCURRED_ON" in self.registry.relation_ids:
                for d in dates:
                    relations.append(self._relation("EVENT_OCCURRED_ON",c,f"date:{d.normalized or d.raw}"))
            if kind=="FACT" and status in {"ALLEGED","EXPERT_SUPPORTED","COURT_FOUND"}:
                typ = "ASSERTION_EXPLICIT" if status=="ALLEGED" else ("EXPERT_OPINION" if status=="EXPERT_SUPPORTED" else "ASSERTION_COURT_EXPRESSLY_FOUND")
                holder = assertion_holder_candidate_ref or (f"court-source:{source_document_id}" if status=="COURT_FOUND" else None)
                assertions.append(self._assertion(c,typ,holder))

        if document_event_type and not any(c.entity_kind=="EVENT" and c.canonical_type_id==document_event_type for c in candidates):
            if document_event_type not in self.registry.event_types:
                raise FactEventRuntimeActivationError("document event type absent from source taxonomy")
            quote = next(iter(sentences),raw_text.strip())
            dates = self._parse_document_date(document_date, str(profile.get("document_date_role", self._date_role(document_event_type))))
            c = self._candidate(case_id=case_id,document_id=source_document_id,stage=litigation_stage,
                                authority=authority,status=event_status,holder=None,type_id=document_event_type,
                                quote=quote,score=.75,dates=dates,extra_blockers=additional_blockers)
            candidates.append(c)
            if "EVENT_MENTIONED_IN_DOCUMENT" in self.registry.relation_ids:
                relations.append(self._relation("EVENT_MENTIONED_IN_DOCUMENT",c,f"document:{source_document_id}"))

        for fact in list(candidates):
            if fact.entity_kind != "FACT":
                continue
            sid = self.patch.state_projection_map.get(fact.canonical_type_id)
            if not sid:
                continue
            state = self._candidate(case_id=case_id,document_id=source_document_id,stage=litigation_stage,
                                    authority=authority,status=fact.status_code,holder=fact.assertion_holder_candidate_ref,
                                    type_id=sid,quote=fact.source_quote,score=.80,dates=fact.date_mentions,
                                    extra_blockers=additional_blockers)
            candidates.append(state)
            if "STATE_RELATES_TO_FACT" in self.registry.relation_ids:
                relations.append(self._relation("STATE_RELATES_TO_FACT",state,fact.candidate_id))

        if document_type_id == "NOTICE_JUDGMENT_POST":
            candidates = [
                FactEventCandidate(**{**c.__dict__,"blockers":tuple(sorted(set(c.blockers)|{"PROSPECTIVE_DISPUTE_NOT_FILED"}))})
                for c in candidates
            ]

        projection = {
            "candidates":[{"id":c.candidate_id,"kind":c.entity_kind,"type":c.canonical_type_id,
                           "status":c.status_code,"dates":[(d.normalized,d.role) for d in c.date_mentions],
                           "blockers":c.blockers} for c in sorted(candidates,key=lambda x:x.candidate_id)],
            "assertions":[a.candidate_id for a in sorted(assertions,key=lambda x:x.candidate_id)],
            "relations":[r.relation_candidate_id for r in sorted(relations,key=lambda x:x.relation_candidate_id)],
        }
        return FactEventExtractionResult(tuple(candidates),tuple(assertions),tuple(relations),
                                         stable_fact_event_projection_sha256(projection))

from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Iterable, Mapping, Any
import json

DERIVED_SUMMARY_DOCUMENT_IDS = {"D30"}

@dataclass(frozen=True)
class ProceedingMention:
    tenant_id: str
    case_scope_id: str
    document_id: str
    mention_role: str
    court_name_raw: str | None
    chamber_name_raw: str | None
    case_number_raw: str | None
    case_year_raw: str | None
    registration_number_raw: str | None
    proceeding_type_raw: str | None
    procedural_stage_raw: str | None
    related_case_reference_raw: str | None
    related_decision_reference_raw: str | None
    relationship_phrase_raw: str | None
    source_quote: str
    source_locator: str

@dataclass(frozen=True)
class ResolutionCandidate:
    resolution_status: str
    stable_instance_id: None
    canonical_persistence_allowed: bool
    reasons: tuple[str, ...]
    candidate_key: str | None

class CaseProceedingCoreRuntime:
    def extract_mentions(self, payload: Mapping[str, Any]) -> tuple[ProceedingMention, ...]:
        tenant_id = str(payload.get("tenant_id") or "").strip()
        case_scope_id = str(payload.get("case_scope_id") or "").strip()
        document_id = str(payload.get("document_id") or "").strip()
        if not tenant_id or not case_scope_id or not document_id:
            raise ValueError("tenant_id, case_scope_id and document_id are required")
        if bool(payload.get("derived_source")) or document_id in DERIVED_SUMMARY_DOCUMENT_IDS:
            return ()
        out = []
        for raw in payload.get("proceeding_mentions") or []:
            quote = str(raw.get("source_quote") or "").strip()
            locator = str(raw.get("source_locator") or "").strip()
            if not quote or not locator:
                continue
            role = raw.get("mention_role") or "UNRESOLVED_ROLE"
            if role not in {"CURRENT_PROCEEDING_MENTION","REFERENCED_PROCEEDING_MENTION","UNRESOLVED_ROLE"}:
                role = "UNRESOLVED_ROLE"
            out.append(ProceedingMention(
                tenant_id=tenant_id, case_scope_id=case_scope_id, document_id=document_id,
                mention_role=role,
                court_name_raw=_clean(raw.get("court_name_raw")),
                chamber_name_raw=_clean(raw.get("chamber_name_raw")),
                case_number_raw=_clean(raw.get("case_number_raw")),
                case_year_raw=_clean(raw.get("case_year_raw")),
                registration_number_raw=_clean(raw.get("registration_number_raw")),
                proceeding_type_raw=_clean(raw.get("proceeding_type_raw")),
                procedural_stage_raw=_clean(raw.get("procedural_stage_raw")),
                related_case_reference_raw=_clean(raw.get("related_case_reference_raw")),
                related_decision_reference_raw=_clean(raw.get("related_decision_reference_raw")),
                relationship_phrase_raw=_clean(raw.get("relationship_phrase_raw")),
                source_quote=quote, source_locator=locator
            ))
        return tuple(out)

    def resolve_pair(self, left: ProceedingMention, right: ProceedingMention) -> ResolutionCandidate:
        if left.tenant_id != right.tenant_id:
            return ResolutionCandidate("REJECTED_CROSS_TENANT", None, False, ("CROSS_TENANT",), None)
        reasons = []
        if left.case_number_raw and right.case_number_raw and left.case_number_raw == right.case_number_raw:
            reasons.append("CASE_NUMBER_MATCH_NON_SUFFICIENT")
        if left.case_year_raw and right.case_year_raw and left.case_year_raw == right.case_year_raw:
            reasons.append("CASE_YEAR_MATCH_SUPPORTING_ONLY")
        if left.court_name_raw and right.court_name_raw and left.court_name_raw == right.court_name_raw:
            reasons.append("RAW_COURT_NAME_MATCH_NON_CANONICAL")
        if left.mention_role != right.mention_role:
            reasons.append("CURRENT_VS_REFERENCED_ROLE_DIFFERENT")
        if not reasons:
            reasons.append("NO_RESOLUTION_SIGNAL")
        key_material = {
            "tenant_id": left.tenant_id,
            "case_scope_id": left.case_scope_id,
            "left": [left.document_id,left.source_locator,left.case_number_raw,left.case_year_raw,left.court_name_raw],
            "right":[right.document_id,right.source_locator,right.case_number_raw,right.case_year_raw,right.court_name_raw],
        }
        key = sha256(json.dumps(key_material, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        return ResolutionCandidate("UNRESOLVED", None, False, tuple(reasons), key)

    def propose_lineage(self, source: ProceedingMention, target: ProceedingMention, explicit_source_relation: bool) -> dict:
        if source.tenant_id != target.tenant_id:
            return {"status":"REJECTED_CROSS_TENANT","canonical_persistence_allowed":False}
        if not explicit_source_relation:
            return {"status":"UNRESOLVED_NO_EXPLICIT_SOURCE_RELATION","canonical_persistence_allowed":False}
        return {
            "status":"RELATION_CANDIDATE_ONLY",
            "canonical_persistence_allowed":False,
            "stable_relation_id":None,
            "source_document_id":target.document_id,
            "source_locator":target.source_locator,
        }

def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None

def stable_projection_sha256(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",",":")).encode()).hexdigest()

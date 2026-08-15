from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Protocol, Sequence
import copy
import json
import re

from .offline import ExtractionResult, OfflineCaseEngine, OfflineRunResult


@dataclass(frozen=True)
class BatchDocument:
    document_id: str
    document_date: str
    case_scope_id: str
    document_type_id: str
    litigation_stage: str
    raw_text: str
    structured_fixture: Mapping[str, Any]
    matter_id: str | None = None
    proceeding_id: str | None = None
    derived_secondary_source: bool = False


class PerDocumentFixtureExtractor:
    """Test-only fixture extractor keyed by document_id, not document type."""

    extractor_id = "PER_DOCUMENT_FIXTURE_EXTRACTOR_V1"

    def __init__(self, fixtures: Mapping[str, Mapping[str, Any]]) -> None:
        self._fixtures = {key: copy.deepcopy(value) for key, value in fixtures.items()}

    def extract(self, *, raw_text: str, contract) -> ExtractionResult:
        try:
            payload = self._fixtures[contract.document_id]
        except KeyError as exc:
            raise KeyError(f"no fixture for document_id={contract.document_id}") from exc
        return ExtractionResult(payload=copy.deepcopy(payload), extractor_id=self.extractor_id)


@dataclass(frozen=True)
class IdentityResolution:
    correlation_key: str
    status: str
    authoritative_for_test: bool = False


class IdentityProvider(Protocol):
    def resolve(self, *, case_scope_id: str, name_raw: str) -> IdentityResolution:
        ...


def normalize_arabic_name(value: str) -> str:
    value = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)
    value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي")
    value = " ".join(value.split())
    for prefix in (
        "السيد ", "السيدة ", "الأستاذ ", "الأستاذة ",
        "المحامي ", "المحامية ", "الدكتور ", "الدكتورة ",
    ):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return value.strip()


class PolicySafeIdentityCorrelator:
    """Correlation only; never a PARTY identity merge or stable-ID decision."""

    def resolve(self, *, case_scope_id: str, name_raw: str) -> IdentityResolution:
        normalized = normalize_arabic_name(name_raw)
        seed = json.dumps([case_scope_id, normalized], ensure_ascii=False).encode("utf-8")
        return IdentityResolution(
            correlation_key=f"pcorr_{sha256(seed).hexdigest()[:20]}",
            status="POSSIBLE_MATCH_REQUIRES_REVIEW",
            authoritative_for_test=False,
        )


class GoldenIdentityOracle:
    """Explicit QA oracle. Never use this provider in production execution."""

    def __init__(self, mapping: Mapping[str, str]) -> None:
        self._mapping = {normalize_arabic_name(k): v for k, v in mapping.items()}

    def resolve(self, *, case_scope_id: str, name_raw: str) -> IdentityResolution:
        normalized = normalize_arabic_name(name_raw)
        oracle_key = self._mapping.get(normalized)
        if oracle_key is None:
            return PolicySafeIdentityCorrelator().resolve(
                case_scope_id=case_scope_id, name_raw=name_raw
            )
        return IdentityResolution(
            correlation_key=f"test:{case_scope_id}:{oracle_key}",
            status="TEST_ORACLE_CONFIRMED",
            authoritative_for_test=True,
        )


@dataclass(frozen=True)
class BatchRunResult:
    document_runs: tuple[OfflineRunResult, ...]
    stable_projection: Mapping[str, Any]
    stable_projection_sha256: str
    canonical_persistence_allowed: bool = False


class BatchOrchestrator:
    """Deterministic Phase-1 batch runner for DOCUMENT -> PARTY -> REQUEST."""

    def __init__(self, *, engine: OfflineCaseEngine, identity_provider: IdentityProvider) -> None:
        self.engine = engine
        self.identity_provider = identity_provider

    @staticmethod
    def _stable_hash(payload: Mapping[str, Any]) -> str:
        encoded = json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def run(self, documents: Sequence[BatchDocument]) -> BatchRunResult:
        ordered = sorted(documents, key=lambda d: (d.document_date, d.document_id))
        if len({d.document_id for d in ordered}) != len(ordered):
            raise ValueError("duplicate document_id in batch")

        extractor = PerDocumentFixtureExtractor(
            {d.document_id: d.structured_fixture for d in ordered}
        )
        runs: list[OfflineRunResult] = []
        party_groups: dict[tuple[str, str], dict[str, Any]] = {}
        request_clusters: list[dict[str, Any]] = []
        request_links: list[dict[str, Any]] = []

        for document in ordered:
            run = self.engine.run(
                case_id=document.case_scope_id,
                document_id=document.document_id,
                document_type_id=document.document_type_id,
                raw_text=document.raw_text,
                extractor=extractor,
                matter_id=document.matter_id,
                proceeding_id=document.proceeding_id,
                litigation_stage=document.litigation_stage,
                allow_unresolved_profile_for_fixture=True,
            )
            runs.append(run)

            if document.derived_secondary_source:
                if run.party_candidates or run.request_candidates:
                    raise ValueError("derived secondary summary must not create PARTY/REQUEST candidates")
                continue

            for candidate in run.party_candidates:
                if candidate.payload.get("role_category") != "PARTY":
                    continue
                identity = self.identity_provider.resolve(
                    case_scope_id=document.case_scope_id,
                    name_raw=str(candidate.payload.get("name_raw", "")),
                )
                key = (document.case_scope_id, identity.correlation_key)
                group = party_groups.setdefault(
                    key,
                    {
                        "case_scope_id": document.case_scope_id,
                        "correlation_key": identity.correlation_key,
                        "resolution_status": identity.status,
                        "stable_party_id": None,
                        "mentions": [],
                        "roles": set(),
                    },
                )
                group["mentions"].append(
                    [document.document_id, candidate.payload.get("name_raw", "")]
                )
                group["roles"].add(
                    candidate.payload.get("procedural_role_suggestion")
                    or candidate.payload.get("role_raw")
                    or ""
                )

            for candidate in run.request_candidates:
                position = str(candidate.payload.get("procedural_position_candidate", "")).upper()
                requester = self.identity_provider.resolve(
                    case_scope_id=document.case_scope_id,
                    name_raw=str(candidate.payload.get("requested_by_raw", "")),
                )
                nature = str(candidate.payload.get("request_nature_candidate", ""))
                existing = [
                    cluster
                    for cluster in request_clusters
                    if cluster["case_scope_id"] == document.case_scope_id
                    and cluster["requester_key"] == requester.correlation_key
                    and cluster["nature"] == nature
                ]

                if position == "REITERATED" and existing:
                    if requester.authoritative_for_test:
                        cluster = existing[-1]
                        cluster["mentions"].append(
                            [document.document_id, candidate.payload.get("raw_text", "")]
                        )
                        request_links.append(
                            {
                                "document_id": document.document_id,
                                "relation": "REITERATED",
                                "target_cluster_id": cluster["cluster_id"],
                            }
                        )
                        continue
                    request_links.append(
                        {
                            "document_id": document.document_id,
                            "relation": "REITERATED_PENDING_PARTY_RESOLUTION",
                            "target_cluster_id": existing[-1]["cluster_id"],
                        }
                    )

                seed = {
                    "case_scope_id": document.case_scope_id,
                    "document_id": document.document_id,
                    "candidate_id": candidate.candidate_id,
                }
                cluster_id = f"rqgrp_{self._stable_hash(seed)[:20]}"
                request_clusters.append(
                    {
                        "cluster_id": cluster_id,
                        "case_scope_id": document.case_scope_id,
                        "requester_key": requester.correlation_key,
                        "nature": nature,
                        "position": position,
                        "related_request_raw": candidate.payload.get("related_request_raw", ""),
                        "stable_request_id": None,
                        "mentions": [[document.document_id, candidate.payload.get("raw_text", "")]],
                    }
                )
                if position in {"ALTERNATIVE", "INCIDENTAL"}:
                    request_links.append(
                        {
                            "document_id": document.document_id,
                            "relation": position,
                            "target_cluster_id": cluster_id,
                        }
                    )

        parties = []
        for group in party_groups.values():
            group = dict(group)
            group["mentions"] = sorted(group["mentions"])
            group["roles"] = sorted(group["roles"])
            parties.append(group)

        projection = {
            "documents": sorted(
                [
                    {
                        "document_id": d.document_id,
                        "document_date": d.document_date,
                        "case_scope_id": d.case_scope_id,
                        "document_type_id": d.document_type_id,
                        "litigation_stage": d.litigation_stage,
                    }
                    for d in ordered
                ],
                key=lambda row: (row["document_date"], row["document_id"]),
            ),
            "party_groups": sorted(parties, key=lambda row: (row["case_scope_id"], row["correlation_key"])),
            "request_clusters": sorted(request_clusters, key=lambda row: row["cluster_id"]),
            "request_links": sorted(
                request_links,
                key=lambda row: (row["document_id"], row["relation"], row["target_cluster_id"]),
            ),
            "canonical_persistence_allowed": False,
            "stable_ids_issued": False,
        }
        return BatchRunResult(
            document_runs=tuple(runs),
            stable_projection=projection,
            stable_projection_sha256=self._stable_hash(projection),
        )

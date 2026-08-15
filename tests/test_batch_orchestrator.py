from types import SimpleNamespace

from qanun_case_runtime.batch import (
    BatchDocument,
    BatchOrchestrator,
    GoldenIdentityOracle,
    PolicySafeIdentityCorrelator,
)


class FakeEngine:
    def run(self, *, document_id, **kwargs):
        fixture = kwargs["extractor"]._fixtures[document_id]
        parties = []
        for i, row in enumerate(fixture.get("parties", [])):
            parties.append(
                SimpleNamespace(
                    candidate_id=f"p-{document_id}-{i}",
                    payload=row,
                )
            )
        requests = []
        for i, row in enumerate(fixture.get("requests", [])):
            requests.append(
                SimpleNamespace(
                    candidate_id=f"r-{document_id}-{i}",
                    payload=row,
                )
            )
        return SimpleNamespace(
            party_candidates=tuple(parties),
            request_candidates=tuple(requests),
        )


def party(name, role, category="PARTY"):
    return {
        "name_raw": name,
        "role_category": category,
        "procedural_role_suggestion": role,
        "role_raw": role,
    }


def request(text, nature, requester, position="ORIGINAL"):
    return {
        "raw_text": text,
        "requested_by_raw": requester,
        "request_nature_candidate": nature,
        "procedural_position_candidate": position,
        "related_request_raw": "",
    }


def doc(doc_id, date, fixture, *, derived=False):
    return BatchDocument(
        document_id=doc_id,
        document_date=date,
        case_scope_id="CASE-1",
        document_type_id="TEST",
        litigation_stage="FIRST_INSTANCE",
        raw_text="fixture",
        structured_fixture=fixture,
        derived_secondary_source=derived,
    )


def test_golden_oracle_preserves_one_actor_with_multiple_stage_roles():
    oracle = GoldenIdentityOracle(
        {
            "سامر العطار": "SAMER",
            "سامر فوزي العطار": "SAMER",
        }
    )
    engine = BatchOrchestrator(engine=FakeEngine(), identity_provider=oracle)
    result = engine.run(
        [
            doc("D2", "2024-01-01", {"parties": [party("سامر العطار", "APPELLANT")]}),
            doc("D1", "2022-01-01", {"parties": [party("سامر فوزي العطار", "DEFENDANT")]}),
        ]
    )
    assert len(result.stable_projection["party_groups"]) == 1
    group = result.stable_projection["party_groups"][0]
    assert group["stable_party_id"] is None
    assert group["roles"] == ["APPELLANT", "DEFENDANT"]


def test_nonparty_roles_are_not_promoted_to_case_party_groups():
    oracle = GoldenIdentityOracle({"نبيل المصري": "NABIL"})
    engine = BatchOrchestrator(engine=FakeEngine(), identity_provider=oracle)
    result = engine.run(
        [
            doc(
                "D1",
                "2022-01-01",
                {
                    "parties": [
                        party("نبيل المصري", "PLAINTIFF"),
                        party("ليلى منصور", "ATTORNEY", "ATTORNEY"),
                        party("يوسف الحداد", "EXPERT", "EXPERT"),
                    ]
                },
            )
        ]
    )
    assert len(result.stable_projection["party_groups"]) == 1


def test_reiterated_request_links_to_existing_cluster_only_with_test_oracle():
    oracle = GoldenIdentityOracle({"نبيل المصري": "NABIL", "نبيل حسن المصري": "NABIL"})
    engine = BatchOrchestrator(engine=FakeEngine(), identity_provider=oracle)
    result = engine.run(
        [
            doc(
                "D1",
                "2022-01-01",
                {"requests": [request("تثبيت البيع", "SPECIFIC_PERFORMANCE", "نبيل حسن المصري")]},
            ),
            doc(
                "D2",
                "2022-02-01",
                {"requests": [request("نجدد طلب تثبيت البيع", "SPECIFIC_PERFORMANCE", "نبيل المصري", "REITERATED")]},
            ),
        ]
    )
    assert len(result.stable_projection["request_clusters"]) == 1
    assert result.stable_projection["request_links"][0]["relation"] == "REITERATED"
    assert result.stable_projection["request_clusters"][0]["stable_request_id"] is None


def test_policy_safe_correlator_never_auto_confirms_identity():
    engine = BatchOrchestrator(engine=FakeEngine(), identity_provider=PolicySafeIdentityCorrelator())
    result = engine.run(
        [doc("D1", "2022-01-01", {"parties": [party("رامي عدنان القباني", "INTERVENOR")]})]
    )
    group = result.stable_projection["party_groups"][0]
    assert group["resolution_status"] == "POSSIBLE_MATCH_REQUIRES_REVIEW"
    assert group["stable_party_id"] is None


def test_secondary_summary_cannot_create_party_or_request_candidates():
    engine = BatchOrchestrator(
        engine=FakeEngine(),
        identity_provider=GoldenIdentityOracle({"نبيل المصري": "NABIL"}),
    )
    summary = doc("D30", "2026-08-15", {}, derived=True)
    result = engine.run([summary])
    assert result.stable_projection["party_groups"] == []
    assert result.stable_projection["request_clusters"] == []


def test_batch_projection_is_input_order_invariant():
    oracle = GoldenIdentityOracle({"نبيل المصري": "NABIL", "سامر العطار": "SAMER"})
    engine = BatchOrchestrator(engine=FakeEngine(), identity_provider=oracle)
    documents = [
        doc("D2", "2022-02-01", {"parties": [party("سامر العطار", "DEFENDANT")]}),
        doc("D1", "2022-01-01", {"parties": [party("نبيل المصري", "PLAINTIFF")]}),
    ]
    forward = engine.run(documents)
    reverse = engine.run(list(reversed(documents)))
    assert forward.stable_projection_sha256 == reverse.stable_projection_sha256
    assert forward.stable_projection == reverse.stable_projection

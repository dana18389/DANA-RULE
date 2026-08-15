import os

import pytest

from qanun_case_runtime import (
    BindingBlockedError,
    FixtureExtractor,
    GovernanceBundleLoader,
    GovernanceRuntime,
    OfflineCaseEngine,
    OutputValidationError,
)


def _bundle_or_skip():
    path = os.getenv("QANUN_GOVERNANCE_BUNDLE_ZIP")
    if not path:
        pytest.skip("set QANUN_GOVERNANCE_BUNDLE_ZIP to run delivery integration tests")
    runtime = GovernanceRuntime(production_activation_allowed=False)
    bundle = GovernanceBundleLoader(runtime).load(path)
    return runtime, bundle


def _valid_civil_claim_fixture():
    return {
        "issuance_and_submission": {
            "issuer_name_raw": "أحمد محمد",
            "issuer_type_raw": "PLAINTIFF",
            "recipient_name_raw": "محكمة البداية المدنية بدمشق",
            "submission_date_raw": "2026-08-15",
            "document_number_raw": "",
            "submission_method_raw": "FILED",
            "source_page": 1,
            "source_quote": "الجهة المدعية أحمد محمد",
            "certainty": "EXPLICIT",
        },
        "parties_and_persons": [
            {
                "name_raw": "أحمد محمد",
                "normalized_name_suggestion": "أحمد محمد",
                "person_type": "NATURAL",
                "role_raw": "المدعي",
                "role_category": "PARTY",
                "procedural_role_suggestion": "PLAINTIFF",
                "original_proceeding_role_raw": "",
                "represented_by_raw": "",
                "represents_raw": [],
                "address_raw": "دمشق",
                "identifiers_raw": [],
                "is_existing_case_party_candidate": False,
                "certainty": "EXPLICIT",
                "source_page": 1,
                "source_quote": "المدعي أحمد محمد",
            }
        ],
        "facts": [],
        "requests": [
            {
                "request_text_raw": "إلزام المدعى عليه بدفع مبلغ 1000000 ل.س",
                "request_summary": "إلزام بالدفع",
                "requested_by_raw": "أحمد محمد",
                "against_party_raw": "خالد علي",
                "request_nature_raw": "موضوعي",
                "primary_or_incidental_raw": "أصلي",
                "object_raw": "دفع مبلغ",
                "amount_raw": "1000000",
                "currency_raw": "SYP",
                "related_request_raw": "",
                "procedural_stage": "FIRST_INSTANCE",
                "explicit_status_raw": "PENDING",
                "certainty": "EXPLICIT",
                "source_page": 1,
                "source_quote": "ألتمس إلزام المدعى عليه بدفع مبلغ مليون ليرة سورية",
            }
        ],
        "defenses": [],
        "evidence_references": [],
        "legal_citations": [],
        "jurisprudence_citations": [],
        "dates_and_events": [],
        "amounts": [],
        "related_documents": [],
        "possible_deadline_events": [],
        "contradictions_within_document": [],
        "case_memory_update_proposals": [],
        "extraction_warnings": [],
        "type_specific": {
            "claim_subject": "مطالبة مالية",
            "claim_value": "1000000 ل.س",
            "cause_of_action": "دين",
            "reliefs_sought": "إلزام المدعى عليه بالدفع",
        },
        "source_extracted_judicial_identifiers": [],
        "procedural_continuity_references": [],
    }


def test_unresolved_profile_remains_blocking_without_explicit_fixture_override():
    runtime, bundle = _bundle_or_skip()
    engine = OfflineCaseEngine(runtime=runtime, bundle=bundle)
    with pytest.raises(BindingBlockedError):
        engine.build_execution_contract(
            case_id="CASE-001",
            document_id="DOC-001",
            document_type_id="CIVIL_CLAIM_PETITION",
        )


def test_valid_fixture_runs_document_party_request_handoff_candidate_only():
    runtime, bundle = _bundle_or_skip()
    fixture = _valid_civil_claim_fixture()
    engine = OfflineCaseEngine(runtime=runtime, bundle=bundle)
    result = engine.run(
        case_id="CASE-001",
        document_id="DOC-001",
        document_type_id="CIVIL_CLAIM_PETITION",
        raw_text="استدعاء دعوى مطالبة مالية",
        extractor=FixtureExtractor({"CIVIL_CLAIM_PETITION": fixture}),
        allow_unresolved_profile_for_fixture=True,
    )

    assert result.party_candidate_count == 1
    assert result.request_candidate_count == 1
    assert result.canonical_persistence_allowed is False
    assert result.execution_contract.mode == "OFFLINE_FIXTURE_TEST"
    assert result.execution_contract.unresolved_profile_override is True
    assert any(
        event.get("event") == "SANDBOX_BLOCKER_OVERRIDE"
        and event.get("production_eligible") is False
        for event in result.audit_trace
    )


def test_invalid_fixture_is_rejected_by_real_document_runtime_schema():
    runtime, bundle = _bundle_or_skip()
    fixture = _valid_civil_claim_fixture()
    del fixture["requests"][0]["source_quote"]
    engine = OfflineCaseEngine(runtime=runtime, bundle=bundle)

    with pytest.raises(OutputValidationError, match="source_quote"):
        engine.run(
            case_id="CASE-001",
            document_id="DOC-001",
            document_type_id="CIVIL_CLAIM_PETITION",
            raw_text="استدعاء دعوى مطالبة مالية",
            extractor=FixtureExtractor({"CIVIL_CLAIM_PETITION": fixture}),
            allow_unresolved_profile_for_fixture=True,
        )

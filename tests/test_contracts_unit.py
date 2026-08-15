import pytest

from qanun_case_runtime import (
    GovernanceContractRegistry,
    GovernanceRuntime,
    SandboxCandidatePipeline,
    BindingBlockedError,
)


def sample_governance():
    return {
        "08_prompt_registry": [
            {
                "prompt_id": "EG_BANK_TRANSFER_PROOF",
                "prompt_version": "1.2",
                "prompt_hash": "p" * 64,
            }
        ],
        "09_schema_registry": [
            {
                "schema_id": "BANK_TRANSFER_PROOF",
                "schema_version": "SCHEMA_V1",
                "schema_hash": "s" * 64,
            }
        ],
        "14_operator_registry": [
            {"operator_id": f"OP_{i}"} for i in range(19)
        ],
        "15_prompt_schema_profile_bindings": [
            {
                "binding_id": "DOCUMENT::BANK_TRANSFER_PROOF::EG_BANK_TRANSFER_PROOF",
                "document_type_id": "BANK_TRANSFER_PROOF",
                "prompt_id": "EG_BANK_TRANSFER_PROOF",
                "prompt_version": "1.2",
                "prompt_hash": "p" * 64,
                "schema_id": "BANK_TRANSFER_PROOF",
                "schema_version": "SCHEMA_V1",
                "schema_hash": "s" * 64,
                "extraction_profile_id": "NOT_DEFINED_IN_SOURCE",
                "binding_status": "PASS_STATIC_PROMPT_SCHEMA_EXACT_PROFILE_NOT_DEFINED_IN_SOURCE",
                "blocking_errors": ["UNKNOWN_EXTRACTION_PROFILE"],
            }
        ],
    }


def runtime():
    r = GovernanceRuntime()
    payload = b"governance-v1.1-runtime-contract"
    r.register_bytes(
        artifact_id="GOVERNANCE_V1_1_CONTRACT",
        version="1.1",
        expected_sha256=r.digest_bytes(payload),
        payload=payload,
    )
    return r


def test_binding_resolves_exact_prompt_and_schema():
    registry = GovernanceContractRegistry(sample_governance())
    binding = registry.resolve_document_binding("BANK_TRANSFER_PROOF")
    assert binding.prompt_id == "EG_BANK_TRANSFER_PROOF"
    assert binding.schema_id == "BANK_TRANSFER_PROOF"


def test_unresolved_profile_blocks_executable_resolution():
    registry = GovernanceContractRegistry(sample_governance())
    with pytest.raises(BindingBlockedError):
        registry.resolve_document_binding("BANK_TRANSFER_PROOF", require_executable=True)


def test_document_candidate_is_candidate_only():
    registry = GovernanceContractRegistry(sample_governance())
    candidate = SandboxCandidatePipeline(runtime(), registry).emit_candidate(
        case_id="CASE-SIM-001",
        index_id="DOCUMENT",
        document_type_id="BANK_TRANSFER_PROOF",
        payload={"raw_text": "إشعار حوالة مصرفية"},
    )
    assert candidate.status == "CANDIDATE_ONLY"
    assert candidate.canonical_persistence_allowed is False
    assert candidate.human_review_required is True
    assert "UNKNOWN_EXTRACTION_PROFILE" in candidate.blockers


def test_party_and_request_candidates_never_receive_stable_ids():
    registry = GovernanceContractRegistry(sample_governance())
    pipeline = SandboxCandidatePipeline(runtime(), registry)
    party = pipeline.emit_candidate(
        case_id="CASE-SIM-001",
        index_id="PARTY",
        payload={"name": "أحمد خالد", "role": "DEFENDANT"},
    )
    request = pipeline.emit_candidate(
        case_id="CASE-SIM-001",
        index_id="REQUEST",
        payload={"request_text": "إلزام المدعى عليه بالدفع"},
    )
    assert party.candidate_id.startswith("cand_")
    assert request.candidate_id.startswith("cand_")
    assert "stable_id" not in party.payload
    assert "stable_id" not in request.payload

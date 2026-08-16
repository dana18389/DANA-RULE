import gzip
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from qanun_case_runtime.evidence import EvidencePackageLoader
from qanun_case_runtime.evidence_runtime import EvidenceActivationPatch
from qanun_case_runtime.evidence_runtime_v2 import EvidenceHardeningPatchV2, EvidenceSandboxRuntimeV2
from qanun_case_runtime.evidence_batch_v2 import EvidenceBatchDocumentV2, EvidenceBatchOrchestratorV2
from qanun_case_runtime.fact_event import FactEventPackageLoader
from qanun_case_runtime.fact_event_runtime import FactEventActivationPatch, FactEventSandboxRuntime
from qanun_case_runtime.governance import GovernanceRuntime

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_ZIP_ENV = "QANUN_EVIDENCE_DELIVERY_ZIP"
FACT_EVENT_ZIP_ENV = "QANUN_FACT_EVENT_DELIVERY_ZIP"
BASE_PATCH = ROOT / "config/evidence_runtime_activation_patch_v1.json"
HARDENING_PATCH = ROOT / "config/evidence_runtime_hardening_patch_v2.json"
FACT_PATCH = ROOT / "config/fact_event_runtime_activation_patch_v1.json"
FIXTURE = ROOT / "tests/fixtures/evidence_golden_case_d01_d30.json.gz"


def evidence_runtime_v2():
    path = os.environ.get(EVIDENCE_ZIP_ENV)
    if not path:
        pytest.skip(f"set {EVIDENCE_ZIP_ENV} to run EVIDENCE V2 integration tests")
    loaded = EvidencePackageLoader(GovernanceRuntime(production_activation_allowed=False)).load(Path(path))
    base_bytes = BASE_PATCH.read_bytes()
    base = EvidenceActivationPatch.from_mapping(json.loads(base_bytes))
    hardening = EvidenceHardeningPatchV2.from_mapping(json.loads(HARDENING_PATCH.read_text(encoding="utf-8")))
    return loaded, EvidenceSandboxRuntimeV2(
        loaded=loaded,
        base_patch=base,
        hardening_patch=hardening,
        base_activation_patch_bytes=base_bytes,
    )


def fixture_rows():
    return {row["document_id"]: row for row in json.loads(gzip.decompress(FIXTURE.read_bytes()).decode())["documents"]}


def test_reference_entity_kind_is_structurally_separate():
    _, runtime = evidence_runtime_v2()
    row = fixture_rows()["D12"]
    result = runtime.extract(
        case_id=row["case_scope_id"], source_document_id=row["document_id"],
        document_type_id=row["document_type_id"], litigation_stage=row["litigation_stage"],
        raw_text=row["raw_text"], fact_candidates={},
    )
    assert result.candidates
    assert all(c.record_kind == "EVIDENCE_REFERENCE" for c in result.candidates)
    assert all(c.entity_kind == "EVIDENCE_REFERENCE" for c in result.candidates)


def test_fact_target_spoofing_and_cross_document_targets_are_rejected():
    _, runtime = evidence_runtime_v2()
    row = fixture_rows()["D02"]
    spoofed = {
        "not_a_fact_candidate": {
            "candidate_id": "not_a_fact_candidate",
            "canonical_type_id": "FACT_PAYMENT_STATUS",
            "source_document_id": "D02",
            "source_quote": row["raw_text"],
            "entity_kind": "FACT",
        },
        "fecand_cross_doc": {
            "candidate_id": "fecand_cross_doc",
            "canonical_type_id": "FACT_PAYMENT_STATUS",
            "source_document_id": "D99",
            "source_quote": row["raw_text"],
            "entity_kind": "FACT",
        },
    }
    result = runtime.extract(
        case_id=row["case_scope_id"], source_document_id="D02",
        document_type_id=row["document_type_id"], litigation_stage=row["litigation_stage"],
        raw_text=row["raw_text"], fact_candidates=spoofed,
    )
    assert set(result.rejected_fact_targets) == set(spoofed)
    assert not [r for r in result.relation_candidates if r.relation_id == "EVIDENCE_SUPPORTS_FACT"]


def test_delivery_zip_hash_is_activation_bound():
    loaded, runtime = evidence_runtime_v2()
    bad = replace(runtime.hardening_patch, target_delivery_zip_sha256="0" * 64)
    with pytest.raises(Exception, match="delivery ZIP hash mismatch"):
        EvidenceSandboxRuntimeV2(
            loaded=loaded, base_patch=runtime.patch, hardening_patch=bad,
            base_activation_patch_bytes=BASE_PATCH.read_bytes(),
        )


def test_composite_batch_identity_allows_same_document_id_in_distinct_case_scopes():
    _, runtime = evidence_runtime_v2()
    row = fixture_rows()["D30"]
    docs = [
        EvidenceBatchDocumentV2("CASE-A", "D30", row["document_date"], row["document_type_id"], row["litigation_stage"], row["raw_text"], derived_secondary_source=True),
        EvidenceBatchDocumentV2("CASE-B", "D30", row["document_date"], row["document_type_id"], row["litigation_stage"], row["raw_text"], derived_secondary_source=True),
    ]
    run = EvidenceBatchOrchestratorV2(runtime).run(docs)
    assert {key for key, _ in run.document_results} == {("CASE-A", "D30"), ("CASE-B", "D30")}
    assert not run.result_for("CASE-A", "D30").candidates


def test_fact_event_to_evidence_real_runtime_e2e_d02():
    evidence_zip = os.environ.get(EVIDENCE_ZIP_ENV)
    fact_zip = os.environ.get(FACT_EVENT_ZIP_ENV)
    if not evidence_zip or not fact_zip:
        pytest.skip(f"set {EVIDENCE_ZIP_ENV} and {FACT_EVENT_ZIP_ENV} for real cross-index E2E")

    _, evidence = evidence_runtime_v2()
    fact_loaded = FactEventPackageLoader(GovernanceRuntime(production_activation_allowed=False)).load(Path(fact_zip))
    fact_patch = FactEventActivationPatch.from_mapping(json.loads(FACT_PATCH.read_text(encoding="utf-8")))
    fact_runtime = FactEventSandboxRuntime(loaded=fact_loaded, patch=fact_patch)
    row = fixture_rows()["D02"]

    fact_result = fact_runtime.extract(
        case_id=row["case_scope_id"], source_document_id="D02",
        document_type_id=row["document_type_id"], litigation_stage=row["litigation_stage"],
        raw_text=row["raw_text"], document_date=row["document_date"],
    )
    actual_facts = {c.candidate_id: c for c in fact_result.candidates if c.entity_kind == "FACT"}
    assert actual_facts, "FACT_EVENT runtime must produce actual FACT candidates for D02"

    result = evidence.extract(
        case_id=row["case_scope_id"], source_document_id="D02",
        document_type_id=row["document_type_id"], litigation_stage=row["litigation_stage"],
        raw_text=row["raw_text"], fact_candidates=actual_facts,
    )
    support = [r for r in result.relation_candidates if r.relation_id == "EVIDENCE_SUPPORTS_FACT"]
    assert support
    assert {r.target_ref for r in support} <= set(actual_facts)
    assert all(getattr(r, "target_validation", None) == "FACT_CANDIDATE_VALIDATED" for r in support)
    # No legacy hard-coded fact_refs() are involved in this test.
    assert all(r.target_ref.startswith("fecand_") for r in support)


def test_v1_frozen_files_are_unchanged_by_v2_patch():
    baseline = json.loads((ROOT / "config/evidence_runtime_baseline_v1.json").read_text(encoding="utf-8"))
    assert baseline["status"] == "FROZEN_SANDBOX_BASELINE_LOCAL_VERIFIED"
    assert baseline["golden_case_projection_sha256"] == "27bb93ccd73b10aa976dddbffc9a6bb62dae7da6dd62b36c9bee994280d8d0b6"
    assert hashlib.sha256(BASE_PATCH.read_bytes()).hexdigest() == "f4ae93fca98a76adf590fd5cd6261343a3b8f8a2ba74cffc4ca9b6eb2b600e2f"

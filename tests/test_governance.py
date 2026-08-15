import pytest

from qanun_case_runtime import GovernanceRuntime, GovernanceError, HashMismatchError, ActivationBlockedError


def test_register_exact_hash_and_snapshot():
    runtime = GovernanceRuntime(production_activation_allowed=False)
    payload = b"immutable-package"
    digest = runtime.digest_bytes(payload)
    runtime.register_bytes(artifact_id="TEST", version="1", expected_sha256=digest, payload=payload)
    snapshot = runtime.snapshot(environment="sandbox_shadow_mode")
    assert snapshot.bindings["TEST"].sha256 == digest
    assert snapshot.snapshot_id.startswith("snap_")


def test_hash_mismatch_is_blocking():
    runtime = GovernanceRuntime()
    with pytest.raises(HashMismatchError):
        runtime.register_bytes(artifact_id="TEST", version="1", expected_sha256="0" * 64, payload=b"wrong")


def test_registry_is_immutable_for_same_artifact_id():
    runtime = GovernanceRuntime()
    p1 = b"v1"
    p2 = b"v2"
    runtime.register_bytes(artifact_id="DOCUMENT", version="1", expected_sha256=runtime.digest_bytes(p1), payload=p1)
    with pytest.raises(GovernanceError, match="immutable registry conflict"):
        runtime.register_bytes(artifact_id="DOCUMENT", version="2", expected_sha256=runtime.digest_bytes(p2), payload=p2)


def test_production_execution_is_blocked():
    runtime = GovernanceRuntime(production_activation_allowed=False)
    payload = b"x"
    runtime.register_bytes(artifact_id="TEST", version="1", expected_sha256=runtime.digest_bytes(payload), payload=payload)
    with pytest.raises(ActivationBlockedError):
        runtime.snapshot(environment="production")


def test_canonical_persistence_is_blocked_in_sandbox():
    runtime = GovernanceRuntime(production_activation_allowed=False)
    with pytest.raises(ActivationBlockedError):
        runtime.assert_business_persistence_allowed(environment="sandbox_shadow_mode")

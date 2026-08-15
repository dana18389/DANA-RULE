from pathlib import Path
import os
import pytest

from qanun_case_runtime import GovernanceBundleLoader, GovernanceRuntime


@pytest.mark.integration
def test_real_delivery_bundle_loads_and_verifies_every_artifact():
    zip_path = os.environ.get("QANUN_GOVERNANCE_BUNDLE_ZIP")
    if not zip_path:
        pytest.skip("set QANUN_GOVERNANCE_BUNDLE_ZIP to run delivery-bundle integration test")

    runtime = GovernanceRuntime(production_activation_allowed=False)
    loaded = GovernanceBundleLoader(runtime).load(Path(zip_path))

    assert loaded.bundle_sha256 == "ba67faab762f7286c9164747a3bc2e26933e5627f502293f2de44d9880f35e8a"
    assert len(loaded.bindings) == 9
    assert set(loaded.bindings) == {
        "DOCUMENT",
        "PARTY",
        "REQUEST",
        "DOCUMENT_PARTY",
        "DOCUMENT_PARTY_COMPATIBILITY_ADAPTER",
        "REQUEST_CROSS_INDEX",
        "THREE_INDEX_BINDING",
        "GOVERNANCE_V1",
        "GOVERNANCE_V1_1",
    }
    assert loaded.bindings["DOCUMENT"].sha256 == "bf607f3dc03b426de47a1bc6cde0f3392ee882aaa2001cb14fb8b1956defab4d"
    assert loaded.bindings["PARTY"].sha256 == "47993bdd98de1a644dd4352815ce33e9be1da2b0ef7e8697f934fe5c0b87d5f0"
    assert loaded.bindings["REQUEST"].sha256 == "4e6908192f2f529a356f4c105a0afb6a5cf6987d9167ab75f0b8055a45e69e80"
    assert len(loaded.contracts.prompts) == 215
    assert len(loaded.contracts.schemas) == 226
    assert len(loaded.contracts.operators) == 19
    assert len(loaded.contracts.bindings) == 226
    assert loaded.unresolved_extraction_profiles == 226
    assert loaded.snapshot.environment == "registry_import"

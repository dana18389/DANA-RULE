import os
from pathlib import Path
import pytest

from qanun_case_runtime import GovernanceContractRegistry

GOV_SHA256 = "8a8fe588477bd79aea105f7ecf54189180eb04852418eac02f7e7c9b127273d5"


def test_real_governance_delivery_contract_when_mounted():
    raw = os.environ.get("QANUN_GOVERNANCE_V1_1_PATH")
    if not raw:
        pytest.skip("QANUN_GOVERNANCE_V1_1_PATH not mounted")
    path = Path(raw)
    registry = GovernanceContractRegistry.from_file(path, expected_sha256=GOV_SHA256)
    report = registry.validate()
    assert report.structurally_valid
    assert report.prompt_count == 215
    assert report.schema_count == 226
    assert report.operator_count == 19
    assert report.binding_count == 226
    # Governance V1.1 explicitly records extraction profiles as unresolved.
    # Runtime must surface this, never silently invent/bypass it.
    assert report.unresolved_profile_bindings == 226

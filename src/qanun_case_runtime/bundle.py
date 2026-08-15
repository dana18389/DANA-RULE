from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
import zipfile

from .contracts import GovernanceContractRegistry
from .governance import (
    ArtifactBinding,
    ExecutionSnapshot,
    GovernanceError,
    GovernanceRuntime,
    HashMismatchError,
)


class BundleValidationError(GovernanceError):
    pass


@dataclass(frozen=True)
class LoadedGovernanceBundle:
    bundle_sha256: str
    delivery_root: str
    bindings: Mapping[str, ArtifactBinding]
    snapshot: ExecutionSnapshot
    contracts: GovernanceContractRegistry
    source_packages: Mapping[str, Mapping[str, Any]]
    unresolved_extraction_profiles: int


class GovernanceBundleLoader:
    """Load CASE_EXTRACTION_GOVERNANCE_V1.1 directly from its delivery ZIP.

    The loader fail-closes. It verifies every file declared by the delivery
    manifest before mutating the runtime registry, verifies each immutable
    baseline artifact against the baseline manifest, then registers the
    verified artifacts atomically from the caller's perspective.
    """

    DELIVERY_MANIFEST = "13_GOVERNANCE_V1_1_DELIVERY_MANIFEST.json"
    BASELINE_MANIFEST = "02_GOVERNANCE_V1_1_BASELINE_MANIFEST.json"
    GOVERNANCE_V11 = "QANUN_AI_CASE_EXTRACTION_GOVERNANCE_V1_1_PRODUCTION_CANDIDATE.json"

    BASELINE_PREFIXES = {
        "DOCUMENT": "DOCUMENT__",
        "PARTY": "PARTY__",
        "REQUEST": "REQUEST__",
        "DOCUMENT_PARTY": "DOCUMENT_PARTY__",
        "DOCUMENT_PARTY_COMPATIBILITY_ADAPTER": "DOCUMENT_PARTY_COMPATIBILITY_ADAPTER__",
        "REQUEST_CROSS_INDEX": "REQUEST_CROSS_INDEX__",
        "THREE_INDEX_BINDING": "THREE_INDEX_BINDING__",
        "GOVERNANCE_V1": "GOVERNANCE_V1__",
    }

    def __init__(self, runtime: GovernanceRuntime) -> None:
        self.runtime = runtime

    @staticmethod
    def _digest(payload: bytes) -> str:
        return sha256(payload).hexdigest()

    def load(self, zip_path: str | Path) -> LoadedGovernanceBundle:
        zip_path = Path(zip_path)
        bundle_sha256 = self._digest(zip_path.read_bytes())

        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            roots = {
                name[: -len(self.DELIVERY_MANIFEST)]
                for name in names
                if name.endswith(self.DELIVERY_MANIFEST)
            }
            if len(roots) != 1:
                raise BundleValidationError(
                    f"expected exactly one delivery root, got {len(roots)}"
                )
            root = next(iter(roots))

            delivery = json.loads(archive.read(root + self.DELIVERY_MANIFEST))
            self._verify_delivery_manifest(archive, root, names, delivery)

            baseline = json.loads(archive.read(root + self.BASELINE_MANIFEST))
            baseline_by_id = {
                artifact["artifact_id"]: artifact for artifact in baseline["artifacts"]
            }

            resolved: dict[str, tuple[str, str, bytes]] = {}
            source_packages: dict[str, Mapping[str, Any]] = {}
            for artifact_id, prefix in self.BASELINE_PREFIXES.items():
                matches = [
                    name
                    for name in names
                    if name.startswith(root + "00_IMMUTABLE_BASELINE/" + prefix)
                ]
                if len(matches) != 1:
                    raise BundleValidationError(
                        f"{artifact_id}: expected one baseline file, got {len(matches)}"
                    )

                payload = archive.read(matches[0])
                if artifact_id == "THREE_INDEX_BINDING":
                    item = next(
                        row
                        for row in delivery["files"]
                        if row["file"].startswith(
                            "00_IMMUTABLE_BASELINE/THREE_INDEX_BINDING__"
                        )
                    )
                    expected_sha256 = item["sha256"]
                    version = "1.0.0"
                else:
                    metadata = baseline_by_id[artifact_id]
                    expected_sha256 = metadata["calculated_sha256"]
                    version = metadata["artifact_version"]

                actual_sha256 = self._digest(payload)
                if actual_sha256 != expected_sha256:
                    raise HashMismatchError(
                        f"{artifact_id}: expected {expected_sha256}, got {actual_sha256}"
                    )
                resolved[artifact_id] = (version, expected_sha256, payload)
                source_packages[artifact_id] = json.loads(payload)

            governance_payload = archive.read(root + self.GOVERNANCE_V11)
            governance_item = next(
                row for row in delivery["files"] if row["file"] == self.GOVERNANCE_V11
            )
            actual_governance_hash = self._digest(governance_payload)
            if actual_governance_hash != governance_item["sha256"]:
                raise HashMismatchError(
                    "Governance V1.1 raw file hash does not match delivery manifest"
                )

            governance_json = json.loads(governance_payload)
            contracts = GovernanceContractRegistry(governance_json)
            report = contracts.validate()
            if not report.structurally_valid:
                raise BundleValidationError(
                    "governance contract registry failed referential validation: "
                    + "; ".join(report.referential_errors[:5])
                )

            for artifact_id, (version, expected_sha256, payload) in resolved.items():
                self.runtime.register_bytes(
                    artifact_id=artifact_id,
                    version=version,
                    expected_sha256=expected_sha256,
                    payload=payload,
                )

            self.runtime.register_bytes(
                artifact_id="GOVERNANCE_V1_1",
                version="1.1",
                expected_sha256=governance_item["sha256"],
                payload=governance_payload,
            )
            source_packages["GOVERNANCE_V1_1"] = governance_json

            snapshot = self.runtime.snapshot(environment="registry_import")
            return LoadedGovernanceBundle(
                bundle_sha256=bundle_sha256,
                delivery_root=root,
                bindings=dict(self.runtime.registry),
                snapshot=snapshot,
                contracts=contracts,
                source_packages=source_packages,
                unresolved_extraction_profiles=report.unresolved_profile_bindings,
            )

    def _verify_delivery_manifest(
        self,
        archive: zipfile.ZipFile,
        root: str,
        names: list[str],
        delivery: dict,
    ) -> None:
        for item in delivery["files"]:
            full_name = root + item["file"]
            if full_name not in names:
                raise BundleValidationError(f"missing delivery file: {item['file']}")
            payload = archive.read(full_name)
            actual_sha256 = self._digest(payload)
            if actual_sha256 != item["sha256"]:
                raise HashMismatchError(
                    f"{item['file']}: expected {item['sha256']}, got {actual_sha256}"
                )
            if len(payload) != item["size_bytes"]:
                raise BundleValidationError(f"size mismatch: {item['file']}")

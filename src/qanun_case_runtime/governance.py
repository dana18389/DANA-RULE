from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
from typing import Dict, Mapping
import json
import time


class GovernanceError(RuntimeError):
    pass


class HashMismatchError(GovernanceError):
    pass


class ActivationBlockedError(GovernanceError):
    pass


@dataclass(frozen=True)
class ArtifactBinding:
    artifact_id: str
    version: str
    sha256: str
    immutable: bool = True


@dataclass(frozen=True)
class ExecutionSnapshot:
    snapshot_id: str
    environment: str
    created_at_epoch_ms: int
    bindings: Mapping[str, ArtifactBinding]

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "environment": self.environment,
            "created_at_epoch_ms": self.created_at_epoch_ms,
            "bindings": {k: asdict(v) for k, v in self.bindings.items()},
        }


class GovernanceRuntime:
    """Milestone-1 governance runtime for QANUN AI Case Intelligence."""

    ALLOWED_NON_PROD = {"sandbox_shadow_mode", "static_validation", "registry_import"}

    def __init__(self, *, production_activation_allowed: bool = False) -> None:
        self._registry: Dict[str, ArtifactBinding] = {}
        self.production_activation_allowed = production_activation_allowed

    @staticmethod
    def digest_bytes(payload: bytes) -> str:
        return sha256(payload).hexdigest()

    @staticmethod
    def digest_file(path: str | Path) -> str:
        p = Path(path)
        h = sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def register_bytes(self, *, artifact_id: str, version: str, expected_sha256: str, payload: bytes) -> ArtifactBinding:
        actual = self.digest_bytes(payload)
        if actual != expected_sha256:
            raise HashMismatchError(f"{artifact_id}: expected {expected_sha256}, got {actual}")
        binding = ArtifactBinding(artifact_id=artifact_id, version=version, sha256=actual)
        existing = self._registry.get(artifact_id)
        if existing and existing != binding:
            raise GovernanceError(f"immutable registry conflict for {artifact_id}")
        self._registry[artifact_id] = binding
        return binding

    def register_file(self, *, artifact_id: str, version: str, expected_sha256: str, path: str | Path) -> ArtifactBinding:
        p = Path(path)
        actual = self.digest_file(p)
        if actual != expected_sha256:
            raise HashMismatchError(f"{artifact_id}: expected {expected_sha256}, got {actual}")
        binding = ArtifactBinding(artifact_id=artifact_id, version=version, sha256=actual)
        existing = self._registry.get(artifact_id)
        if existing and existing != binding:
            raise GovernanceError(f"immutable registry conflict for {artifact_id}")
        self._registry[artifact_id] = binding
        return binding

    def snapshot(self, *, environment: str) -> ExecutionSnapshot:
        self._assert_environment(environment)
        if not self._registry:
            raise GovernanceError("cannot create execution snapshot from empty registry")
        canonical = json.dumps(
            {k: asdict(v) for k, v in sorted(self._registry.items())},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        snapshot_id = f"snap_{sha256(canonical).hexdigest()[:24]}"
        return ExecutionSnapshot(
            snapshot_id=snapshot_id,
            environment=environment,
            created_at_epoch_ms=int(time.time() * 1000),
            bindings=dict(self._registry),
        )

    def assert_business_persistence_allowed(self, *, environment: str) -> None:
        self._assert_environment(environment)
        if environment != "production":
            raise ActivationBlockedError("canonical business persistence is disabled outside production")
        if not self.production_activation_allowed:
            raise ActivationBlockedError("production activation is blocked by Governance V1.1")

    def _assert_environment(self, environment: str) -> None:
        if environment == "production":
            if not self.production_activation_allowed:
                raise ActivationBlockedError("production execution is blocked by Governance V1.1")
            return
        if environment not in self.ALLOWED_NON_PROD:
            raise GovernanceError(f"unsupported environment/mode: {environment}")

    @property
    def registry(self) -> Mapping[str, ArtifactBinding]:
        return dict(self._registry)

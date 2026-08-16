
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib, json
from typing import Any, Dict, Tuple

PACKAGE_SHA256 = "bd1f40720fe9ceed7b366a652b7f5d0a77027cfe2dd0706760ff00a343f67a8e"
REPORT_SHA256 = "99b507cf097afff3a27deefd436fbd1fbb14561d1b0013731243f537049f77ae"

class LegalReferenceRolePackageError(RuntimeError):
    pass

@dataclass(frozen=True)
class LoadedLegalReferenceRolePackage:
    package: Dict[str, Any]
    report_text: str
    package_sha256: str
    report_sha256: str
    role_ids: Tuple[str, ...]
    query_intent_ids: Tuple[str, ...]
    scenario_tests: Tuple[Dict[str, Any], ...]

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _canon_sha(value: Any) -> str:
    raw=json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",",":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

class LegalReferenceRolePackageLoader:
    def load(self, package_path: str|Path, report_path: str|Path) -> LoadedLegalReferenceRolePackage:
        pp, rp = Path(package_path), Path(report_path)
        if _sha(pp) != PACKAGE_SHA256:
            raise LegalReferenceRolePackageError("PACKAGE_SHA256_MISMATCH")
        if _sha(rp) != REPORT_SHA256:
            raise LegalReferenceRolePackageError("REPORT_SHA256_MISMATCH")
        d=json.loads(pp.read_text(encoding="utf-8"))
        if d.get("package_version") != "1.1.0-legal-rebuild-candidate.2026-08-15":
            raise LegalReferenceRolePackageError("PACKAGE_VERSION_MISMATCH")
        if d.get("package_status") != "PRODUCTION_CANDIDATE_NOT_FROZEN":
            raise LegalReferenceRolePackageError("SOURCE_STATUS_MISMATCH")
        if d.get("production_eligible") is not False:
            raise LegalReferenceRolePackageError("SOURCE_MUST_REMAIN_PRODUCTION_INELIGIBLE")
        manifest=d["rebuild_manifest"]["component_content_sha256"]
        for name, expected in manifest.items():
            if name not in d["components"]:
                raise LegalReferenceRolePackageError(f"MISSING_COMPONENT:{name}")
            if _canon_sha(d["components"][name]) != expected:
                raise LegalReferenceRolePackageError(f"COMPONENT_HASH_MISMATCH:{name}")

        tax=d["components"]["01_legal_reference_role_taxonomy.json"]
        dic=d["components"]["02_legal_reference_role_dictionary.json"]
        qi=d["components"]["03_neo4j_query_intents.json"]
        qt=d["components"]["04_neo4j_query_templates.json"]
        rel=d["components"]["05_legal_reference_relations.json"]
        xmap=d["components"]["09_cross_dictionary_role_map.json"]
        testc=d["components"]["12_test_cases.json"]
        sv=d["static_rebuild_validation"]

        roles=[r["role_id"] for r in tax["role_types"]]
        entries=[r["role_id"] for r in dic["entries"]]
        intents=[q["query_intent_id"] for q in qi["query_intents"]]
        relations=[r["relation_type"] for r in rel["relations"]]

        expected_counts=(19,279,279,41,47,25)
        actual=(len(tax["role_families"]),len(roles),len(entries),len(intents),len(relations),len(testc["tests"]))
        if actual != expected_counts:
            raise LegalReferenceRolePackageError(f"COUNT_MISMATCH:{actual}")
        if len(set(roles)) != 279 or len(set(entries)) != 279 or set(roles) != set(entries):
            raise LegalReferenceRolePackageError("ROLE_DICTIONARY_PARITY_FAILED")
        if len(set(intents)) != 41 or len(set(relations)) != 47:
            raise LegalReferenceRolePackageError("REGISTRY_UNIQUENESS_FAILED")
        routing=qi.get("role_to_query_intent_routing",[])
        if len(routing) != 279 or {r["role_id"] for r in routing} != set(roles):
            raise LegalReferenceRolePackageError("ROLE_ROUTING_COVERAGE_FAILED")
        if any(r.get("automatic_role_assignment_allowed") for r in routing):
            raise LegalReferenceRolePackageError("AUTOMATIC_ROLE_ASSIGNMENT_PROHIBITED")
        if sv.get("status") != "PASS" or not all(sv.get("checks",{}).values()) or len(sv.get("static_test_spec_results",[])) != 25:
            raise LegalReferenceRolePackageError("SOURCE_STATIC_VALIDATION_FAILED")
        if any(x.get("runtime_resolution_executed") for x in sv["static_test_spec_results"]):
            raise LegalReferenceRolePackageError("SOURCE_RUNTIME_STATE_UNEXPECTED")
        if qt.get("execution_status") != "BLOCKED_UNTIL_NEO4J_SCHEMA_SNAPSHOT":
            raise LegalReferenceRolePackageError("QUERY_TEMPLATE_SOURCE_STATE_CHANGED")
        if any(t.get("cypher_template") for t in qt.get("templates",[])):
            raise LegalReferenceRolePackageError("CYPHER_MUST_REMAIN_UNGENERATED_WITHOUT_SCHEMA")
        if xmap.get("per_type_expansion_status") not in {
            "PENDING_PRODUCTION_TYPE_INVENTORIES",
            "BLOCKED_EXTERNAL_PRODUCTION_TYPE_INVENTORIES",
            "PENDING_DICTIONARY_ARTIFACTS",
            "PENDING_DICTIONARY_ARTIFACT",
            "NOT_EXPANDED",
            "BLOCKED_EXTERNAL_INPUT"
        } and any(m.get("source_type_id") is not None for m in xmap.get("mappings",[])):
            raise LegalReferenceRolePackageError("CROSS_DICTIONARY_PER_TYPE_STATE_UNEXPECTED")
        if len(xmap.get("mappings",[])) != 15 or any(m.get("source_type_id") is not None for m in xmap.get("mappings",[])):
            raise LegalReferenceRolePackageError("PER_TYPE_MAPPING_MUST_REMAIN_UNRESOLVED")

        return LoadedLegalReferenceRolePackage(
            package=d,
            report_text=rp.read_text(encoding="utf-8"),
            package_sha256=PACKAGE_SHA256,
            report_sha256=REPORT_SHA256,
            role_ids=tuple(sorted(roles)),
            query_intent_ids=tuple(sorted(intents)),
            scenario_tests=tuple(testc["tests"]),
        )

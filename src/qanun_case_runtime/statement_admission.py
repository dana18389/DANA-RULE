from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json
from .governance import ExecutionSnapshot, GovernanceError, GovernanceRuntime, HashMismatchError

class StatementAdmissionPackageError(GovernanceError):
    pass

@dataclass(frozen=True)
class StatementAdmissionValidationReport:
    statement_event_type_count:int
    statement_function_type_count:int
    proposition_type_count:int
    denial_type_count:int
    admission_candidate_type_count:int
    attribution_type_count:int
    scope_type_count:int
    explicitness_type_count:int
    lifecycle_status_count:int
    concrete_taxonomy_type_count:int
    dictionary_entry_count:int
    relation_count:int
    statement_transition_count:int
    admission_transition_count:int
    backend_model_count:int
    validation_check_count:int
    unresolved_extension_count:int
    errors:tuple[str,...]
    @property
    def valid(self)->bool: return not self.errors

class StatementAdmissionRegistry:
    EXPECTED={
      "statement_event_types":29,"statement_function_types":37,"proposition_types":45,
      "denial_types":14,"admission_candidate_types":36,"attribution_types":10,
      "scope_types":7,"explicitness_types":5,"lifecycle_statuses":16,
      "concrete_taxonomy_types":174,"dictionary_entries":174,"relations":116,
      "statement_transitions":16,"admission_transitions":14,"backend_models":14,
      "validation_checks":55,"unresolved_extensions":3,
    }
    REQUIRED_BOUNDARIES={
      "STATEMENT_EVENT != STATEMENT_PROPOSITION","STATEMENT_PROPOSITION != FACT",
      "STATEMENT_PROPOSITION != CLAIM","STATEMENT_PROPOSITION != REQUEST",
      "STATEMENT_PROPOSITION != DEFENSE","STATEMENT_PROPOSITION != EVIDENCE_ITEM",
      "ADMISSION_ASSESSMENT != STATEMENT_EVENT","ADMISSION_ASSESSMENT != FACT_TRUTH",
      "ADMISSION_ASSESSMENT != REQUEST_ACCEPTANCE",
      "ADMISSION_ASSESSMENT != EVIDENCE_AUTHENTICITY_FINALITY",
      "CONFESSION_ASSESSMENT != CIVIL_ADMISSION_ASSESSMENT",
      "COURT_POSITION != COURT_NARRATION","REPRESENTATIVE_STATEMENT != PRINCIPAL_STATEMENT",
      "STATEMENT != CONSENT","STATEMENT != WAIVER","STATEMENT != LEGAL_ARGUMENT",
      "CONSENT != WAIVER","CONSENT != ADMISSION","WAIVER != ADMISSION",
      "LEGAL_ARGUMENT != ADMISSION","SIGNATURE_ADMISSION != DOCUMENT_CONTENT_ADMISSION",
      "DOCUMENT_RECEIPT_ADMISSION != DOCUMENT_VALIDITY_ADMISSION",
      "PAYMENT_RECEIPT_ADMISSION != PAYMENT_CAUSE_ADMISSION",
      "PAYMENT_RECEIPT_ADMISSION != OBLIGATION_EXTINGUISHMENT",
      "CONTRACT_EXISTENCE_ADMISSION != CONTRACT_VALIDITY_OR_ENFORCEABILITY",
      "SUPPORTING_EVIDENCE != FACT_TRUTH","NO_LLM_STABLE_IDS",
    }
    TAX_KEYS=("statement_event_types","statement_function_types","proposition_types","denial_types",
              "admission_candidate_types","attribution_types","scope_types","explicitness_types","lifecycle_statuses")

    def __init__(self,package:Mapping[str,Any]):
        self.package=package
        self.components=package["production_components_v1_3"]
        self.taxonomy=self.components["taxonomy"]
        self.dictionary=self.components["dictionary"]
        self.relations=self.components["relations"]
        self.validation=self.components["validation"]
        self.types={}
        self.axis={}
        for key in self.TAX_KEYS:
            for row in self.taxonomy[key]:
                tid=str(row["type_id"])
                if tid in self.types: raise StatementAdmissionPackageError(f"duplicate type ID: {tid}")
                self.types[tid]=row; self.axis[tid]=key
        self.dictionary_entries={str(x["type_id"]):x for x in self.dictionary["entries"]}
        self.concrete_type_ids={tid for tid,row in self.types.items() if row.get("classification_level")=="TYPE"}
        self.relationship_types=tuple(self.relations["relationship_types"])
        self.relation_ids={str(x["relation_id"]) for x in self.relationship_types}
        self.unresolved_extensions=tuple(package["legal_rebuild_alignment_v1_3"]["unresolved_canonical_extensions"])

    def validate(self)->StatementAdmissionValidationReport:
        errors=[]
        actual={
          "statement_event_types":len(self.taxonomy["statement_event_types"]),
          "statement_function_types":len(self.taxonomy["statement_function_types"]),
          "proposition_types":len(self.taxonomy["proposition_types"]),
          "denial_types":len(self.taxonomy["denial_types"]),
          "admission_candidate_types":len(self.taxonomy["admission_candidate_types"]),
          "attribution_types":len(self.taxonomy["attribution_types"]),
          "scope_types":len(self.taxonomy["scope_types"]),
          "explicitness_types":len(self.taxonomy["explicitness_types"]),
          "lifecycle_statuses":len(self.taxonomy["lifecycle_statuses"]),
          "concrete_taxonomy_types":len(self.concrete_type_ids),
          "dictionary_entries":len(self.dictionary_entries),
          "relations":len(self.relationship_types),
          "statement_transitions":len(self.relations["statement_status_transition_rules"]),
          "admission_transitions":len(self.relations["admission_status_transition_rules"]),
          "backend_models":len(self.components["backend_contract"]["models"]),
          "validation_checks":len(self.validation["checks"]),
          "unresolved_extensions":len(self.unresolved_extensions),
        }
        for k,e in self.EXPECTED.items():
            if actual[k]!=e: errors.append(f"{k}: expected {e}, got {actual[k]}")
        if set(self.dictionary_entries)!=self.concrete_type_ids: errors.append("dictionary/concrete-taxonomy parity mismatch")
        if len(self.relation_ids)!=len(self.relationship_types): errors.append("duplicate relation IDs")
        pm=self.package["package_metadata"]
        if pm.get("runtime_activation_state")!="NOT_RUNTIME_ACTIVATED": errors.append("source runtime state changed")
        if pm.get("production_eligible") is not False: errors.append("source unexpectedly production eligible")
        if self.validation.get("validation_status")!="PASS_WITH_GOVERNANCE_GUARDS": errors.append("source validation status mismatch")
        sm=self.validation.get("summary",{})
        if sm.get("total_checks")!=55 or sm.get("passed_checks")!=55 or sm.get("failed_checks")!=0: errors.append("source validation not 55/55")
        rv=self.validation.get("runtime_validation",{})
        if rv.get("status")!="NOT_RUN_RUNTIME_UNAVAILABLE" or rv.get("sandbox_activation_allowed") is not False: errors.append("unexpected runtime validation state")
        align=self.package["legal_rebuild_alignment_v1_3"]
        if align.get("compatibility")!="COMPATIBLE_ADDITIVE": errors.append("compatibility changed")
        if not self.REQUIRED_BOUNDARIES.issubset(set(align.get("immutable_ontology_boundaries",[]))): errors.append("required ontology boundaries missing")
        for ext in self.unresolved_extensions:
            if ext.get("stable_type_id") is not None: errors.append("unresolved extension unexpectedly has stable ID")
        return StatementAdmissionValidationReport(
          *(actual[k] for k in ["statement_event_types","statement_function_types","proposition_types","denial_types",
             "admission_candidate_types","attribution_types","scope_types","explicitness_types","lifecycle_statuses",
             "concrete_taxonomy_types","dictionary_entries","relations","statement_transitions","admission_transitions",
             "backend_models","validation_checks","unresolved_extensions"]),tuple(errors))

    def type(self,tid:str)->Mapping[str,Any]:
        if tid not in self.types: raise StatementAdmissionPackageError(f"unknown type: {tid}")
        return self.types[tid]

@dataclass(frozen=True)
class LoadedStatementAdmissionPackage:
    package_sha256:str
    baseline_sha256:str
    registry:StatementAdmissionRegistry
    registry_report:StatementAdmissionValidationReport
    snapshot:ExecutionSnapshot
    runtime_status:str
    activation_blockers:tuple[str,...]

class StatementAdmissionPackageLoader:
    EXPECTED_PACKAGE_SHA256="d637367b1968eaf35c2277464920ec9f664272c35faef2936a2d0c29fdb062a0"
    EXPECTED_BASELINE_SHA256="f19b51cf0fe54a97d00491f1a852198987d6139809396a0dfce02261f24e2d55"
    def __init__(self,runtime:GovernanceRuntime): self.runtime=runtime
    def load(self,path:str|Path)->LoadedStatementAdmissionPackage:
        payload=Path(path).read_bytes(); digest=sha256(payload).hexdigest()
        if digest!=self.EXPECTED_PACKAGE_SHA256: raise HashMismatchError(f"STATEMENT_ADMISSION package hash mismatch: {digest}")
        package=json.loads(payload)
        align=package["legal_rebuild_alignment_v1_3"]
        baseline=str(align["source_hashes"]["statement_admission_baseline_v1_2_0"])
        if baseline!=self.EXPECTED_BASELINE_SHA256: raise HashMismatchError("STATEMENT_ADMISSION baseline lineage hash mismatch")
        registry=StatementAdmissionRegistry(package); report=registry.validate()
        if not report.valid: raise StatementAdmissionPackageError("; ".join(report.errors))
        self.runtime.register_bytes(artifact_id="STATEMENT_ADMISSION", version="1.3.0", expected_sha256=digest, payload=payload)
        snapshot=self.runtime.snapshot(environment="registry_import")
        blockers=("SOURCE_RUNTIME_NOT_ACTIVATED","RUNTIME_LIVE_VALIDATION_NOT_RUN","HUMAN_REVIEW_REQUIRED_PER_RECORD",
                  "CONSENT_UNRESOLVED_CANONICAL_EXTENSION","WAIVER_UNRESOLVED_CANONICAL_EXTENSION",
                  "LEGAL_ARGUMENT_UNRESOLVED_CANONICAL_EXTENSION","NO_STABLE_INSTANCE_ID_SERVICE",
                  "NO_CANONICAL_RELATION_PERSISTENCE","SPEAKER_RESOLUTION_REQUIRED","CAPACITY_RESOLUTION_REQUIRED",
                  "NO_AUTOMATIC_LEGAL_EFFECT")
        return LoadedStatementAdmissionPackage(digest,baseline,registry,report,snapshot,"LOADED_NOT_ACTIVATED",blockers)

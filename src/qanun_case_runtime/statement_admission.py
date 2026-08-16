from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json, zipfile
from .governance import GovernanceRuntime, GovernanceError, HashMismatchError, ExecutionSnapshot

class StatementAdmissionPackageError(GovernanceError): pass

@dataclass(frozen=True)
class StatementAdmissionValidationReport:
    statement_event_types:int; statement_function_types:int; proposition_types:int; denial_types:int
    admission_candidate_types:int; attribution_types:int; scope_types:int; explicitness_types:int
    lifecycle_statuses:int; concrete_taxonomy_types:int; dictionary_entries:int; relationship_types:int
    statement_transitions:int; admission_transitions:int; backend_models:int; source_validation_checks:int
    unresolved_extensions:int; errors:tuple[str,...]
    @property
    def valid(self): return not self.errors

class StatementAdmissionRegistry:
    EXPECTED={
      'statement_event_types':29,'statement_function_types':37,'proposition_types':45,'denial_types':14,
      'admission_candidate_types':36,'attribution_types':10,'scope_types':7,'explicitness_types':5,
      'lifecycle_statuses':16,'concrete_taxonomy_types':174,'dictionary_entries':174,
      'relationship_types':116,'statement_transitions':16,'admission_transitions':14,'backend_models':14,
      'source_validation_checks':55,'unresolved_extensions':3,
    }
    REQUIRED_BOUNDARIES={
      'STATEMENT_EVENT != STATEMENT_PROPOSITION','STATEMENT_PROPOSITION != FACT','STATEMENT_PROPOSITION != CLAIM',
      'STATEMENT_PROPOSITION != REQUEST','STATEMENT_PROPOSITION != DEFENSE','STATEMENT_PROPOSITION != EVIDENCE_ITEM',
      'ADMISSION_ASSESSMENT != STATEMENT_EVENT','ADMISSION_ASSESSMENT != FACT_TRUTH',
      'ADMISSION_ASSESSMENT != REQUEST_ACCEPTANCE','ADMISSION_ASSESSMENT != EVIDENCE_AUTHENTICITY_FINALITY',
      'CONFESSION_ASSESSMENT != CIVIL_ADMISSION_ASSESSMENT','COURT_POSITION != COURT_NARRATION',
      'REPRESENTATIVE_STATEMENT != PRINCIPAL_STATEMENT','STATEMENT != CONSENT','STATEMENT != WAIVER',
      'STATEMENT != LEGAL_ARGUMENT','CONSENT != WAIVER','CONSENT != ADMISSION','WAIVER != ADMISSION',
      'LEGAL_ARGUMENT != ADMISSION','SIGNATURE_ADMISSION != DOCUMENT_CONTENT_ADMISSION',
      'DOCUMENT_RECEIPT_ADMISSION != DOCUMENT_VALIDITY_ADMISSION',
      'PAYMENT_RECEIPT_ADMISSION != PAYMENT_CAUSE_ADMISSION',
      'PAYMENT_RECEIPT_ADMISSION != OBLIGATION_EXTINGUISHMENT',
      'CONTRACT_EXISTENCE_ADMISSION != CONTRACT_VALIDITY_OR_ENFORCEABILITY','SUPPORTING_EVIDENCE != FACT_TRUTH',
      'NO_LLM_STABLE_IDS'
    }
    SECTIONS=('statement_event_types','statement_function_types','proposition_types','denial_types',
              'admission_candidate_types','attribution_types','scope_types','explicitness_types','lifecycle_statuses')
    def __init__(self, package:Mapping[str,Any]):
        self.package=package; self.pc=package['production_components_v1_3']; self.taxonomy=self.pc['taxonomy']
        self.dictionary=self.pc['dictionary']; self.relations=self.pc['relations']; self.backend=self.pc['backend_contract']
        self.type_sets={s:{str(x['type_id']) for x in self.taxonomy[s]} for s in self.SECTIONS}
        self.all_taxonomy_ids=set().union(*self.type_sets.values())
        self.family_ids={x for x in self.all_taxonomy_ids if x.endswith('_FAMILY')}
        self.concrete_ids=self.all_taxonomy_ids-self.family_ids
        self.dictionary_entries={str(x['type_id']):x for x in self.dictionary['entries']}
        self.relationship_types=tuple(self.relations['relationship_types']); self.relation_ids={str(x['relation_id']) for x in self.relationship_types}
        self.statement_transitions=tuple(self.relations['statement_status_transition_rules'])
        self.admission_transitions=tuple(self.relations['admission_status_transition_rules'])
        self.models=dict(self.backend['models'])
        self.unresolved=tuple(package['legal_rebuild_alignment_v1_3']['unresolved_canonical_extensions'])
    def validate(self)->StatementAdmissionValidationReport:
        errors=[]
        actual={s:len(self.taxonomy[s]) for s in self.SECTIONS}
        actual.update(concrete_taxonomy_types=len(self.concrete_ids), dictionary_entries=len(self.dictionary_entries),
                      relationship_types=len(self.relationship_types), statement_transitions=len(self.statement_transitions),
                      admission_transitions=len(self.admission_transitions), backend_models=len(self.models),
                      source_validation_checks=len(self.pc['validation']['checks']), unresolved_extensions=len(self.unresolved))
        for k,v in self.EXPECTED.items():
            if actual[k]!=v: errors.append(f'{k}: expected {v}, got {actual[k]}')
        if set(self.dictionary_entries)!=self.concrete_ids: errors.append('dictionary not in exact concrete taxonomy parity')
        for seq,key,label in [(self.relationship_types,'relation_id','relation'),(self.statement_transitions,'transition_id','statement transition'),(self.admission_transitions,'transition_id','admission transition')]:
            ids=[x.get(key) for x in seq]
            if len(ids)!=len(set(ids)): errors.append(f'duplicate {label} IDs')
        meta=self.package['package_metadata']; val=self.pc['validation']
        if meta.get('status')!='GOVERNANCE_CANDIDATE_NOT_RUNTIME_ACTIVATED': errors.append('unexpected source package status')
        if meta.get('runtime_activation_state')!='NOT_RUNTIME_ACTIVATED': errors.append('source runtime unexpectedly activated')
        if meta.get('production_eligible') is not False: errors.append('source production eligibility unexpectedly true')
        if val.get('validation_status')!='PASS_WITH_GOVERNANCE_GUARDS': errors.append('source validation not guarded PASS')
        if val.get('blocking_errors'): errors.append('source has blocking errors')
        if val.get('summary',{}).get('failed_checks')!=0: errors.append('source has failed checks')
        if val.get('runtime_validation',{}).get('status')!='NOT_RUN_RUNTIME_UNAVAILABLE': errors.append('unexpected source runtime validation state')
        boundaries=set(self.package['legal_rebuild_alignment_v1_3']['immutable_ontology_boundaries'])
        if not self.REQUIRED_BOUNDARIES.issubset(boundaries): errors.append('required immutable ontology boundaries missing')
        concepts={x.get('concept') for x in self.unresolved}
        if concepts!={'CONSENT','WAIVER','LEGAL_ARGUMENT'}: errors.append('unexpected unresolved extension set')
        if any(x.get('stable_type_id') not in (None,'',False) for x in self.unresolved): errors.append('unresolved extension contains stable type id')
        return StatementAdmissionValidationReport(**{k:actual[k] for k in self.EXPECTED}, errors=tuple(errors))
    def require(self, section:str, type_id:str):
        if type_id not in self.type_sets[section]: raise StatementAdmissionPackageError(f'unknown {section}: {type_id}')
    def require_relation(self, relation_id:str):
        if relation_id not in self.relation_ids: raise StatementAdmissionPackageError(f'unknown relation: {relation_id}')

@dataclass(frozen=True)
class LoadedStatementAdmissionPackage:
    delivery_zip_sha256:str; package_sha256:str; validation_sha256:str; changeset_sha256:str; baseline_sha256:str
    cross_index_context_sha256:str; registry:StatementAdmissionRegistry; registry_report:StatementAdmissionValidationReport
    snapshot:ExecutionSnapshot; runtime_status:str; activation_blockers:tuple[str,...]

class StatementAdmissionPackageLoader:
    PACKAGE='QANUN_AI_STATEMENT_ADMISSION_UNIFIED_V1.3.0_LEGAL_REBUILT_GOVERNANCE_CANDIDATE.json'
    VALIDATION='QANUN_AI_STATEMENT_ADMISSION_REBUILD_VALIDATION_V1.3.0.json'
    CHANGESET='QANUN_AI_STATEMENT_ADMISSION_REBUILD_CHANGESET_V1.3.0.json'
    MANIFEST='DELIVERY_MANIFEST_V1.3.0.json'
    BASELINE='BASELINE_IMMUTABLE/QANUN_AI_STATEMENT_ADMISSION_UNIFIED_PRODUCTION_V1_2(3).json'
    CONTEXT='SOURCE_CONTEXT/CROSS_INDEX_LEGAL_IMPACT_MASTER(1).md'
    def __init__(self,runtime:GovernanceRuntime): self.runtime=runtime
    @staticmethod
    def digest(b:bytes): return sha256(b).hexdigest()
    def load(self,path:str|Path)->LoadedStatementAdmissionPackage:
        p=Path(path); zip_bytes=p.read_bytes(); zip_sha=self.digest(zip_bytes)
        with zipfile.ZipFile(p) as z:
            required={self.PACKAGE,self.VALIDATION,self.CHANGESET,self.MANIFEST,self.BASELINE,self.CONTEXT}
            missing=required-set(z.namelist())
            if missing: raise StatementAdmissionPackageError(f'delivery missing files: {sorted(missing)}')
            manifest=json.loads(z.read(self.MANIFEST)); rows={r['file_name']:r for r in manifest['files']}
            for n in (self.PACKAGE,self.VALIDATION,self.CHANGESET):
                b=z.read(n); r=rows.get(n)
                if not r: raise StatementAdmissionPackageError(f'manifest missing {n}')
                if len(b)!=r['size_bytes'] or self.digest(b)!=r['sha256']: raise HashMismatchError(f'manifest mismatch: {n}')
            pb=z.read(self.PACKAGE); vb=z.read(self.VALIDATION); cb=z.read(self.CHANGESET); bb=z.read(self.BASELINE); xb=z.read(self.CONTEXT)
            package=json.loads(pb); validation=json.loads(vb)
        baseline_sha=self.digest(bb); context_sha=self.digest(xb)
        source_hashes=manifest['source_hashes']
        if baseline_sha!=source_hashes['statement_admission_baseline_v1_2_0']: raise HashMismatchError('embedded v1.2 baseline hash mismatch')
        if context_sha!=source_hashes['cross_index_legal_impact_master']: raise HashMismatchError('cross-index context hash mismatch')
        package_sha=self.digest(pb)
        if package_sha!=validation.get('rebuilt_package_sha256'): raise HashMismatchError('package hash differs from validation')
        if baseline_sha!=validation.get('baseline_package_sha256'): raise HashMismatchError('baseline hash differs from validation')
        registry=StatementAdmissionRegistry(package); report=registry.validate()
        if not report.valid: raise StatementAdmissionPackageError('; '.join(report.errors[:12]))
        self.runtime.register_bytes(artifact_id='STATEMENT_ADMISSION',version='1.3.0',expected_sha256=package_sha,payload=pb)
        snap=self.runtime.snapshot(environment='registry_import')
        blockers=('SOURCE_RUNTIME_NOT_ACTIVATED','SOURCE_RUNTIME_LIVE_VALIDATION_NOT_RUN','NO_AUTOMATIC_CLASSIFICATION',
                  'NO_AUTOMATIC_RELATION_WRITES','NO_AUTOMATIC_LEGAL_EFFECT','NO_STABLE_INSTANCE_ID_SERVICE',
                  'NO_CANONICAL_PERSISTENCE','ENTITY_RESOLUTION_REQUIRED','CAPACITY_AT_STATEMENT_TIME_REQUIRED',
                  'LEGAL_REFERENCE_TEMPORAL_VALIDITY_REQUIRED','UNRESOLVED_CONSENT_WAIVER_LEGAL_ARGUMENT')
        return LoadedStatementAdmissionPackage(zip_sha,package_sha,self.digest(vb),self.digest(cb),baseline_sha,context_sha,
                                               registry,report,snap,'LOADED_NOT_ACTIVATED',blockers)

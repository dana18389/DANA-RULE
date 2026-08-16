from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json

class DecisionPositionPackageError(RuntimeError):
    pass

def _sha_file(path: str|Path)->str:
    return sha256(Path(path).read_bytes()).hexdigest()

def _sha_obj(obj: Any)->str:
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return sha256(raw).hexdigest()

@dataclass(frozen=True)
class DecisionPositionRegistry:
    judicial_act_type_ids:frozenset[str]
    decision_type_ids:frozenset[str]
    court_position_type_ids:frozenset[str]
    disposition_type_ids:frozenset[str]
    legal_authority_use_type_ids:frozenset[str]
    relation_ids:frozenset[str]
    decision_type_to_family:Mapping[str,str]
    dictionary_by_type:Mapping[str,Mapping[str,Any]]

    def require(self, kind:str, value:str)->str:
        pools={
            'judicial_act':self.judicial_act_type_ids,
            'decision_type':self.decision_type_ids,
            'court_position':self.court_position_type_ids,
            'disposition':self.disposition_type_ids,
            'legal_authority_use':self.legal_authority_use_type_ids,
            'relation':self.relation_ids,
        }
        if value not in pools[kind]:
            raise DecisionPositionPackageError(f'unknown {kind}: {value}')
        return value

@dataclass(frozen=True)
class LoadedDecisionPositionPackage:
    package:Mapping[str,Any]
    report_text:str
    package_sha256:str
    report_sha256:str
    registry:DecisionPositionRegistry
    validation:Mapping[str,Any]

class DecisionPositionPackageLoader:
    EXPECTED_PACKAGE_VERSION='QANUN-DP-SY-1.2.0-LEGAL-REBUILD-CANDIDATE.2026-08-15'
    EXPECTED_STATUS='PRODUCTION_CANDIDATE_NOT_FROZEN'
    def load(self, package_json_path:str|Path, report_md_path:str|Path)->LoadedDecisionPositionPackage:
        p=Path(package_json_path); r=Path(report_md_path)
        package=json.loads(p.read_text(encoding='utf-8'))
        report=r.read_text(encoding='utf-8')
        if package.get('package_version')!=self.EXPECTED_PACKAGE_VERSION:
            raise DecisionPositionPackageError('unexpected package_version')
        if package.get('status')!=self.EXPECTED_STATUS:
            raise DecisionPositionPackageError('unexpected package status')
        if package.get('merge_mode')!='LOSSLESS_COMPATIBLE_ADDITIVE_LEGAL_REBUILD':
            raise DecisionPositionPackageError('unexpected merge mode')
        comps=package.get('components') or {}
        required={'taxonomy','dictionary','relations','backend_contract','validation','original_manifest'}
        if set(comps) != required:
            raise DecisionPositionPackageError(f'component set mismatch: {set(comps)}')
        for name in required:
            c=comps[name]
            if _sha_obj(c['content']) != c['content_sha256']:
                raise DecisionPositionPackageError(f'component content sha mismatch: {name}')
            if c['content_sha256'] != c['source_byte_sha256']:
                raise DecisionPositionPackageError(f'component source/content sha mismatch: {name}')
        val=comps['validation']['content']
        s=val['summary']
        if not (val.get('validation_status')=='PASS' and s.get('validation_checks_total')==37 and s.get('validation_checks_passed')==37 and s.get('validation_checks_needing_revision')==0):
            raise DecisionPositionPackageError('static validation is not 37/37 PASS')
        if val.get('runtime_validation_status')!='NOT_RUN_RUNTIME_UNAVAILABLE':
            raise DecisionPositionPackageError('source runtime state unexpectedly changed')
        if val.get('activation_status')!='BLOCKED_PENDING_SANDBOX_RUNTIME_VALIDATION':
            raise DecisionPositionPackageError('source activation state unexpectedly changed')
        if not all(x.get('status')=='PASS_STATIC_GUARD_PRESENT' for x in val.get('prompt_validation_37',[])):
            raise DecisionPositionPackageError('prompt_validation_37 not all PASS')
        tax=comps['taxonomy']['content']; dic=comps['dictionary']['content']; rel=comps['relations']['content']
        decision_to_family={}
        decision_ids=set()
        for fam in tax['decision_families']:
            for dt in fam.get('decision_types',[]):
                did=str(dt['decision_type_id']); decision_ids.add(did); decision_to_family[did]=str(fam['family_id'])
        dictionary_by_type={str(e['type_id']):e for e in dic['dictionary_entries']}
        if set(dictionary_by_type) != decision_ids | {str(x['id']) for x in tax['court_position_types']}:
            raise DecisionPositionPackageError('dictionary/taxonomy parity mismatch')
        reg=DecisionPositionRegistry(
            judicial_act_type_ids=frozenset(str(x['judicial_act_type_id']) for x in tax['judicial_act_types']),
            decision_type_ids=frozenset(decision_ids),
            court_position_type_ids=frozenset(str(x['id']) for x in tax['court_position_types']),
            disposition_type_ids=frozenset(str(x['id']) for x in tax['disposition_item_types']),
            legal_authority_use_type_ids=frozenset(str(x['id']) for x in tax['legal_authority_use_types']),
            relation_ids=frozenset(str(x['relation_id']) for x in rel['relationship_types']),
            decision_type_to_family=decision_to_family,
            dictionary_by_type=dictionary_by_type,
        )
        expected=(32,202,76,28,104,278,6)
        got=(len(reg.judicial_act_type_ids),len(reg.decision_type_ids),len(reg.court_position_type_ids),
             len(reg.disposition_type_ids),len(reg.relation_ids),len(dictionary_by_type),
             s['backend_record_model_count'])
        if got != expected:
            raise DecisionPositionPackageError(f'inventory mismatch {got} != {expected}')
        return LoadedDecisionPositionPackage(package,report,_sha_file(p),_sha_file(r),reg,val)

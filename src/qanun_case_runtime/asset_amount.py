from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json, zipfile
from .governance import GovernanceRuntime

class AssetAmountPackageError(RuntimeError): pass

@dataclass(frozen=True)
class AssetAmountRegistry:
    type_ids:frozenset[str]
    relation_ids:frozenset[str]
    dictionary_entry_count:int
    schema_def_count:int
    unresolved_extensions:tuple[str,...]
    def require_type(self, type_id:str)->str:
        if type_id not in self.type_ids: raise AssetAmountPackageError(f'unknown type_id: {type_id}')
        return type_id
    def require_relation(self, relation_id:str)->str:
        if relation_id not in self.relation_ids: raise AssetAmountPackageError(f'unknown relation_id: {relation_id}')
        return relation_id

@dataclass(frozen=True)
class LoadedAssetAmountPackage:
    delivery_zip_sha256:str
    package_sha256:str
    validation_sha256:str
    changeset_sha256:str
    baseline_sha256:str
    cross_index_specs_sha256:str
    cross_index_context_sha256:str
    package:Mapping[str,Any]
    validation:Mapping[str,Any]
    changeset:Mapping[str,Any]
    cross_index_specs:Mapping[str,Any]
    registry:AssetAmountRegistry

class AssetAmountPackageLoader:
    PACKAGE='asset_amount_backend_monolith.production.v1.2.0_LEGAL_REBUILT_GOVERNANCE_CANDIDATE.json'
    VALIDATION='QANUN_AI_ASSET_AMOUNT_REBUILD_VALIDATION_V1.2.0.json'
    CHANGESET='QANUN_AI_ASSET_AMOUNT_REBUILD_CHANGESET_V1.2.0.json'
    CROSS='QANUN_AI_ASSET_AMOUNT_CROSS_INDEX_REGRESSION_SPECS_V1.2.0.json'
    MANIFEST='DELIVERY_MANIFEST_V1.2.0.json'
    BASELINE='BASELINE_IMMUTABLE/asset_amount_backend_monolith.production.v1.1.0 (1).json'
    CONTEXT='SOURCE_CONTEXT/CROSS_INDEX_LEGAL_IMPACT_MASTER(1).md'
    def __init__(self, governance:GovernanceRuntime): self.governance=governance
    @staticmethod
    def _sha(b:bytes)->str: return sha256(b).hexdigest()
    def load(self,path:str|Path)->LoadedAssetAmountPackage:
        p=Path(path); zbytes=p.read_bytes(); zsha=self._sha(zbytes)
        with zipfile.ZipFile(p) as z:
            manifest=json.loads(z.read(self.MANIFEST))
            rows={x['file_name']:x for x in manifest['files']}
            for name,row in rows.items():
                b=z.read(name)
                if len(b)!=row['size_bytes'] or self._sha(b)!=row['sha256']:
                    raise AssetAmountPackageError(f'manifest mismatch: {name}')
            pb=z.read(self.PACKAGE); vb=z.read(self.VALIDATION); cb=z.read(self.CHANGESET); xb=z.read(self.CROSS)
            bb=z.read(self.BASELINE); ctx=z.read(self.CONTEXT)
        package=json.loads(pb); validation=json.loads(vb); changeset=json.loads(cb); cross=json.loads(xb)
        if package.get('package_version')!='1.2.0-legal-rebuilt-governance-candidate' or package.get('authoritative_domain_version')!='1.2.0': raise AssetAmountPackageError('wrong package version')
        if package.get('status')!='GOVERNANCE_CANDIDATE_NOT_RUNTIME_ACTIVATED': raise AssetAmountPackageError('source activation state changed')
        if validation.get('validation_status')!='PASS_WITH_GOVERNANCE_GUARDS': raise AssetAmountPackageError('validation status not acceptable')
        if validation.get('summary',{}).get('static_governance_failure_count')!=0: raise AssetAmountPackageError('source validation failures')
        if package.get('production_gate',{}).get('production_eligible') is not False: raise AssetAmountPackageError('source production gate must remain false')
        rv=package['runtime_v1_2']['modules']; entries=rv['dictionary']['entries']; rels=rv['relations']['relationship_types']
        tids=frozenset(str(e['type_id']) for e in entries)
        rids=frozenset(str(r['relation_id']) for r in rels)
        unresolved=tuple(x['concept'] for x in package.get('legal_rebuild_alignment_v1_2',{}).get('unresolved_canonical_extensions',[]))
        reg=AssetAmountRegistry(tids,rids,len(entries),len(rv['schemas'].get('$defs',{})),unresolved)
        lin=package['legal_rebuild_alignment_v1_2']['source_hashes']
        if self._sha(bb)!=lin['asset_amount_baseline_v1_1_0']: raise AssetAmountPackageError('baseline hash mismatch')
        if self._sha(ctx)!=lin['cross_index_legal_impact_master']: raise AssetAmountPackageError('cross-index context hash mismatch')
        self.governance.register_bytes(artifact_id='ASSET_AMOUNT_DELIVERY_V1.2.0',version='1.2.0',expected_sha256=zsha,payload=zbytes)
        return LoadedAssetAmountPackage(zsha,self._sha(pb),self._sha(vb),self._sha(cb),self._sha(bb),self._sha(xb),self._sha(ctx),package,validation,changeset,cross,reg)

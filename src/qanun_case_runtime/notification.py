from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json, zipfile

class NotificationPackageError(RuntimeError): pass

@dataclass(frozen=True)
class NotificationRegistry:
    notification_type_ids:frozenset[str]
    notification_status_ids:frozenset[str]
    attempt_result_ids:frozenset[str]
    validity_status_ids:frozenset[str]
    challenge_type_ids:frozenset[str]
    court_assessment_status_ids:frozenset[str]
    deadline_trigger_status_ids:frozenset[str]
    relation_ids:frozenset[str]
    def require_relation(self, rid:str)->str:
        if rid not in self.relation_ids: raise NotificationPackageError(f'unknown relation id: {rid}')
        return rid

@dataclass(frozen=True)
class LoadedNotificationPackage:
    package:Mapping[str,Any]
    validation:Mapping[str,Any]
    changeset:Mapping[str,Any]
    cross_index_specs:Mapping[str,Any]
    lineage:Mapping[str,Any]
    manifest:Mapping[str,Any]
    baseline:Mapping[str,Any]
    registry:NotificationRegistry
    delivery_zip_sha256:str
    package_sha256:str
    baseline_sha256:str

class NotificationPackageLoader:
    VERSION='1.1.0'
    PKG='QANUN_AI_NOTIFICATION_PRODUCTION_PACKAGE_V1.1.0_LEGAL_REBUILT_GOVERNANCE_CANDIDATE.json'
    VAL='QANUN_AI_NOTIFICATION_REBUILD_VALIDATION_V1.1.0.json'
    CHG='QANUN_AI_NOTIFICATION_REBUILD_CHANGESET_V1.1.0.json'
    XI='QANUN_AI_NOTIFICATION_CROSS_INDEX_REGRESSION_SPECS_V1.1.0.json'
    LIN='QANUN_AI_NOTIFICATION_SOURCE_LINEAGE_V1.1.0.json'
    MAN='DELIVERY_MANIFEST_V1.1.0.json'
    BASE='BASELINE_IMMUTABLE/QANUN_AI_NOTIFICATION_PRODUCTION_PACKAGE_V1.0.0(2).json'
    def load(self, path:str|Path)->LoadedNotificationPackage:
        path=Path(path); raw=path.read_bytes(); zsha=sha256(raw).hexdigest()
        with zipfile.ZipFile(path) as z:
            data={n:z.read(n) for n in z.namelist()}
        for n in (self.PKG,self.VAL,self.CHG,self.XI,self.LIN,self.MAN,self.BASE):
            if n not in data: raise NotificationPackageError(f'missing {n}')
        manifest=json.loads(data[self.MAN])
        for row in manifest.get('files',[]):
            n=row.get('file') or row.get('path') or row.get('name') or row.get('filename')
            if not n or n not in data: raise NotificationPackageError(f'manifest missing file: {n}')
            expected=row.get('sha256')
            if expected and sha256(data[n]).hexdigest()!=expected: raise NotificationPackageError(f'hash mismatch: {n}')
            size=row.get('size') or row.get('bytes') or row.get('size_bytes')
            if size is not None and len(data[n])!=int(size): raise NotificationPackageError(f'size mismatch: {n}')
        package=json.loads(data[self.PKG]); validation=json.loads(data[self.VAL]); changeset=json.loads(data[self.CHG]); xi=json.loads(data[self.XI]); lineage=json.loads(data[self.LIN]); baseline=json.loads(data[self.BASE])
        pver=str(package.get('package_metadata',{}).get('package_version',''))
        if not pver.startswith(self.VERSION): raise NotificationPackageError(f'wrong package version: {pver}')
        release=package.get('release_decision',{})
        if release.get('production_eligible') is not False: raise NotificationPackageError('source package must remain production-ineligible')
        if release.get('automatic_legal_validity_decisions') not in (False,'DISABLED',None): raise NotificationPackageError('automatic validity unexpectedly enabled')
        if release.get('automatic_deadline_activation') not in (False,'DISABLED',None): raise NotificationPackageError('automatic deadline unexpectedly enabled')
        if validation.get('summary',{}).get('blocking_failures') not in ([],None): raise NotificationPackageError('blocking validation failures')
        pkgsha=sha256(data[self.PKG]).hexdigest(); basesha=sha256(data[self.BASE]).hexdigest()
        reg=self._registry(package)
        return LoadedNotificationPackage(package,validation,changeset,xi,lineage,manifest,baseline,reg,zsha,pkgsha,basesha)
    def _registry(self,p:Mapping[str,Any])->NotificationRegistry:
        rt=p.get('production_runtime_v1_1') or p.get('production_runtime') or {}
        cat=rt.get('notification_operational_catalog',{})
        def ids_from(obj):
            if isinstance(obj,list):
                out=[]
                for x in obj:
                    if isinstance(x,str): out.append(x)
                    elif isinstance(x,dict):
                        for k in ('id','type_id','notification_type_id','status_id','result_id','challenge_type_id','validity_status_id','assessment_status_id','deadline_trigger_status_id'):
                            if x.get(k): out.append(str(x[k])); break
                return frozenset(out)
            if isinstance(obj,dict): return frozenset(map(str,obj.keys()))
            return frozenset()
        def find(keys):
            for k in keys:
                if k in cat: return ids_from(cat[k])
            return frozenset()
        relcat=rt.get('relationship_catalog',{})
        rels=frozenset()
        if isinstance(relcat,list): rels=ids_from(relcat)
        elif isinstance(relcat,dict):
            tmp=[]
            for v in relcat.values(): tmp.extend(ids_from(v))
            rels=frozenset(tmp)
        return NotificationRegistry(
            find(('notification_types','notification_type_catalog','types')),
            find(('notification_statuses','statuses')),
            find(('attempt_results','service_attempt_results')),
            find(('validity_statuses','notification_validity_statuses')),
            find(('challenge_types','service_challenge_types')),
            find(('court_assessment_statuses','assessment_statuses')),
            find(('deadline_trigger_statuses','deadline_statuses')),
            rels,
        )

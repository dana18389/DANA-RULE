from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json, zipfile

EXPECTED_ZIP_SHA256='139cc534885921563b6d525f37f9727b0abfeb1f54d803c0686d84d5c99cf048'
EXPECTED_PACKAGE_SHA256='10933df0de4009f0c0106ba14f325ac6ddabdc17f1780bae597e87c263f15189'
EXPECTED_BASELINE_SHA256='2541dd4920f3ee1efd91d60a6a1d5b4f9cc4f4eb662464a85d5b363926893ff6'
EXPECTED_VALIDATION_SHA256='eac4f44509a07fed35dc195f882e60fd33e3ceb41622ab81994236117475f23a'
EXPECTED_CROSS_INDEX_SHA256='94b1ebf08a77956179f0f8f5dc0c8c801a015d0ed657bda075a57d6acebd4ace'
EXPECTED_CONTEXT_SHA256='42e9b4acddf385b03eef037ef5cc8db3610f9cf4f7357a3544a55b5cbe3f0a18'

class ProcedureHearingPackageError(RuntimeError): pass

@dataclass(frozen=True)
class LoadedProcedureHearingPackage:
    delivery_zip_sha256:str
    package_sha256:str
    baseline_sha256:str
    validation_sha256:str
    cross_index_sha256:str
    package:Mapping[str,Any]
    validation:Mapping[str,Any]
    cross_index_specs:Mapping[str,Any]
    manifest:Mapping[str,Any]

class ProcedureHearingPackageLoader:
    PACKAGE_NAME='QANUN_PROCEDURE_HEARING_SY_v1.2.0_LEGAL_REBUILT_GOVERNANCE_CANDIDATE.json'
    VALIDATION_NAME='QANUN_PROCEDURE_HEARING_REBUILD_VALIDATION_V1.2.0.json'
    CROSS_NAME='QANUN_PROCEDURE_HEARING_CROSS_INDEX_REGRESSION_SPECS_V1.2.0.json'
    MANIFEST_NAME='DELIVERY_MANIFEST_V1.2.0.json'
    BASELINE_NAME='BASELINE_IMMUTABLE/QANUN_PROCEDURE_HEARING_SY_v1.1.0_CONSOLIDATED_PRODUCTION(3).json'
    CONTEXT_NAME='SOURCE_CONTEXT/CROSS_INDEX_LEGAL_IMPACT_MASTER(1).md'
    @staticmethod
    def _h(b:bytes)->str: return sha256(b).hexdigest()
    def load(self,path:str|Path)->LoadedProcedureHearingPackage:
        p=Path(path); raw=p.read_bytes(); zsha=self._h(raw)
        if zsha!=EXPECTED_ZIP_SHA256: raise ProcedureHearingPackageError('delivery zip hash mismatch')
        with zipfile.ZipFile(p) as z:
            manifest=json.loads(z.read(self.MANIFEST_NAME))
            for item in manifest['files']:
                b=z.read(item['file_name'])
                if len(b)!=int(item['size_bytes']) or self._h(b)!=item['sha256']:
                    raise ProcedureHearingPackageError('manifest mismatch: '+item['file_name'])
            pb=z.read(self.PACKAGE_NAME); vb=z.read(self.VALIDATION_NAME); cb=z.read(self.CROSS_NAME)
            bb=z.read(self.BASELINE_NAME); xb=z.read(self.CONTEXT_NAME)
        if self._h(pb)!=EXPECTED_PACKAGE_SHA256 or self._h(bb)!=EXPECTED_BASELINE_SHA256 or self._h(vb)!=EXPECTED_VALIDATION_SHA256 or self._h(cb)!=EXPECTED_CROSS_INDEX_SHA256 or self._h(xb)!=EXPECTED_CONTEXT_SHA256:
            raise ProcedureHearingPackageError('authoritative hash mismatch')
        package=json.loads(pb); validation=json.loads(vb); cross=json.loads(cb)
        if validation.get('validation_status')!='PASS_WITH_GOVERNANCE_GUARDS': raise ProcedureHearingPackageError('bad static status')
        if validation.get('summary',{}).get('static_legal_rebuild_pass_count')!=55: raise ProcedureHearingPackageError('expected 55 pass')
        if cross.get('case_count')!=18: raise ProcedureHearingPackageError('expected 18 cross specs')
        if manifest.get('production_eligible') is not False: raise ProcedureHearingPackageError('production must remain false')
        return LoadedProcedureHearingPackage(zsha,self._h(pb),self._h(bb),self._h(vb),self._h(cb),package,validation,cross,manifest)

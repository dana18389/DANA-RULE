from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from typing import Any, Mapping, Sequence
import json,re
from .asset_amount import LoadedAssetAmountPackage, AssetAmountPackageError

@dataclass(frozen=True)
class AssetAmountCandidate:
    candidate_id:str; case_id:str; source_document_id:str; entity_kind:str; type_id:str|None; source_quote:str
    amount_decimal_string:str|None=None; currency_code:str|None=None; role:str|None=None; comparator:str|None=None
    status:str='EXTRACTED_CANDIDATE'; derived:bool=False; quoted:bool=False; disputed:bool=False
    canonical_persistence_allowed:bool=False; automatic_legal_effect_allowed:bool=False; stable_id:None=None

@dataclass(frozen=True)
class AssetAmountRelationCandidate:
    relation_candidate_id:str; relation_id:str; case_id:str; source_ref:str; target_ref:str; source_document_id:str
    source_quote:str; status:str='RELATION_CANDIDATE_ONLY_UNVERIFIED'; canonical_persistence_allowed:bool=False

@dataclass(frozen=True)
class AssetAmountResult:
    candidates:tuple[AssetAmountCandidate,...]; relations:tuple[AssetAmountRelationCandidate,...]; guard_signals:tuple[str,...]; projection_sha256:str

_NUM=re.compile(r'(?<!\d)(\d{1,3}(?:[,٬]\d{3})+|\d+)(?:\.(\d+))?')
_WORDS={
'عشرة ملايين':10000000,'عشره ملايين':10000000,'خمسة ملايين':5000000,'خمسه ملايين':5000000,
'عشرين مليون':20000000,'مائة مليون':100000000,'مئه مليون':100000000,'خمسين مليون':50000000,
'تسعين مليون':90000000,'مائة وعشرون مليون':120000000,'مئه وعشرون مليون':120000000,
'خمسمئة وأربعون مليون':540000000,'خمسمئه واربعون مليون':540000000,'ثلاثمئة مليون':300000000,
'مئة مليون':100000000,'مائه مليون':100000000,'سبعة ملايين':7000000,'سبعه ملايين':7000000,
'تسعة ملايين':9000000,'تسعه ملايين':9000000,'أربعة ملايين':4000000,'اربعه ملايين':4000000,
}

def norm(s:str)->str:
    s=re.sub(r'[\u064b-\u065f\u0670\u0640]','',s)
    for a,b in [('أ','ا'),('إ','ا'),('آ','ا'),('ى','ي'),('ؤ','و'),('ئ','ي'),('ة','ه')]: s=s.replace(a,b)
    return ' '.join(re.sub(r'[^\u0621-\u064A0-9%/.,_-]+',' ',s).split()).strip()

def _sha(obj:Any)->str:
    return sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def _currency(text:str)->str|None:
    n=norm(text)
    if 'دولار' in n or 'usd' in n.lower(): return 'USD'
    if 'ل س' in n or 'ل.س' in n or 'ليره سوريه' in n or 'ليره' in n: return 'SYP'
    return None

def _amounts(text:str):
    out=[]
    for m in _NUM.finditer(text):
        raw=m.group(0); digits=m.group(1).replace(',','').replace('٬','')
        val=digits+(('.'+m.group(2)) if m.group(2) else '')
        a=max(0,m.start()-32); b=min(len(text),m.end()+40); ctx=text[a:b]
        if '/' in raw: continue
        if re.search(r'\b(?:19|20)\d{2}\b',raw) and not re.search(r'ل\.?س|ليره|دولار|مبلغ|قيمه|ثمن|اجره|دين|فائده',norm(ctx)): continue
        if len(digits)<=4 and not re.search(r'ل\.?س|ليره|دولار|مبلغ|قيمه|ثمن|اجره|دين|فائده|غرام|%',norm(ctx)): continue
        out.append((m.start(),m.end(),raw,val,ctx))
    n=norm(text)
    for w,v in _WORDS.items():
        nw=norm(w); idx=n.find(nw)
        if idx>=0: out.append((10**9+idx,10**9+idx+len(nw),w,str(v),w))
    out.sort(key=lambda x:x[0])
    return out

class AssetAmountSandboxRuntime:
    VERSION='ASSET_AMOUNT_GOVERNED_RULE_MATCHER_V1'
    STATUS='SANDBOX_RUNTIME_ENABLED_CANDIDATE_ONLY'
    EXPECTED_DELIVERY_ZIP_SHA256='975341a698c86dde58978a190d99487cc1b5951ab9aa7ce03a9e311c9c7f19a9'
    EXPECTED_PACKAGE_SHA256='298b39d5e372c0308189279250c69b51a97105486c763b46426db142f73dfeb0'
    EXPECTED_STATEMENT_ADMISSION_PROJECTION='b88eb1a62e6ded8aad57bc78c614655b296bdc8caa56f36f2d18fe21ac3a9b11'
    def __init__(self,loaded:LoadedAssetAmountPackage, statement_admission_projection_sha256:str):
        self.loaded=loaded; self.registry=loaded.registry; self.statement_projection=statement_admission_projection_sha256
        if loaded.delivery_zip_sha256!=self.EXPECTED_DELIVERY_ZIP_SHA256: raise AssetAmountPackageError('delivery ZIP hash mismatch')
        if loaded.package_sha256!=self.EXPECTED_PACKAGE_SHA256: raise AssetAmountPackageError('package hash mismatch')
        if loaded.package['authoritative_domain_version']!='1.2.0': raise AssetAmountPackageError('wrong package')
        if loaded.package['production_gate']['production_eligible'] is not False: raise AssetAmountPackageError('production gate violated')
        if statement_admission_projection_sha256!=self.EXPECTED_STATEMENT_ADMISSION_PROJECTION: raise AssetAmountPackageError('upstream STATEMENT_ADMISSION projection mismatch')
    def _cid(self,prefix,seed): return prefix+_sha(seed)[:24]
    def _cand(self,case,doc,kind,type_id,quote,**kw):
        if type_id and type_id in self.registry.type_ids: self.registry.require_type(type_id)
        cid=self._cid('aacand_',{'c':case,'d':doc,'k':kind,'t':type_id,'q':quote,'kw':kw})
        return AssetAmountCandidate(cid,case,doc,kind,type_id,quote,**kw)
    def _rel(self,case,doc,rid,s,t,q):
        self.registry.require_relation(rid)
        return AssetAmountRelationCandidate(self._cid('aarel_',{'c':case,'d':doc,'r':rid,'s':s,'t':t,'q':q}),rid,case,s,t,doc,q)
    def extract(self,*,case_id:str,source_document_id:str,raw_text:str,derived_secondary_source:bool=False)->AssetAmountResult:
        if derived_secondary_source:
            p={'c':[],'r':[],'g':['DERIVED_SECONDARY_SOURCE_NO_PRIMARY_FINANCIAL_FACTS']}; return AssetAmountResult((),(),tuple(p['g']),_sha(p))
        n=norm(raw_text); c=[]; r=[]; guards=set()
        for i,(_,__,raw,val,ctx) in enumerate(_amounts(raw_text)):
            cur=_currency(ctx or raw_text)
            typ='MONETARY_EXPRESSION.EXACT'
            if 'تقارب' in norm(ctx) or 'يقارب' in norm(ctx): typ='MONETARY_EXPRESSION.APPROXIMATE'
            if 'لا يقل' in norm(ctx): typ='MONETARY_EXPRESSION.MINIMUM'
            if 'حتى مبلغ' in norm(ctx): typ='MONETARY_EXPRESSION.MAXIMUM'
            if 'شهري' in n: typ='MONETARY_EXPRESSION.PERIODIC_AMOUNT'
            if 'سعر القطعه' in n: typ='MONETARY_EXPRESSION.UNIT_PRICE'
            if '%' in raw_text and ('فائده' in n or 'سنويا' in n): typ='MONETARY_EXPRESSION.INTEREST_RATE'
            if 'اجماليا' in n: typ='MONETARY_EXPRESSION.GROSS_AMOUNT'
            q=ctx.strip() or raw
            e=self._cand(case_id,source_document_id,'MONETARY_EXPRESSION',typ,q,amount_decimal_string=val,currency_code=cur,quoted=('وجاء في الحكم السابق' in n))
            v=self._cand(case_id,source_document_id,'MONETARY_VALUE',None,q,amount_decimal_string=val,currency_code=cur)
            c.extend([e,v]); r.append(self._rel(case_id,source_document_id,'MONETARY_EXPRESSION_RECORDED_IN_DOCUMENT',e.candidate_id,source_document_id,q)); r.append(self._rel(case_id,source_document_id,'MONETARY_EXPRESSION_NORMALIZES_TO_VALUE',e.candidate_id,v.candidate_id,q))
        def add(kind,type_id,quote=None,**kw):
            x=self._cand(case_id,source_document_id,kind,type_id,quote or raw_text[:500],**kw); c.append(x); return x
        if any(x in n for x in ['عقار','شقه','المقسم','البناء']): add('ASSET_MENTION','ASSET.IMMOVABLE.REAL_ESTATE')
        if any(x in n for x in ['مركبه','سياره']): add('ASSET_MENTION','ASSET.MOVABLE.VEHICLE')
        if 'ذهب' in n: add('ASSET_MENTION','ASSET.MOVABLE.JEWELRY_GOLD')
        if 'شيك' in n: add('ASSET_MENTION','ASSET.PAYMENT_INSTRUMENT.CHEQUE'); guards.add('PAYMENT_EVIDENCE_SUPPORT_ONLY')
        if 'رهن' in n or 'تامين' in n:
            add('ASSET_MENTION','ASSET.RIGHT.MORTGAGE'); guards.add('SECURITY_CANDIDATE_WITH_UNRESOLVED_DIMENSIONS')
            if 'مسجل' in n: guards.add('SECURITY_EXISTS_OR_REGISTERED_CANDIDATE'); guards.add('PRIORITY_UNRESOLVED')
            if any(x in n for x in ['ترقين','تحرير ضمان','تحرير الرهن']): guards.add('SECURITY_RELEASE_SCOPE_REQUIRED')
        if 'حياز' in n or 'سلمت الشقه' in n: guards.add('IN_POSSESSION')
        if 'ملكي' in n: guards.add('OWNERSHIP_CLAIMED')
        if any(x in n for x in ['دفع','سدد','استلم','قبض','حواله','تحويل مصرفي','المقبوض']):
            pa=add('PAYMENT_ASSERTION',None,disputed=('مختلف' in n or 'نزاع' in n or 'انكر' in n))
            guards.add('PAYMENT_ASSERTION_OR_EVENT')
            if any(x in n for x in ['جزء','جزئ','جزءا']): guards.add('PARTIAL_PAYMENT')
            if any(x in n for x in ['مختلف على سبب','لمعامله','بدل اجره','دون الاقرار بسبب']): guards.add('PAYMENT_CAUSE_DISPUTED'); guards.add('PAYMENT_CAUSE_SEPARATE')
            if any(x in n for x in ['اقر بقبض','اقر باستلام','استلمت من']): guards.add('RECEIPT_EVENT_OR_PROPOSITION')
        if any(x in n for x in ['يطالب','طلب المدعي','طلب مبلغ','يسرد طلب','نلتمس','يعرض مبلغ','مستعدون لدفع']):
            add('FINANCIAL_REQUEST',None); guards.add('REQUESTED_AMOUNT_OR_NARRATION_ONLY')
        if any(x in n for x in ['يقدر المدعي','تقدر المركبه']): add('VALUATION_ASSESSMENT','VALUATION_TYPE.PARTY_ESTIMATE')
        if 'الخبير' in n and any(x in n for x in ['قيمه','يقدر','خلص']):
            add('VALUATION_ASSESSMENT','VALUATION_TYPE.EXPERT_VALUE'); guards.add('EXPERT_VALUE_CANDIDATE')
        if 'المحكمه' in n and 'اعتمدت' in n and 'الخبير' in n:
            guards.add('COURT_ADOPTED_SCOPE_EXPLICIT_ONLY')
            if 'فقط' in n or 'جزء' in n: guards.add('COURT_PARTIAL_ADOPTION')
        dispositive=any(x in n for x in ['لذلك حكمت المحكمه','حكمت المحكمه له','حكم بمبلغ','الزام المدعى عليه بان يدفع'])
        narration=any(x in n for x in ['وعرضت المحكمه','وجاء في الحكم السابق','ورد في الحكم السابق'])
        if dispositive and not narration:
            add('COURT_POSITION','COURT_FINANCIAL_POSITION.AWARDS_AMOUNT'); guards.add('COURT_AWARDS_AMOUNT_EXPLICIT')
        if any(x in n for x in ['نفذ منه','تحصيل تنفيذي','التنفيذ','حصل منه']):
            guards.add('ENFORCEMENT_CONTEXT_SEPARATE')
            if any(x in n for x in ['جزئي','جزيي','نفذ منه','بقي','رصيد']): guards.add('PARTIAL_COLLECTION'); guards.add('OUTSTANDING_BALANCE')
        if 'حكم تحكيمي' in n: guards.add('ARBITRAL_AMOUNT_CONTEXT'); guards.add('ENFORCEMENT_CONTEXT_SEPARATE')
        if any(x in n for x in ['او ما يعادله','تعادل','معادل']) and not ('سعر صرف' in n and 'تاريخ' in n): guards.add('AMOUNT_EQUIVALENCE_CANDIDATE')
        if any(x in n for x in ['فائده','فايده']) and any(x in n for x in ['قانوني','الماده','القانون']): guards.add('DERIVATION_BLOCKED_PENDING_CURRENT_LAW_VALIDITY')
        p={'c':[x.__dict__ for x in c],'r':[x.__dict__ for x in r],'g':sorted(guards),'stable_ids_issued':False,'canonical_persistence_allowed':False,'automatic_legal_effect_allowed':False}
        return AssetAmountResult(tuple(c),tuple(r),tuple(sorted(guards)),_sha(p))

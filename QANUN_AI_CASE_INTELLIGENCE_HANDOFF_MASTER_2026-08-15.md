# QANUN AI — CASE INTELLIGENCE HANDOFF MASTER — 2026-08-15

**Status:** CONTINUITY MASTER / SELF-CONTAINED SNAPSHOT  
**Generated:** 2026-08-15, Europe/Warsaw context  
**Repository Source of Truth:** `https://github.com/dana18389/DANA-RULE`  
**Captured code-state HEAD:** `9d9a75746fedc9017e927e4c6d324bdbe2d43c58`  
**Important:** the commit that adds this handoff is documentation-only and will be later than the captured runtime HEAD. On resume, verify the branch HEAD and confirm that no runtime/config/test files changed after `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` before treating a later HEAD as semantically equivalent.

---

## 1. Purpose and binding continuity rule

This document exists so a new ChatGPT conversation can continue QANUN AI Case Intelligence without restarting the project, reopening settled decisions, or silently changing a frozen baseline.

GitHub is the Source of Truth. Conversation history is secondary. When sources conflict, use this precedence:

1. Frozen authoritative GitHub artifact.
2. Governance state.
3. Runtime / validation evidence tied to the same commit.
4. Golden fixture / Golden assertions.
5. This Handoff Master.
6. Conversation narrative.

A conflict suspends only the conflicting point; it does not reopen the entire project.

---

## 2. Current authoritative state

```text
DOCUMENT    → FROZEN
PARTY       → FROZEN
REQUEST     → FROZEN
DEFENSE     → FROZEN SANDBOX RUNTIME BASELINE
FACT_EVENT  → FROZEN SANDBOX RUNTIME BASELINE
```

### Phase 1

`PHASE_1_RUNTIME_BASELINE` is the frozen test baseline for DOCUMENT + PARTY + REQUEST.

- Git path: `config/phase1_runtime_baseline.json`
- Snapshot URL: https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/phase1_runtime_baseline.json
- Stable projection SHA-256: `86a0fd5861ca16d095745d5402a6086a8f5f7c885d32914340b55b3e53271524`
- Execution mode: `OFFLINE_FIXTURE_TEST`
- Production eligible: `false`

### DEFENSE

Authoritative runtime baseline:

```text
DEFENSE_RUNTIME_BASELINE_V1
=
FROZEN_SANDBOX_BASELINE_LOCAL_VERIFIED
```

- Git path: `config/defense_runtime_baseline_v1.json`
- Snapshot URL: https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/defense_runtime_baseline_v1.json
- DEFENSE package SHA-256: `6cb68fa2e5f62d12230c3e7096f02cb43e321ac0522b1c37ab574991cdd6117f`
- DEFENSE delivery ZIP SHA-256: `98de044c3029635451786ed7c60f46a161529934dfb2e7673f6e169137971039`
- Runtime projection SHA-256: `6b1a616ad3f75d1c79ed326e1c5af7380ba742ede3b704ba1355515228047a4d`
- `config/defense_v1_3_shadow_baseline.json` remains historical evidence; it is superseded for current runtime status by `config/defense_runtime_baseline_v1.json`, not deleted.

### FACT_EVENT

```text
FACT_EVENT_RUNTIME_BASELINE_V1
=
FROZEN_SANDBOX_BASELINE_LOCAL_VERIFIED
```

- Git path: `config/fact_event_runtime_baseline_v1.json`
- Snapshot URL: https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/fact_event_runtime_baseline_v1.json
- FACT_EVENT package SHA-256: `8c7fc4f186a8dda6c7840c3346a4b6c3301cbb82621b42a466529363eabdc198`
- FACT_EVENT delivery ZIP SHA-256: `6060a6d561f503e12ad642d8c6c5d7c957b5271c6d720728b7dc63bf97868e31`
- Activation patch SHA-256 recorded in baseline: `94c4a69dc32012901fe417c9a0a0647546bc32c8db056d4599320ad048498e4f`
- **Frozen Golden runtime projection SHA-256:** `e01e34176ee6b96e401dd38f93d9f6bc6bcd5bb37e71a8e32d75b974a0ddb4cb`

Do not confuse the projection SHA with the source fixture hashes:
- Source Golden DOCX SHA-256: `83fc2b2324750246bd5dc3e3d0fd4d89de67bc8c38192d97c3f43e712508d970`
- Golden fixture JSON SHA-256 recorded by baseline: `af3858d22a2b1eba4cbc9b4071ca7f2d0ca92c9ae85969822db3e2474300050b`
- Frozen FACT_EVENT runtime projection SHA-256: `e01e34176ee6b96e401dd38f93d9f6bc6bcd5bb37e71a8e32d75b974a0ddb4cb`

---

## 3. FACT_EVENT frozen runtime result

Golden Case: `CASE-SY-DAM-REALTY-2022-000731`, D01–D30.

```text
55 Candidates
├── 37 EVENT
├── 12 FACT
└── 6 STATE

6 Assertion Candidates
81 Relation Candidates
```

Truth/status distribution:

```text
DOCUMENTED       = 46
ALLEGED          = 5
EXPERT_SUPPORTED = 3
COURT_FOUND      = 1
```

Validated guards:

- receipt `12/04/2022` and bank execution `13/04/2022` remain distinct;
- event date is separated from referenced-document date;
- `REGISTRATION ≠ OWNERSHIP`;
- `POSSESSION ≠ OWNERSHIP`;
- party allegations stay `ALLEGED`;
- expert observation remains `EXPERT_SUPPORTED`, not a judicial finding;
- `COURT_FOUND` requires explicit court-source language;
- historical mention of the 150M deposit in the appeal response does not create a new payment event;
- original case and judicial-liability related case remain separate scopes;
- D29 notice for 390M creates neither a filed case nor an executive title;
- D30 is a derived/secondary source and creates no new FACT/EVENT/STATE.

```text
same input rerun       → PASS
reverse input order    → PASS
stable IDs generated   → NO
canonical persistence  → NO
automatic legal effect → NO
```

The three `NO` values above are intentional governance behavior at this stage, not failures.

---

## 4. GitHub state at snapshot

```text
Repository       = dana18389/DANA-RULE
Repository URL   = https://github.com/dana18389/DANA-RULE
Visibility       = PUBLIC
Default branch   = main
Working branch   = agent/governance-runtime-m1
Branch URL       = https://github.com/dana18389/DANA-RULE/tree/agent/governance-runtime-m1
Draft PR         = #1
PR URL           = https://github.com/dana18389/DANA-RULE/pull/1
PR Status        = OPEN / DRAFT
Milestones       = 1–7
Mergeable        = YES at snapshot
Base branch      = main
Base SHA         = 812f3e185f50b2920853200bd9c4574f0b0cd251
Code-state HEAD  = 9d9a75746fedc9017e927e4c6d324bdbe2d43c58
Changed files    = 29
Commits in PR    = 44
Tags             = NONE
Releases         = NONE
```

Pinned code-state HEAD URL:
https://github.com/dana18389/DANA-RULE/commit/9d9a75746fedc9017e927e4c6d324bdbe2d43c58

Full Milestones 1–7 comparison:
https://github.com/dana18389/DANA-RULE/compare/812f3e185f50b2920853200bd9c4574f0b0cd251...9d9a75746fedc9017e927e4c6d324bdbe2d43c58

### CI / production status

```text
Local Runtime Regression = PASS
GitHub CI                  = NOT_RUN_NO_WORKFLOW
Production Activation      = FALSE
```

GitHub Actions has no configured workflow at this snapshot. Never rewrite the above as `CI_PASS` or `PRODUCTION_READY`.

---

## 5. Immutable Governance hashes

Governance repository manifest:
- Git path: `config/governance_v1_1_manifest.json`
- URL: https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/governance_v1_1_manifest.json

Recorded immutable source hashes:

```text
Governance delivery ZIP                 ba67faab762f7286c9164747a3bc2e26933e5627f502293f2de44d9880f35e8a
DOCUMENT                                bf607f3dc03b426de47a1bc6cde0f3392ee882aaa2001cb14fb8b1956defab4d
PARTY                                   47993bdd98de1a644dd4352815ce33e9be1da2b0ef7e8697f934fe5c0b87d5f0
REQUEST                                 4e6908192f2f529a356f4c105a0afb6a5cf6987d9167ab75f0b8055a45e69e80
DOCUMENT_PARTY                          d4a750a682d28f4c36558f56c791dfa5f0c34a87f410685f9a5aed43f735bc8d
DOCUMENT_PARTY_COMPATIBILITY_ADAPTER    f74fffe6faed04b8e2fa0f24e121a8c207ec03f3a3a1f1364cb2c7db0f6fd59d
REQUEST_CROSS_INDEX                     59934d7a5a37f81cf84cffb10cd8afe547d383bf0c1187d52cc3a92311738360
THREE_INDEX_BINDING                     047af04aef2aa95ae84bf61b7d273b36af042186c6312c47c17226bae6e8b4cf
GOVERNANCE_V1                           6cd46a3d65afed5d5d1730944939db55e5a0def6a9d70ce8932bd93bf2bfde33
```

Phase-1 production blockers remain:

```text
UNKNOWN_EXTRACTION_PROFILE_FOR_226_DOCUMENT_BINDINGS
PARTY_RESOLUTION_SERVICE_NOT_PRESENT_IN_SOURCE_PACKAGE
REQUEST_IDENTITY_SERVICE_NOT_PRESENT_IN_SOURCE_PACKAGE
```

---

## 6. Authoritative file manifest — all 29 PR files at captured HEAD

Every URL below is pinned to the captured code-state HEAD. `Commit SHA` therefore means the exact snapshot commit carrying that file content; milestone-origin/freeze commits are recorded separately below.

| File | Purpose | Index / Module | Version | Status | Git Path | GitHub URL | Commit SHA | Authoritative | Supersedes | Superseded By |
|---|---|---|---|---|---|---|---|---|---|---|
| `README.md` | Repository/runtime overview | CORE | working | ACTIVE_SUPPORTING | `README.md` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/README.md | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `config/governance_v1_1_manifest.json` | Immutable Governance V1.1 artifact hashes and production gate | GOVERNANCE | 1.1 | AUTHORITATIVE | `config/governance_v1_1_manifest.json` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/governance_v1_1_manifest.json | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `config/phase1_runtime_baseline.json` | Frozen DOCUMENT/PARTY/REQUEST Phase-1 runtime baseline | DOCUMENT/PARTY/REQUEST | V1 | FROZEN_AUTHORITATIVE | `config/phase1_runtime_baseline.json` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/phase1_runtime_baseline.json | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `config/defense_v1_3_shadow_baseline.json` | Historical DEFENSE shadow validation baseline | DEFENSE | 1.3.0 shadow | SUPERSEDED_FOR_RUNTIME_BY_DEFENSE_RUNTIME_BASELINE_V1 | `config/defense_v1_3_shadow_baseline.json` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/defense_v1_3_shadow_baseline.json | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | config/defense_runtime_baseline_v1.json |
| `config/defense_runtime_activation_patch_v1.json` | Compatible-additive DEFENSE sandbox activation patch | DEFENSE | V1 | AUTHORITATIVE_PATCH | `config/defense_runtime_activation_patch_v1.json` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/defense_runtime_activation_patch_v1.json | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `config/defense_runtime_baseline_v1.json` | Frozen DEFENSE sandbox runtime baseline | DEFENSE | V1 | FROZEN_AUTHORITATIVE | `config/defense_runtime_baseline_v1.json` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/defense_runtime_baseline_v1.json | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | DEFENSE_V1_3_SHADOW_BASELINE | — |
| `config/fact_event_runtime_activation_patch_v1.json` | Compatible-additive FACT_EVENT sandbox activation/routing patch | FACT_EVENT | V1 | AUTHORITATIVE_PATCH | `config/fact_event_runtime_activation_patch_v1.json` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/fact_event_runtime_activation_patch_v1.json | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `config/fact_event_runtime_baseline_v1.json` | Frozen FACT_EVENT sandbox runtime baseline and regression result | FACT_EVENT | V1 | FROZEN_AUTHORITATIVE | `config/fact_event_runtime_baseline_v1.json` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/fact_event_runtime_baseline_v1.json | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `pyproject.toml` | Python package/test dependency configuration | ENGINEERING | 0.1.0 | ACTIVE_SUPPORTING | `pyproject.toml` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/pyproject.toml | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/__init__.py` | Exported runtime surface | RUNTIME | working | ACTIVE_SUPPORTING | `src/qanun_case_runtime/__init__.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/__init__.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/governance.py` | Governance runtime safety layer | GOVERNANCE | working | ACTIVE_SUPPORTING | `src/qanun_case_runtime/governance.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/governance.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/contracts.py` | Governance contract registry and candidate pipeline | INTEGRATION | working | ACTIVE_SUPPORTING | `src/qanun_case_runtime/contracts.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/contracts.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/bundle.py` | Governance delivery ZIP loader/hash verifier | GOVERNANCE | working | ACTIVE_SUPPORTING | `src/qanun_case_runtime/bundle.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/bundle.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/offline.py` | Offline fixture execution and schema/cross-index validation | RUNTIME | working | ACTIVE_SUPPORTING | `src/qanun_case_runtime/offline.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/offline.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/batch.py` | Deterministic Phase-1 DOCUMENT/PARTY/REQUEST batch orchestrator | DOCUMENT/PARTY/REQUEST | working | ACTIVE_SUPPORTING | `src/qanun_case_runtime/batch.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/batch.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/defense.py` | DEFENSE v1.3 registry/loader/shadow routing | DEFENSE | 1.3.0 adapter | ACTIVE_SUPPORTING | `src/qanun_case_runtime/defense.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/defense.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/defense_runtime.py` | DEFENSE candidate-only raw-text sandbox runtime | DEFENSE | V1 | ACTIVE_SUPPORTING | `src/qanun_case_runtime/defense_runtime.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/defense_runtime.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/fact_event.py` | FACT_EVENT v0.3 registry/loader | FACT_EVENT | 0.3.0 adapter | ACTIVE_SUPPORTING | `src/qanun_case_runtime/fact_event.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/fact_event.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/fact_event_runtime.py` | FACT_EVENT candidate-only raw-text sandbox runtime | FACT_EVENT | V1 | ACTIVE_SUPPORTING | `src/qanun_case_runtime/fact_event_runtime.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/fact_event_runtime.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `src/qanun_case_runtime/fact_event_batch.py` | Deterministic FACT_EVENT batch orchestrator | FACT_EVENT | V1 | ACTIVE_SUPPORTING | `src/qanun_case_runtime/fact_event_batch.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/fact_event_batch.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_governance.py` | Governance runtime unit tests | GOVERNANCE | working | AUTHORITATIVE_TEST | `tests/test_governance.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_governance.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_governance_delivery_contract.py` | Real Governance delivery contract integration test | GOVERNANCE | working | AUTHORITATIVE_TEST | `tests/test_governance_delivery_contract.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_governance_delivery_contract.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_contracts_unit.py` | Contract registry unit tests | INTEGRATION | working | AUTHORITATIVE_TEST | `tests/test_contracts_unit.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_contracts_unit.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_bundle.py` | Governance bundle verification tests | GOVERNANCE | working | AUTHORITATIVE_TEST | `tests/test_bundle.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_bundle.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_offline_runtime.py` | Offline governed runtime integration tests | DOCUMENT/PARTY/REQUEST | working | AUTHORITATIVE_TEST | `tests/test_offline_runtime.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_offline_runtime.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_batch_orchestrator.py` | Phase-1 Golden batch identity/request/determinism tests | DOCUMENT/PARTY/REQUEST | working | AUTHORITATIVE_TEST | `tests/test_batch_orchestrator.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_batch_orchestrator.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_defense_v1_3_shadow.py` | DEFENSE v1.3 shadow governance/routing tests | DEFENSE | 1.3.0 | AUTHORITATIVE_TEST | `tests/test_defense_v1_3_shadow.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_defense_v1_3_shadow.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_defense_runtime_activation.py` | DEFENSE raw-text sandbox activation/regression tests | DEFENSE | V1 | AUTHORITATIVE_TEST | `tests/test_defense_runtime_activation.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_defense_runtime_activation.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |
| `tests/test_fact_event_runtime_v1.py` | FACT_EVENT v1 critical governance regression tests | FACT_EVENT | V1 | AUTHORITATIVE_TEST | `tests/test_fact_event_runtime_v1.py` | https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_fact_event_runtime_v1.py | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | YES at snapshot | — | — |

Notes:
- `config/defense_v1_3_shadow_baseline.json` is retained for audit/history, not the current DEFENSE runtime baseline.
- No other PR file was identified as deprecated/superseded at this snapshot.
- Blob SHA is available through the Git tree; content SHA-256 is recorded where governance/baselines require it. Git blob SHA must not be mislabeled as SHA-256.

---

## 7. Relevant Git history for Milestones 1–7

The branch is 44 commits ahead of base. The following are the milestone-defining commits needed for continuity; use the full compare link above for every intermediate export/test commit.

| Milestone / purpose | Commit SHA | Message |
|---|---|---|
| Repository base | `812f3e185f50b2920853200bd9c4574f0b0cd251` | initialize case intelligence backend |
| Governance runtime | `cc4c65e2ae1a2ed56ee3803d5d6de14eaf9e0b8f` | implement governance runtime safety layer |
| Governance hashes | `d1c7863733b85680bb7dab2042a4e7b149e4e602` | register governance v1.1 immutable hashes |
| Contract registry | `61e16d7e3f85c3aa95f96c049c13ef48eb4874a7` | add contract registry and sandbox candidate pipeline |
| Verified Governance loader | `ac42e896beb5db8854d7a5e2aaf316336ffddd5b` | add verified governance delivery bundle loader |
| Offline runtime | `818e5ca09e450805d48c09e7477846f50d1def16` | add deterministic offline fixture execution engine |
| PARTY/REQUEST handoffs | `11b7d831c96656bb56e6cf97fdc4155cabe8faa5` | build real party and request candidate handoffs offline |
| Cross-index export | `cd6d51db5af7fc47fcd2ebf6d9aa13b84a8428c0` | export cross-index offline candidate types |
| Phase-1 batch | `f4a17b87fabcbeb2430f22ced6638307bbaa4f2c` | add deterministic phase1 batch orchestration |
| Freeze Phase-1 | `c43582b6cea2922a2e1601ae53d235e6b173ad78` | freeze phase1 golden runtime baseline |
| Phase-1 identity/request tests | `a84ff86b59757b242a014680d5415a373e1b2664` | test phase1 batch identity and request behavior |
| DEFENSE loader | `d1a463a6d90bd97949cf127ceea74a4ed4393b20` | add governed defense v1.3 shadow loader |
| Freeze DEFENSE shadow | `c61070f6481b1a245480c257808f4ff4d540ae11` | freeze defense v1.3 shadow validation baseline |
| DEFENSE raw-text runtime | `7dd5cb05dc4173fc096c21039137799c91920717` | add defense raw text sandbox runtime |
| DEFENSE activation patch | `9d731e26ab77d7f5457143bb138e3b4fd2fd69de` | add defense sandbox activation patch |
| DEFENSE runtime tests | `79705def6cfdd3ede310cdde647b2475c0f7cee5` | test defense raw text sandbox runtime |
| Freeze DEFENSE runtime | `cdf44b7d851d52c82287531558011838fa1e2078` | freeze defense sandbox runtime baseline v1 |
| FACT_EVENT loader | `2b0f2df61d0dcee2e3e108c432014a86d12a0e88` | add FACT_EVENT v0.3 governed loader |
| FACT_EVENT runtime | `6a0a8dff7f16b79b3d65a05701e85d4306e3f698` | add FACT_EVENT sandbox runtime |
| FACT_EVENT batch | `e439e35206c89636091855498f2367c854dfa068` | add FACT_EVENT deterministic batch runner |
| FACT_EVENT activation patch | `c7ea06ad9ddc8013857e6bb38952445901dc1e4c` | add FACT_EVENT sandbox activation patch |
| Initial FACT_EVENT freeze | `b93c7dc42761d5d95c8fa9d9c2d4cc8f5c5791e2` | freeze FACT_EVENT sandbox runtime baseline |
| FACT_EVENT routing guards | `7e860c5d4161b83024ff0eacc887c6cfb70f4fa3` | align FACT_EVENT runtime with golden routing guards |
| Authoritative FACT_EVENT baseline alignment | `494dfd41950859c82171f025c45ddd4e8e8b926d` | align FACT_EVENT baseline with published runtime |
| FACT_EVENT regression tests | `1e55d69130116c102e7437a084b844f76e5e0fbc` | add FACT_EVENT governance regression tests |
| Code-state HEAD at handoff snapshot | `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` | export FACT_EVENT runtime surface |

For a new chat, the **runtime semantic snapshot** is `9d9a75746fedc9017e927e4c6d324bdbe2d43c58`. A later handoff-only documentation commit does not change that semantic runtime snapshot.

---

## 8. Golden Case and regression artifacts

Case ID: `CASE-SY-DAM-REALTY-2022-000731`.

Golden source:
- File name: `QANUN_AI_SYRIAN_CASE_LITIGATION_SCENARIO_V1.docx`
- D01–D30
- Data class: `DATA_TEST_SYNTHETIC`
- Source DOCX SHA-256 recorded in FACT_EVENT baseline: `83fc2b2324750246bd5dc3e3d0fd4d89de67bc8c38192d97c3f43e712508d970`
- The synthetic package explicitly states that it is not a real judicial file and that party statements are not automatically facts.

Golden runtime result:
- `config/fact_event_runtime_baseline_v1.json`
- https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/fact_event_runtime_baseline_v1.json

FACT_EVENT regression tests:
- `tests/test_fact_event_runtime_v1.py`
- https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_fact_event_runtime_v1.py

Phase-1 regression:
- `config/phase1_runtime_baseline.json`
- `tests/test_batch_orchestrator.py`

DEFENSE regression:
- `config/defense_runtime_baseline_v1.json`
- `tests/test_defense_runtime_activation.py`

### Continuity artifact availability

The Golden DOCX was available to the working conversation/library and was used to reconstruct exact D01–D30 text, but the DOCX itself is **not committed in the captured Git tree**.

The baseline records a Golden fixture JSON SHA-256 (`af3858...`), but no standalone Golden fixture JSON file is present in the 29-file repository tree.

Therefore:

```text
MISSING_HANDOFF_ARTIFACT:
- GitHub copy of QANUN_AI_SYRIAN_CASE_LITIGATION_SCENARIO_V1.docx
- Standalone Golden fixture JSON whose recorded SHA-256 is af3858d22a2b1eba4cbc9b4071ca7f2d0ca92c9ae85969822db3e2474300050b
```

Do not silently reconstruct or replace either file in a new chat. The frozen regression result remains valid; replay requiring exact source bytes must be blocked until the artifact is supplied or versioned into GitHub.

---

## 9. Source delivery archives and validation reports

The code contains loaders and the baselines contain verified SHA-256 values, but the source ZIP archives themselves are not present in the captured Git tree.

### Governance

Expected archive:
`CASE_EXTRACTION_GOVERNANCE_V1_1_DELIVERY.zip`

Recorded SHA-256:
`ba67faab762f7286c9164747a3bc2e26933e5627f502293f2de44d9880f35e8a`

Runtime verifier:
`src/qanun_case_runtime/bundle.py`

### DEFENSE

Expected delivery:
`QANUN_AI_DEFENSE_REBUILD_DELIVERY_v1.3.0` / corresponding ZIP

Recorded delivery SHA-256:
`98de044c3029635451786ed7c60f46a161529934dfb2e7673f6e169137971039`

Recorded package SHA-256:
`6cb68fa2e5f62d12230c3e7096f02cb43e321ac0522b1c37ab574991cdd6117f`

Runtime verifier:
`src/qanun_case_runtime/defense.py`

### FACT_EVENT

Expected archive:
`QANUN_AI_FACT_EVENT_REBUILD_DELIVERY_V0.3.0(1).zip`

Recorded delivery SHA-256:
`6060a6d561f503e12ad642d8c6c5d7c957b5271c6d720728b7dc63bf97868e31`

Recorded package SHA-256:
`8c7fc4f186a8dda6c7840c3346a4b6c3301cbb82621b42a466529363eabdc198`

Runtime verifier:
`src/qanun_case_runtime/fact_event.py`

The original validation reports/manifests are inside/associated with the delivery packages and are not standalone committed files in the captured tree.

```text
MISSING_HANDOFF_ARTIFACT:
- Governance source delivery ZIP and its internal schemas/manifests/reports
- DEFENSE source delivery ZIP and internal validation report/changeset/manifest
- FACT_EVENT source delivery ZIP and internal validation report/changeset/manifest
```

The hashes remain authoritative evidence of what was verified. Do not claim an exact replay is possible from GitHub alone until these archives are available.

---

## 10. Baseline protection and change policy

Treat the following as immutable according to their current statuses:

```text
DOCUMENT
PARTY
REQUEST
DEFENSE
FACT_EVENT
```

Forbidden without a versioned governance process:

```text
Silent overwrite
Silent rename
Canonical ID change
Schema semantic change
Relation semantic change
Lifecycle semantic change
```

Before changing a frozen area, classify the finding as exactly one or more of:

```text
ENGINEERING_BUG
RUNTIME_BUG
INTEGRATION_GAP
MAPPING_GAP
BASELINE_GAP
LEGAL_SEMANTIC_GAP
TEST_FIXTURE_ERROR
GOVERNANCE_CHANGE
```

A frozen baseline may change only by:

```text
VERSIONED_PATCH
or
NEW_BASELINE_VERSION
```

and the change must include:

```text
Impact
Migration
Backward Compatibility
Golden Regression
Rollback
```

Do not reopen DOCUMENT/PARTY/REQUEST/DEFENSE/FACT_EVENT merely because a new conversation starts.

---

## 11. Non-negotiable runtime semantics already settled

- no name-only merge;
- attorney ≠ party;
- request ≠ court disposition;
- candidate ≠ canonical unique entity;
- no LLM stable IDs;
- no final relation to unresolved party/target;
- opponent statement ≠ established fact;
- expert opinion ≠ court judgment;
- quoted/historical judgment ≠ current judgment;
- registration ≠ ownership;
- possession ≠ ownership;
- temporal sequence ≠ causation;
- appeal/cassation grounds are assertions/challenges, not established facts;
- derived summary D30 cannot create primary case truth;
- judicial-liability action is a related/subcase scope, not a fourth ordinary appeal instance.

---

## 12. OPEN_ENGINEERING_GAPS

These gaps are engineering/runtime matters. They are not automatically Baseline Gaps:

1. `GitHub CI workflow`: no Actions workflow/checks exist.
2. `Production persistence`: not implemented/approved.
3. `Stable ID service`: production stable-instance service not ready.
4. `Canonical persistence`: intentionally disabled.
5. `Database migrations`: no production migration layer is established in this PR.
6. `Database constraints/indexes`: production DB constraints/indexes are not established here.
7. `Idempotency`: relation/persistence idempotency is still a blocker.
8. `Concurrency`: production concurrency controls are not established.
9. `Outbox / transaction boundaries`: production outbox/transaction boundaries are not established.
10. `Audit trail`: candidate/provenance model exists conceptually/runtime-side; production persistent audit implementation remains open.
11. `Observability`: no production metrics/tracing/alerting baseline.
12. `Feature flags`: production activation/shadow flags require a production control plane.
13. `Rollback`: versioned rollback mechanism is required before production activation.
14. `Production shadow mode`: sandbox candidate-only exists; production shadow deployment is not established.
15. `Production activation`: `FALSE`.
16. `Live LLM/schema binding`: not run for DEFENSE/FACT_EVENT; Phase-1 extraction profiles remain unresolved.
17. `Entity resolution`: PARTY/entity production resolver remains unavailable.
18. `Canonical REQUEST/DEFENSE relation mapping`: required by FACT_EVENT cross-index relations.
19. `Current-law resolver`: required where source packages flag legal-validity recheck.
20. `Deadline rule registry`: required for dependent temporal/legal deadline semantics.
21. `Source archives in GitHub`: Governance, DEFENSE, FACT_EVENT delivery ZIPs are not committed.
22. `Golden source/fixture in GitHub`: source DOCX and standalone fixture JSON are not committed.

---

## 13. OPEN_LEGAL_OR_SEMANTIC_GAPS

Only legal/taxonomy/ontology decisions belong here; engineers must not resolve these by ad-hoc code:

1. FACT_EVENT unresolved extension: `ARBITRAL_AWARD_ISSUANCE_REMAINS_UNRESOLVED_NO_STABLE_EVENT_ID`.
2. FACT_EVENT unresolved extension: `FORMAL_TENDER_OR_LEGAL_DEPOSIT_MAY_REQUIRE_DISTINCT_CANONICAL_TYPE`.
3. Current-law validity must be rechecked wherever DEFENSE/FACT_EVENT source flags require it; taxonomy presence is not proof of current Syrian-law validity.
4. Any future distinction between procedural tender, court deposit, payment/performance, and legal effect must be resolved at taxonomy/legal-governance level before adding a canonical ID.
5. `DECISION_POSITION_ARBITRAL_AWARD_MODEL_REQUIRED` remains a semantic/dependency issue for the relevant relation surface.

No new canonical IDs, schemas, relations, or legal semantics may be invented to close these gaps.

---

## 14. Current production blockers by baseline

### Phase 1

```text
UNKNOWN_EXTRACTION_PROFILE_FOR_226_DOCUMENT_BINDINGS
PARTY_RESOLUTION_SERVICE_NOT_PRESENT_IN_SOURCE_PACKAGE
REQUEST_IDENTITY_SERVICE_NOT_PRESENT_IN_SOURCE_PACKAGE
```

### DEFENSE

```text
LIVE_LLM_SCHEMA_BINDING_NOT_RUN
PARTY_ENTITY_RESOLUTION_SERVICE_NOT_PRODUCTION_READY
DEFENSE_STABLE_ID_SERVICE_NOT_PRODUCTION_READY
DEFENSE_RELATION_PERSISTENCE_AND_IDEMPOTENCY_NOT_PRODUCTION_READY
CURRENT_LAW_VALIDITY_RECHECK_REQUIRED_WHERE_FLAGGED
GITHUB_CI_NOT_CONFIGURED_FOR_RUNTIME_TESTS
```

### FACT_EVENT

```text
CANONICAL_REQUEST_REGISTRY_MAPPING_REQUIRED
CANONICAL_DEFENSE_REGISTRY_MAPPING_REQUIRED
DECISION_POSITION_ARBITRAL_AWARD_MODEL_REQUIRED
LEGAL_REFERENCE_CURRENT_LAW_RESOLVER_REQUIRED
DEADLINE_RULE_REGISTRY_REQUIRED
ENTITY_RESOLUTION_REQUIRED
STABLE_INSTANCE_ID_SERVICE_REQUIRED
RELATION_PERSISTENCE_IDEMPOTENCY_REQUIRED
LIVE_LLM_SCHEMA_BINDING_NOT_RUN
```

Plus the two unresolved source-declared canonical extensions identified above.

---

## 15. Next approved index

```text
NEXT INDEX = EVIDENCE
```

Structural reason:

```text
FACT
   ↓
SUPPORTED_BY
   ↓
EVIDENCE

EVENT
   ↓
SUPPORTED_BY
   ↓
EVIDENCE
```

EVIDENCE integration must be `COMPATIBLE ADDITIVE` against immutable:

```text
DOCUMENT
PARTY
REQUEST
DEFENSE
FACT_EVENT
```

If EVIDENCE requires changing any frozen baseline, create a Patch Proposal and do not modify silently.

Following planned target:

```text
STATEMENT_ADMISSION
```

It must connect STATEMENT / ADMISSION / PARTY / FACT / EVENT / EVIDENCE / COURT_POSITION while preserving:

```text
Statement by party ≠ Fact
Allegation ≠ Court Finding
Admission ≠ Universal truth outside its scope
Expert opinion ≠ Court judgment
```

---

## 16. START NEW CHAT — exact continuity instruction

Read:

`QANUN_AI_CASE_INTELLIGENCE_HANDOFF_MASTER_2026-08-15.md`

completely and treat it as binding continuation context.

Repository:
https://github.com/dana18389/DANA-RULE

Draft PR:
https://github.com/dana18389/DANA-RULE/pull/1

Working branch:
https://github.com/dana18389/DANA-RULE/tree/agent/governance-runtime-m1

Captured runtime code-state HEAD:
https://github.com/dana18389/DANA-RULE/commit/9d9a75746fedc9017e927e4c6d324bdbe2d43c58

First verify GitHub and confirm that later commits after `9d9a75746fedc9017e927e4c6d324bdbe2d43c58` are either handoff/documentation-only or explicitly versioned changes. Then read the authoritative baselines, runtime files, and tests linked in this Handoff.

Confirm only the following continuity state before proceeding:

```text
DOCUMENT    → FROZEN
PARTY       → FROZEN
REQUEST     → FROZEN
DEFENSE     → FROZEN SANDBOX RUNTIME BASELINE
FACT_EVENT  → FROZEN SANDBOX RUNTIME BASELINE

FACT_EVENT_RUNTIME_BASELINE_V1
=
FROZEN_SANDBOX_BASELINE_LOCAL_VERIFIED

Local Runtime Regression = PASS
GitHub CI = NOT_RUN_NO_WORKFLOW
Production Activation = FALSE
```

Do not restart the project. Do not redo full validation of a frozen index merely because this is a new conversation. Do not modify any frozen baseline. Do not create IDs, relations, schemas, or legal semantics absent from authoritative packages.

If there is a conflict, record a Finding and identify its source before changing anything.

Then continue directly from:

```text
NEXT INDEX = EVIDENCE
```

After EVIDENCE:

```text
STATEMENT_ADMISSION
```

---

## 17. Required links for continuity

Repository:
https://github.com/dana18389/DANA-RULE

Draft PR:
https://github.com/dana18389/DANA-RULE/pull/1

Branch:
https://github.com/dana18389/DANA-RULE/tree/agent/governance-runtime-m1

Captured HEAD:
https://github.com/dana18389/DANA-RULE/commit/9d9a75746fedc9017e927e4c6d324bdbe2d43c58

Governance manifest:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/governance_v1_1_manifest.json

Phase-1 frozen baseline (DOCUMENT/PARTY/REQUEST):
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/phase1_runtime_baseline.json

DEFENSE frozen runtime baseline:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/defense_runtime_baseline_v1.json

DEFENSE activation patch:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/defense_runtime_activation_patch_v1.json

FACT_EVENT frozen runtime baseline:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/fact_event_runtime_baseline_v1.json

FACT_EVENT activation patch:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/config/fact_event_runtime_activation_patch_v1.json

FACT_EVENT runtime:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/fact_event_runtime.py

FACT_EVENT batch:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/fact_event_batch.py

FACT_EVENT regression tests:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/tests/test_fact_event_runtime_v1.py

DEFENSE runtime:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/defense_runtime.py

Phase-1 batch:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/batch.py

Governance loader:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/bundle.py

Contract registry:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/contracts.py

Offline runtime:
https://github.com/dana18389/DANA-RULE/blob/9d9a75746fedc9017e927e4c6d324bdbe2d43c58/src/qanun_case_runtime/offline.py

Compare / commit history:
https://github.com/dana18389/DANA-RULE/compare/812f3e185f50b2920853200bd9c4574f0b0cd251...9d9a75746fedc9017e927e4c6d324bdbe2d43c58

Missing direct GitHub links must remain marked `MISSING_HANDOFF_ARTIFACT`; do not substitute guessed URLs.

---

## 18. Final Continuity Gate

```text
[PASS] Current state recorded
[PASS] Frozen baselines identified
[PASS] FACT_EVENT runtime result recorded
[PASS] Golden runtime projection SHA recorded
[PASS] Repository identified
[PASS] PR identified
[PASS] Branch identified
[PASS] Captured runtime Commit SHA recorded
[PASS] Authoritative repository files identified
[PASS] GitHub links recorded for committed artifacts
[PASS] Runtime baseline reports linked
[PARTIAL / MISSING_HANDOFF_ARTIFACT] Exact source delivery ZIPs are not committed
[PARTIAL / MISSING_HANDOFF_ARTIFACT] Golden DOCX and standalone fixture JSON are not committed
[PASS] Open engineering gaps separated
[PASS] Open legal/semantic gaps separated
[PASS] Do-not-change rules recorded
[PASS] Next target = EVIDENCE
[PASS] Following target = STATEMENT_ADMISSION
[PASS] GitHub CI accurately marked NOT_RUN_NO_WORKFLOW
[PASS] Production Activation = FALSE
[PASS] Tags checked = NONE
[PASS] Releases checked = NONE
```

The Handoff is operationally sufficient to understand what was built, frozen, tested, passed, not run, protected, and next. Exact byte-for-byte replay of the external source packages remains intentionally blocked until the `MISSING_HANDOFF_ARTIFACT` archives/fixtures are supplied or versioned into GitHub.

---

## 19. Continuity summary

At this snapshot, Milestones 1–7 are implemented on the Draft PR. Phase 1 (DOCUMENT/PARTY/REQUEST), DEFENSE sandbox runtime, and FACT_EVENT sandbox runtime have frozen baselines. Local runtime evidence is PASS; GitHub CI did not run because no workflow exists; production activation remains false.

The next task is not to rebuild prior indexes. It is to onboard **EVIDENCE** additively against the five immutable baselines, then proceed to **STATEMENT_ADMISSION**.

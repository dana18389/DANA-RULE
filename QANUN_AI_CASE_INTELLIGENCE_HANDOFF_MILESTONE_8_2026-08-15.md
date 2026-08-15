# QANUN AI — CASE INTELLIGENCE HANDOFF — MILESTONE 8 ADDENDUM

**Date:** 2026-08-15  
**Repository:** `dana18389/DANA-RULE`  
**Branch:** `agent/governance-runtime-m1`  
**Base continuity master:** `QANUN_AI_CASE_INTELLIGENCE_HANDOFF_MASTER_2026-08-15.md`  
**Milestone 8 semantic runtime commit:** `663abeea565ffdd0bd4c5749f0afa593ac080e81`

This addendum supersedes only the current-state / next-index portions of the earlier continuity master. All immutable governance principles, frozen baselines, legal boundaries, and Milestones 1–7 decisions in the master remain binding.

## Current authoritative state

```text
DOCUMENT    → FROZEN
PARTY       → FROZEN
REQUEST     → FROZEN
DEFENSE     → FROZEN SANDBOX RUNTIME BASELINE
FACT_EVENT  → FROZEN SANDBOX RUNTIME BASELINE
EVIDENCE    → FROZEN SANDBOX RUNTIME BASELINE

Production Activation → FALSE
GitHub CI              → NOT_RUN_NO_WORKFLOW
NEXT INDEX             → STATEMENT_ADMISSION
```

## EVIDENCE source and immutable fingerprints

- Source delivery: `QANUN_AI_EVIDENCE_REBUILD_DELIVERY_V1.1.0(2).zip`
- Delivery ZIP SHA-256: `501fee41f1201d568b982de96c40b3700963eb17144b09bb6cf2577c57abfd89`
- Source package: `QANUN_AI_SY_EVIDENCE_BACKEND_COMPLETE_V1.1.0_LEGAL_REBUILT_GOVERNANCE_CANDIDATE.json`
- Package SHA-256: `e73fd6f9b619a3daa7347f64df6c08a95dca1c793753a44044a02e4d66a4e906`
- Validation report SHA-256: `dbb84a692e12df42a48306bb168fb5ed536cb005ec29e3d1ab05cdac189b5430`
- Changeset SHA-256: `8dfaf168078fcf4f9819ffc5f7181639d1e0546e81ab29dc969c8b7181b1c8e5`
- Activation patch SHA-256: `f4ae93fca98a76adf590fd5cd6261343a3b8f8a2ba74cffc4ca9b6eb2b600e2f`

## Frozen EVIDENCE runtime baseline

Authoritative Git path:
`config/evidence_runtime_baseline_v1.json`

Status:
`FROZEN_SANDBOX_BASELINE_LOCAL_VERIFIED`

Frozen D01–D30 EVIDENCE projection SHA-256:
`27bb93ccd73b10aa976dddbffc9a6bb62dae7da6dd62b36c9bee994280d8d0b6`

Upstream frozen projections:
- Phase 1: `86a0fd5861ca16d095745d5402a6086a8f5f7c885d32914340b55b3e53271524`
- DEFENSE: `6b1a616ad3f75d1c79ed326e1c5af7380ba742ede3b704ba1355515228047a4d`
- FACT_EVENT: `e01e34176ee6b96e401dd38f93d9f6bc6bcd5bb37e71a8e32d75b974a0ddb4cb`

## Static source validation

```text
Evidence families             10
Evidence types                166
Dictionary entries            166
Evidence functions            28
Challenge types               16
Authenticity statuses         17
Admissibility statuses        11
Relations                     96
Status transitions            65
Chain-of-custody event types  21
Entity schemas                8
Source validation             40/40 PASS
Stable IDs added/deleted      0 / 0
```

## Golden Case runtime result

Synthetic source case:
`CASE-SY-DAM-REALTY-2022-000731`, D01–D30.

Source DOCX SHA-256:
`83fc2b2324750246bd5dc3e3d0fd4d89de67bc8c38192d97c3f43e712508d970`

Committed fixture:
`tests/fixtures/evidence_golden_case_d01_d30.json.gz`

Compressed fixture SHA-256:
`9cf9f3c45c7709a4008214915601446945fa6f7adb951b8fc0e2d2524919ccef`

Decompressed canonical fixture SHA-256:
`78093fae4cbba9ecef46aa2d129f9cd27f4d0c5a2870c29cb161f7c6cd2b28d8`

Result:

```text
37 EVIDENCE candidates
├── 20 EVIDENCE_ITEM
└── 17 EVIDENCE_REFERENCE

44 relation candidates
├── 37 source-document relations
└── 7 EVIDENCE_SUPPORTS_FACT
```

Local committed regression equivalent: `5/5 PASS`.
Same-input rerun: PASS.  
Reversed-input-order invariance: PASS.

## Critical Milestone 8 guard: occurrence-aware FACT support

A false many-to-many risk was detected while integrating EVIDENCE with the frozen FACT_EVENT runtime: both the 12/04/2022 receipt and the 13/04/2022 bank-transfer occurrence share `FACT_PAYMENT_STATUS`. Linking only by canonical fact type could therefore cross-link each evidence item to both occurrences.

Milestone 8 resolves this with `MATCHING_QUOTE` occurrence-aware support for D02/payment evidence. Each evidence occurrence can support only its matching FACT occurrence from the same source document.

Validated:
- 12/04 receipt → only matching receipt/payment-status occurrence.
- 13/04 electronic transfer → only matching transfer/payment-status occurrence.
- cadastral extract can support the three registration/encumbrance facts in D04, but never an ownership fact.
- real-estate inspection evidence can support physical/possession facts in D14.
- `EVIDENCE_SUPPORTS_FACT` remains `RELATION_CANDIDATE_ONLY_UNVERIFIED` and never changes FACT truth/status.

## Immutable legal/runtime boundaries

- `EVIDENCE_ITEM != EVIDENCE_REFERENCE`
- `FACT != EVIDENCE`
- supporting evidence != fact truth
- authenticity != integrity
- integrity != lawful acquisition/privacy
- lawful acquisition/privacy != admissibility
- admissibility != probative value
- court admission != court reliance
- court reliance != court fact finding
- digital format != authenticity
- unlawful collection != automatic exclusion
- chain of custody is never invented without an actual source/handling record
- no stable instance IDs are issued
- no canonical persistence is permitted
- no automatic admissibility decision is permitted
- no automatic probative-value decision is permitted
- no automatic legal effect is permitted

The source EVIDENCE package itself remains immutable and source-declared `NOT_RUNTIME_ACTIVATED / BLOCKED_PENDING_RUNTIME_VALIDATION`. The runtime patch is additive and sandbox-candidate-only.

## Remaining non-Milestone-8 blockers

These remain intentionally unresolved for production / automatic legal effects:
- `GATE_LEGAL_ARTICLE_MAPPING = PENDING`
- `GATE_SYRIAN_CORPUS_REGRESSION = PENDING`
- `GATE_RUNTIME_LIVE_VALIDATION = NOT_RUN_RUNTIME_UNAVAILABLE`
- stable-instance ID service
- canonical relation persistence / idempotency
- entity resolution
- live LLM/schema binding

They do not invalidate the frozen local sandbox baseline.

## Git paths added by Milestone 8

- `src/qanun_case_runtime/evidence.py`
- `src/qanun_case_runtime/evidence_runtime.py`
- `src/qanun_case_runtime/evidence_batch.py`
- `config/evidence_runtime_activation_patch_v1.json`
- `config/evidence_runtime_baseline_v1.json`
- `tests/fixtures/evidence_golden_case_d01_d30.json.gz`
- `tests/test_evidence_runtime_v1.py`
- additive exports in `src/qanun_case_runtime/__init__.py`

## Resume instruction

Continue with `STATEMENT_ADMISSION` as the next index. Do not reopen DOCUMENT/PARTY/REQUEST/DEFENSE/FACT_EVENT/EVIDENCE frozen baselines unless a documented conflict or new legal source requires a versioned compatible-additive patch. Preserve the EVIDENCE occurrence-aware support rule when linking statements, admissions, facts, and evidence.

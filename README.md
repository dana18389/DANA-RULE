# DANA-RULE — QANUN AI Case Intelligence Runtime

Milestone 1 implements the backend governance safety layer required before live DOCUMENT / PARTY / REQUEST execution.

## Implemented

- exact SHA-256 verification before artifact registration;
- immutable artifact registry semantics;
- immutable execution snapshots;
- Governance V1.1 environment gates;
- production execution blocked while `production_activation_allowed=false`;
- canonical business persistence blocked outside approved production;
- unit tests for the controls above.

## Baseline

Source: `CASE_EXTRACTION_GOVERNANCE_V1_1_DELIVERY.zip`.
Static governance is validated, but runtime, legal approval, and live tests remain pending. This repository must not claim production readiness until those gates are closed.

## Run tests

```bash
python -m pip install -e '.[test]'
pytest -q
```

## Next milestones

1. Load and verify the real immutable baseline artifacts from the delivery package.
2. Implement operator registry and exact Prompt/Schema bindings for DOCUMENT.
3. Implement candidate-only extraction pipeline and provenance/audit events.
4. Add PARTY resolver rules and no-name-only-merge protections.
5. Add REQUEST identity/relation resolution and cross-index tests.
6. Run sandbox shadow tests against simulated Syrian case files.

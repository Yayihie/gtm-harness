# Contributing to gtm-harness

Thanks for your interest! gtm-harness exists because GTM work has no CI/CD
discipline — pipelines break silently, contracts are tribal knowledge, and
nobody can audit what automation touched. Every contribution should push
toward: **fail loudly, write nothing, audit everything.**

## Ground rules

1. **Local-first, zero-credit.** Core has zero hard deps. Provider SDKs are
   optional extras; the core never talks to a paid API by itself.
2. **Fail loudly, write nothing.** A blocked run writes zero rows. No partial
   state. Tests must assert this.
3. **The contract is the documentation.** Sinks declare field contracts;
   the dry-run plan is the reviewable change set.

## Dev setup

```bash
git clone https://github.com/Yayihie/gtm-harness.git
cd gtm-harness
python3.12 -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/ -q
```

All tests must pass before a PR. CI runs the same suite on push.

## What to work on

Check MILESTONES.md. Current priorities:

- **M4 loose ends:** `plan` output formatting edge cases
- **M5:** PyPI packaging, reference example pipelines, docs
- **Provider adapters:** enrichment waterfall providers (BYO keys, cost-ordered,
  ledger-logged — see gtmharness/adapters/enrich.py for the pattern)
- **Source adapters:** anything with a clear contract (Sheets, Airtable, DB)

## Testing a new adapter

1. Adapter must validate its config BEFORE importing the SDK (helpful error,
   not a stack trace).
2. Adapter must return `[{"key": ..., "id": ..., "status": ...}]` per row.
3. Errors are reported per-row, never crash the run.
4. Add tests in tests/test_<adapter>.py — at minimum: missing-SDK error,
   missing-config error, and a happy path with a fake.

## PR checklist

- [ ] Tests pass locally (`pytest tests/ -q`)
- [ ] New feature has tests
- [ ] No new hard dependencies in the core
- [ ] README/MILESTONES updated if behavior changed
- [ ] Commit message describes the change, not the process

MIT licensed. Keep it that way.

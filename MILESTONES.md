# gtm-harness Milestones

Living roadmap. Checked = shipped and verified. A milestone is done only when
every item under it is built, tested, and demonstrated on the live repo.

## M1 — Core harness (DONE, v0.1.0)

- [x] Pipelines as code (YAML spec, validated at load)
- [x] Contract tests (required/type/enum per sink)
- [x] Schema drift detection (rename/removed/re-typed = loud failure)
- [x] Dry-run plans (`plan` shows WRITE / BLOCK per row)
- [x] Append-only audit log (`audit.jsonl`)
- [x] CLI: check / plan / run / audit
- [x] 22 tests green

## M2 — Integration layer (DONE, v0.2.0)

- [x] Skills registry (`gtmharness skills`, `skill <name> --set k=v`, user dir at ~/.gtmharness/skills)
- [x] HubSpot sink adapter (official SDK, optional extra `gtmharness[hubspot]`)
- [x] Salesforce sink adapter (simple-salesforce, optional extra `gtmharness[salesforce]`)
- [x] GitHub Action: check + plan on every PR
- [x] Provider cost ledger (`gtmharness ledger`)
- [x] 34 tests green

## M3 — Enrichment + webhooks (DONE, v0.3.0)

- [x] Enrichment waterfall adapter (BYO keys, cost-ordered, ledger-logged)
- [x] Retry with exponential backoff on provider HTTP calls
- [x] Per-lead cache — never pay a provider twice for the same lead
- [x] `--budget` flag: hard cap on waterfall spend per run; abort + ledger summary
- [x] Transform executor: `run` executes enrichment steps between source and sink
- [x] Webhook sink adapter
- [x] Removed placeholder sinks (crm/sheet) — only real adapters validate
- [x] 49 tests green

## M4 — Trust & ops (NEXT)

- [ ] `gtmharness diff` — show exactly what a spec change would alter
- [ ] `gtmharness doctor` — validate credentials, adapters, state dir health
- [ ] Rollback: `run` snapshots sink state before write; `revert` restores
- [ ] Structured JSON output mode for CI (`--json` on every command)
- [ ] Audit log integrity: rolling hash chain (tamper-evident)
- [ ] CI badge + coverage badge in README
- [ ] `plan` output wraps/truncates long field values with explicit `…`

## M5 — Community & distribution

- [ ] PyPI publication (`pip install gtmharness`)
- [ ] 3 reference example pipelines (inbound routing, enrichment, webhook fan-out)
- [ ] Launch post framing: "they find leads; gtm-harness guarantees the pipeline
      that moves them doesn't silently break" (vs open-source Clay clones)
- [ ] CONTRIBUTING.md + good-first-issue labels
- [ ] Short demo GIF/asciinema of check -> plan -> run -> audit

## Known issues / fixes to make

1. **`plan` output truncates fields in long rows** — wrap or truncate with
   explicit `…` so output never lies. (M4)
2. **No CI badge / coverage badge in README** — add once Action is green. (M4)
3. **Audit log has no integrity check** — append-only but tamper-silent; add a
   rolling hash chain so edits are detectable. (M4)
4. **Sink adapter errors are reported per-row but don't fail the run** — decide
   policy: fail-fast on first CRM error vs write-what-succeeded + report. (M4)
5. **Skills render doesn't validate the rendered YAML** — a bad param value can
   produce an invalid pipeline; render should round-trip through load_pipeline.
   (M4)

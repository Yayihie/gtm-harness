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

## M4 — Trust & ops (DONE, v0.4.0)

- [x] `gtmharness diff` — show exactly what a spec change would alter
- [x] `gtmharness doctor` — validate credentials, adapters, state dir health
- [x] Rollback: `run` snapshots sink state before write; `revert` restores
- [x] Structured JSON output mode for CI (`--json` on every command)
- [x] Audit log integrity: rolling hash chain (tamper-evident)
- [x] CI badge + coverage badge in README
- [x] `plan` output wraps/truncates long field values with explicit `…`

## M5 — Community & distribution (IN PROGRESS)

- [ ] PyPI publication (`pip install gtmharness`) — BLOCKED: needs user's PyPI
      account/token; not published without it
- [x] 3 reference example pipelines (inbound routing, enrichment, webhook fan-out)
- [x] Launch post drafted (LAUNCH.md) — framed around the r/nocode quote,
      positioned against Clay/Apollo as complementary
- [x] CONTRIBUTING.md
- [ ] Short demo GIF/asciinema of check -> plan -> run -> audit

## Known issues / fixes to make

None open — all M4 issues fixed:
- sink error policy: default writes-what-succeeded + reports + `--fail-fast` flag
- skills render round-trips through `load_pipeline` validation before printing

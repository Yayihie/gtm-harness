# gtmharness

[![CI](https://github.com/Yayihie/gtm-harness/actions/workflows/test.yml/badge.svg)](https://github.com/Yayihie/gtm-harness/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/gtmharness.svg)](https://pypi.org/project/gtmharness/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CI/CD discipline for GTM pipelines.** GTM workflows get built in no-code tools,
handed over as "a Loom video and a Clay table nobody else understands," and break
silently six months later when a field gets renamed upstream. gtmharness applies
the engineering practices that already fixed software to GTM:

- **Pipelines as code** — declared in YAML, validated at load time
- **Contract tests** — sinks declare field contracts (required, type, picklist enum); violations block the run
- **Schema drift detection** — snapshot source schemas; a renamed/removed/re-typed field fails loudly instead of quietly breaking routing
- **Dry-run plans** — `plan` shows the exact write set (WRITE / BLOCK per row) before anything touches the CRM
- **Tamper-evident audit log** — every write is logged with a rolling SHA-256 hash chain; `audit --verify` proves the log is intact
- **Enrichment waterfall** — BYO provider keys, cost-ordered, cached (never pay for the same lead twice), budget-capped per run
- **Rollback** — every run snapshots its write set; `revert` restores

Built from real Reddit pain in r/gtmengineering, r/revops, and r/marketing:

> "I've seen too many 'GTM OS' builds handed over as a Loom video and a Clay table nobody else understands. Six months later a field gets renamed upstream and the routing quietly breaks."

> "Most attribution tools fail not because of the tool but because the underlying CRM data isn't structured to feed them."

> "If it writes under the rep's name, you can't filter its changes in reports, you can't audit what it touched."

## Install

```bash
pip install gtmharness
```

Requires Python 3.10+.

![demo](docs/demo.gif)

## Quickstart

```bash
# 1. Declare a pipeline (see examples/pipeline.yaml)
# 2. Check spec + detect schema drift
gtmharness check examples/pipeline.yaml

# 3. Dry-run: see exactly what would be written
gtmharness plan examples/pipeline.yaml

# 4. Run — writes only if the plan passes; everything audited
gtmharness run examples/pipeline.yaml

# 5. Read the audit log
gtmharness audit examples/pipeline.yaml
```

Example `plan` output:

```
PLAN  pipeline=inbound_lead_routing  rows_in=3  writes=3  errors=0
  [WRITE ] to_crm <- jane@acme.com {'email': 'jane@acme.com', 'lead_source': 'paid', ...}
  [BLOCK ] to_crm <- bad@x.com {'email': 'bad@x.com', 'lead_source': 'free'}
         ! field 'lead_source': value 'free' not in enum ['paid', 'organic', 'event', 'referral']
```

## Philosophy

- **Local-first, zero-credit.** The core never talks to a paid API. Bring your own
  provider keys via source adapters — no Clay-style credit metering.
- **Fail loudly, write nothing.** A blocked run writes zero rows. No partial state.
- **The contract is the documentation.** No Loom video required.

## Enrichment waterfall — BYO keys, cost-ordered, budget-capped

```yaml
  - name: enrich
    kind: transform
    using: enrich
    config:
      providers: [prospeo, leadmagic]   # cheapest first; falls through on miss
      provider_config: {PROSPEO_API_KEY: "…", LEADMAGIC_API_KEY: "…"}
```

- Cost-ordered: try the cheapest provider first, fall through only on a miss
- Per-lead cache: the same lead is never purchased twice (cached per state dir)
- Budget cap: `gtmharness run pipe.yaml --budget 5.00` aborts the run the moment
  cumulative spend crosses the cap, with a ledger summary
- Every provider call is logged to the ledger with its real price

## Webhook sinks

```yaml
  - name: fan_out
    kind: sink
    using: webhook
    config: {url: "https://hooks.example.com/leads"}
```

## Skills — reusable pipeline templates

```bash
gtmharness skills                              # list built-in + user skills
gtmharness skill inbound_lead_routing --set source_path=leads.json crm=crm
```

Skills are plain YAML with `{{param}}` slots — drop your own into
`~/.gtmharness/skills/` and share them as files. No marketplace, no lock-in.

## Clay import — no-code table to pipeline in one command

Two ways in. From a file (schema JSON you exported):

```bash
gtmharness import-clay clay_table.json -o clay.yaml --csv clay_export.csv
```

Or live via the [Clay MCP server](https://github.com/shanefirek/clay-mcp-public) —
gtmharness speaks MCP stdio JSON-RPC directly, pulls the schema with
`clay_get_table` and the rows with `clay_export_table` (download included):

```bash
npm install && npm run build   # in clay-mcp-public; needs CLAY_SESSION_COOKIE in env
gtmharness import-clay --table-id t_abc123xyz --view-id gv_1 --mcp-path "node dist/index.js" -o clay.yaml
gtmharness --state-dir .gtmharness check clay.yaml   # establish the schema baseline
gtmharness --state-dir .gtmharness plan  clay.yaml   # dry-run the write set
gtmharness --state-dir .gtmharness run   clay.yaml
```

- Every Clay column becomes a contract field, typed by Clay's own type
  (text/email/url → string, number → number, date → datetime, checkbox → boolean)
- Formula, AI/Claygent, HTTP API and waterfall columns are preserved under
  `computed_columns` in the source config and marked optional in the contract,
  so the YAML documents what Clay computes upstream
- Duplicate column names get `_1` suffixes; field ids map to slugs via `field_map`
- Clay CSVs export every cell as text — the `clay_csv` adapter coerces values
  to the contract types before the plan gate sees them

## Real CRM sinks (optional extras)

```bash
pip install "gtmharness[hubspot]"      # official HubSpot SDK
pip install "gtmharness[salesforce]"   # simple-salesforce
```

Point a sink at `using: hubspot` or `using: salesforce` with your credentials in
the step config. The dry-run plan and audit log still gate every write — the
adapter is only the final "do it" step.

## Provider cost ledger

```bash
gtmharness ledger
#  prospeo: 14 calls, 14 rows, $0.1400
```

Every BYO provider call is logged with its real cost to `ledger.jsonl` —
total transparency about what enrichment actually costs you.

## Status

v0.5.0 — spec validation, schema drift, dry-run plans, audit log, CSV/JSON sources,
skills registry, HubSpot + Salesforce + webhook sink adapters, enrichment waterfall
(BYO keys, cost-ordered, cached, budget-capped), provider cost ledger, GitHub Action.
Clay import (`import-clay`): Clay table schema -> validated pipeline YAML, with
computed-column preservation and CSV type coercion.

Roadmap: see MILESTONES.md (M4: trust & ops — diff, doctor, rollback, tamper-evident audit log).

MIT licensed.

# gtmharness

**CI/CD discipline for GTM pipelines.** GTM workflows get built in no-code tools,
handed over as "a Loom video and a Clay table nobody else understands," and break
silently six months later when a field gets renamed upstream. gtmharness applies
the engineering practices that already fixed software to GTM:

- **Pipelines as code** — declared in YAML, validated at load time
- **Contract tests** — sinks declare field contracts (required, type, picklist enum); violations block the run
- **Schema drift detection** — snapshot source schemas; a renamed/removed/re-typed field fails loudly instead of quietly breaking routing
- **Dry-run plans** — `plan` shows the exact write set (WRITE / BLOCK per row) before anything touches the CRM
- **Audit log** — every write is logged with actor, timestamp, sink, and exact fields (append-only JSONL)

Built from real Reddit pain in r/gtmengineering, r/revops, and r/marketing:

> "I've seen too many 'GTM OS' builds handed over as a Loom video and a Clay table nobody else understands. Six months later a field gets renamed upstream and the routing quietly breaks."

> "Most attribution tools fail not because of the tool but because the underlying CRM data isn't structured to feed them."

> "If it writes under the rep's name, you can't filter its changes in reports, you can't audit what it touched."

## Install

```bash
pip install -e .
```

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

## Status

v0.1.0 — core harness: spec validation, schema drift, dry-run plans, audit log, CSV/JSON sources.

Roadmap: CRM adapters (Salesforce/HubSpot), webhook sinks, GitHub Action for PR-time `check` + `plan`, enrichment adapter registry.

MIT licensed.

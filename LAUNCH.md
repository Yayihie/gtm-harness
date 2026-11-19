# Launch post — gtm-harness v0.4.0

**Title:** I built CI/CD discipline for GTM pipelines (open source, MIT)

**Body:**

Every GTM automation I've ever seen dies the same way. It works on day one.
Six months later a field gets renamed upstream and the routing quietly breaks —
and nobody notices until a rep asks why their leads went to the wrong queue.

r/nocode said it best: *"The actual automation part is the easy 20 minutes.
Then someone exports a list from a trade show, or an SDR pastes 400 rows from
Apollo with three different name formats and half the company fields blank,
and suddenly the 'automation' is a maze of regex, dedup logic, lookup tables
and five extra steps just to get something a CRM will accept."*

Software solved this with CI/CD. GTM never got the same treatment.

**gtmharness** applies the practices that fixed software to GTM pipelines:

- **Pipelines as code** — declared in YAML, validated at load time
- **Contract tests** — sinks declare field contracts (required, type, picklist
  enum). A row that violates the contract never reaches the CRM.
- **Schema drift detection** — snapshot source schemas; a renamed field fails
  loudly instead of quietly breaking routing
- **Dry-run plans** — `gtmharness plan` shows the exact write set, row by row,
  before anything touches the CRM
- **Tamper-evident audit log** — every write is logged with a rolling hash
  chain, so "who touched what" is provably intact
- **Enrichment waterfall** — BYO provider keys, cost-ordered, cached (never pay
  for the same lead twice), budget-capped per run
- **Rollback** — every run snapshots its write set; revert restores

```bash
pip install gtmharness
gtmharness check examples/pipeline.yaml   # CI gate: drift detection
gtmharness plan examples/pipeline.yaml    # dry-run: exact write set
gtmharness run examples/pipeline.yaml     # execute + audit
gtmharness audit examples/pipeline.yaml --verify
```

**Positioning:** Apollo/Clay/ZoomInfo find and enrich leads. gtm-harness
guarantees the pipeline that moves them doesn't silently break. They're
complementary — run enrichment, then harness it.

MIT licensed, zero hard deps, local-first. Bring your own provider keys —
the cost ledger shows exactly what enrichment costs you, no credit metering.

Repo: https://github.com/Yayihie/gtm-harness

---

**Subreddit targets:** r/gtmengineering, r/revops, r/growthhacking, r/nocode
**Framing:** lead with the r/nocode quote — it's the exact pain in their words.

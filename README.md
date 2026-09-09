# Northlane Supply Co. — Profitability & Retention Analytics

A US DTC apparel brand analysed end to end: synthetic data generation, a dbt
transformation layer on Postgres, automated quality gates, and a
reconciliation harness that proves the pipeline recovers the truth from a
corrupted source export.

This module produces the **raw layer**: three years of deliberately messy
e-commerce data for a fictional US outdoor-apparel brand, sized and calibrated
so that a specific set of profitability problems is genuinely present in the
data and genuinely discoverable through analysis.

> **The data is synthetic.** Northlane Supply Co. does not exist. The generator
> is included in full so the assumptions behind every number are inspectable.
> Building it required modelling the actual economics of a DTC apparel
> business — dimensional-weight shipping, returns disposition, cost drift,
> platform over-attribution — which is why it is part of the portfolio rather
> than hidden behind a CSV.

---

## Quick start

```bash
make setup       # install dependencies
make all         # generate -> validate -> load -> build -> reconcile
```

Each stage runs on its own:

| Command | What it does | Result |
|---|---|---|
| `make generate` | Synthetic raw layer, deliberately messy | 3s, ~59 MB |
| `make validate` | Are the planted findings still present? | **20/20 checks** |
| `make load` | Raw CSVs into Postgres schema `raw` | 2s |
| `make build` | staging → intermediate → marts, with tests | **100/100 models and tests** |
| `make reconcile` | Does the pipeline recover the truth? | **15/15 metrics** |
| `make golden` | Values Power BI must reproduce | 45 measures |
| `make dashboard` | Rebuild the static demo page | `docs/index.html` |

Requires a Postgres connection in `DATABASE_URL`. Free tiers (Neon, Supabase)
are sufficient. Fully deterministic — the same seed produces byte-identical
output.

---

## The result that matters

The generator knows the ground truth. The pipeline only ever sees the corrupted
export. `make reconcile` runs both and compares:

```
  [PASS] FY2025 gross revenue         $10,017,805.50  $10,017,805.50  +0.000%
  [PASS] FY2025 net revenue (returns) $ 6,971,458.67  $ 6,971,458.67  +0.000%
  [PASS] FY2025 refunds               $ 1,962,393.16  $ 1,962,393.16  +0.000%
  [PASS] FY2025 CM2                   $ 2,358,596.72  $ 2,358,763.83  +0.007%
  [PASS] F1 defect-SKU CM2            $  -153,630.69  $  -153,630.69  -0.000%

15/15 metrics reconcile within 0.5%
```

The residual 0.007% on CM2 is not noise: it is the five imputed unit costs,
traceable to the row. A pipeline that loads without errors but quietly drops 3%
of revenue looks identical to a correct one until someone checks. This is that
check.

It also confirms the analysis rediscovers the two problem SKUs from their return
behaviour alone, without ever touching the `is_defect_sku` label:

```
Finding 1 -- two worst SKUs by CM2, discovered from the dirty data:
        sku  units  return_rate      cm1        cm2
NL-OUT-0023   4038        0.461 14328.28 -100810.87
NL-OUT-0017   2434        0.459 15043.40  -52819.82
  planted SKUs:    ['NL-OUT-0017', 'NL-OUT-0023']
  discovered SKUs: ['NL-OUT-0017', 'NL-OUT-0023']
  match: YES
```

---

## What it produces

| File | Rows | Grain |
|---|---|---|
| `raw_orders.csv` | 98,693 | one per order |
| `raw_order_lines.csv` | 173,930 | one per order × SKU × line |
| `raw_returns.csv` | 38,729 | one per return line |
| `raw_ad_spend.csv` | 14,210 | date × channel × campaign |
| `raw_products.csv` | 540 | one per SKU **cost version** (SCD2) |
| `raw_customers.csv` | 72,000 | one per customer |
| `raw_geography.csv` | 51 | one per state + DC |
| `injected_defects.csv` | 8 | manifest of deliberate corruptions |

FY2025: **$10.0M gross revenue**, 48,531 orders, $184 AOV, 20.3% unit return rate.

---

## Modelled economics

Not decoration — each of these changes a number a client would care about.

- **SCD Type 2 unit costs.** Costs step up twice over the history. Orders are
  priced against the cost version valid on the order date, so historical margin
  is not silently rewritten by today's supplier pricing.
- **Dimensional-weight shipping.** Carriers bill `max(actual, dimensional)`
  weight. A boxed parka to Zone 8 costs multiples of a t-shirt to Zone 2. This
  is what makes geography an economic variable rather than a map colour.
- **Returns as a process, not a rate.** Log-normal delay (median ~12 days),
  disposition split across restock / liquidate / destroy, partial COGS recovery,
  return shipping and restock labour, and reason codes that concentrate on
  sizing for defective SKUs.
- **Discount-driven return uplift.** Deeper discounts attract bracket-buyers.
  Return probability scales with discount depth.
- **Platform over-attribution, per channel.** Search reports ~1.15× true
  revenue; view-through-heavy social reports up to 2.0×. The gap between
  `platform_reported_revenue` and real order revenue is itself analysable.
- **Channel-specific retention.** Lifetime order count is drawn from a
  channel-specific geometric distribution, producing realistic cohort curves
  rather than a hard-coded LTV table.
- **Sales tax carried but excluded from revenue.** Present in the raw data so
  the transformation layer has to handle it correctly.

---

## Deliberate data quality defects

Clean synthetic data is the clearest possible signal of a portfolio project.
The raw layer ships broken, with a manifest:

| Defect | Table | Rows |
|---|---|---|
| Inconsistent product name casing / abbreviation | `raw_order_lines` | 38,300 |
| Three date formats in one column | orders / lines / returns | 48,873 |
| Mixed state format (`CA`, `California`, `ca.`) | `raw_orders` | 8,816 |
| Duplicate orders (checkout retry) | orders / lines | 393 |
| Null `unit_cost` on newly onboarded SKUs | `raw_products` | 5 |
| Orphaned returns (no matching order line) | `raw_returns` | 295 |
| Decimal-point typo in price feed | `raw_order_lines` | 93 |
| Untrimmed / uppercased emails | `raw_customers` | 2,165 |

Every one has a matching test and a documented resolution with its dollar
impact in [`docs/data_quality_report.md`](docs/data_quality_report.md). The
orphaned returns are **quarantined rather than deleted** — deleting them would
have improved every margin figure, which is exactly why it would have been
wrong. The disclosed exposure is $25,222, or 0.52% of CM2.

---

## Transformation layer

Four layers, strictly separated. The discipline is the point: a reviewer can see
where each kind of logic lives.

| Layer | Materialised | Rule |
|---|---|---|
| `raw` | tables, all TEXT | Lossless copy. A source that emits three date formats must be *storable*. |
| `staging` | views | Casts, renames, string cleaning. **No joins, no business logic.** |
| `intermediate` | views | Joins and cleaning that needs context: SCD2 range join, deduplication, imputation, typo correction. |
| `marts` | tables | Star schema. The only layer Power BI touches. |

Deciding *where* a fix belongs is most of the work. The decimal-point typo
correction cannot live in staging because detecting it requires `list_price`
from the product dimension — so it lives in intermediate, and that constraint is
what makes the layer boundary real rather than decorative.

### Three models worth reading

**`int_order_lines_enriched`** — the consequential one. Joins unit cost on the
SCD2 version valid on the *order date*:

```sql
inner join products p
    on p.sku = l.sku
   and o.order_date between p.valid_from and p.valid_to
```

Joining the current version instead would apply 2025 supplier pricing to 2023
orders and quietly rewrite two years of margin history. This is also why
`valid_to` is coerced to `9999-12-31` in staging: with NULL, `BETWEEN` silently
drops every current-version row.

**`fct_order_lines`** — the CM1/CM2 waterfall at line grain. Returns are joined
*pre-aggregated*, because a line with three return records must still produce one
fact row. Fanning out a fact table on returns is the most common margin bug in
e-commerce models, and it is invisible in aggregate.

**`fct_channel_economics_monthly`** — the only model that computes CM3, because
channel-month is the only grain at which ad spend is actually measured. There is
no state-level CM3 in this project. Producing one would be an allocation
presented as a measurement.

---

## Quality gates

`dbt build` runs **100 models and tests**, all passing. Beyond the standard
`unique` / `not_null` / `relationships` coverage:

| Test | What it catches |
|---|---|
| `assert_lines_reconcile_to_order_header` | Join fan-out *and* dropped lines, in one test |
| `assert_scd2_windows_do_not_overlap` | Duplicate cost versions silently doubling revenue |
| `assert_net_revenue_identity` | A price correction applied to the wrong column, or twice |
| `assert_returns_are_plausible` | Returns before the sale, or beyond the 60-day window |
| `assert_orphan_returns_within_tolerance` | Quarantine growing past 2% of refunds (warn) |

Orchestration is GitHub Actions on a daily cron, running against a throwaway
Postgres service container so a pull request can never touch the warehouse the
dashboard reads from. A single daily batch does not justify Airflow.

---

## Layout

```
src/
├── generate_data.py        # CLI orchestrator
├── validate_findings.py    # self-test: are the findings still there?
├── load_to_postgres.py     # COPY into schema `raw`, with row reconciliation
├── reconcile_marts.py      # ground truth vs pipeline output
└── datagen/
    ├── config.py           # every constant in the project
    ├── catalog.py          # products (SCD2) + geography + shipping curves
    ├── customers.py        # cohorts, channels, order calendar
    ├── orders.py           # baskets, discounts, landed-cost allocation
    ├── returns.py          # timing, disposition, reasons
    ├── marketing.py        # spend, campaigns, attribution inflation
    └── dirty.py            # deliberate corruption layer

dbt/
├── macros/                 # mixed-date parsing, state normalisation, surrogate keys
├── models/{staging,intermediate,marts}/
└── tests/                  # six singular integrity tests

docs/
├── business_rules.md       # decisions that change the numbers
└── data_quality_report.md  # every defect, its fix, its dollar impact
```

No `dbt_utils` dependency: the date spine uses `generate_series` and surrogate
keys use `md5`. One fewer thing to break.

---

## Documentation

- [`FINDINGS.md`](FINDINGS.md) — the four findings with measured figures
- [`docs/business_rules.md`](docs/business_rules.md) — CM1/CM2/CM3 definitions, attribution rules, allocation bases
- [`docs/data_quality_report.md`](docs/data_quality_report.md) — every defect, its resolution, its margin impact

---

## Live demo

**[View the dashboard →](https://YOUR-USERNAME.github.io/northlane-analytics/)**

A single self-contained page, hand-built SVG, no charting library, no build step.
Works on a phone and offline. Deploying it is one setting: GitHub → Settings →
Pages → Source: `main` branch, `/docs` folder. That is why the page lives in
`docs/`.

```bash
REPO_URL=https://github.com/you/northlane-analytics make dashboard
make serve      # preview at localhost:8000
```

Three things worth knowing about how it is built:

**No figure is typed into the HTML.** `src/export_dashboard_data.py` queries the
marts into a JSON payload; `src/build_dashboard.py` injects it into
`docs/index.template.html`. Even the prose is derived — an early draft asserted
that "several months fall below zero", and the data says exactly one does, so the
sentence now counts them. A refresh is `make dashboard`, not an editing session.

**The data is embedded, not fetched.** No CORS, no loading state, no failure mode
to design around. The page opens from `file://` as readily as from Pages.

**A broken chart cannot blank the page.** Each renderer runs inside its own
try/catch, `.reveal` only hides content once JavaScript is confirmed running, and
a timeout reveals anything still hidden after 2.5s. Verified against five
scenarios: intact payload, two kinds of corrupted payload, an environment with no
`matchMedia` or `IntersectionObserver`, and JavaScript disabled entirely. The
page renders in all five.

---

## Report layer

The `.pbix` is built by hand in Power BI Desktop — there is no reliable way to
author one programmatically. Everything that makes building it mechanical is
specified:

| Document | Contents |
|---|---|
| [`powerbi/data_model.md`](powerbi/data_model.md) | Relationships with cardinality, which columns to hide and why, the inactive returns-to-calendar relationship, satellite-table handling, page-by-page visual spec |
| [`powerbi/dax_measures.md`](powerbi/dax_measures.md) | 45 measures with the business logic behind each |
| [`powerbi/golden_values.md`](powerbi/golden_values.md) | Expected value for every measure, regenerated by `make golden` |

Two modelling decisions worth reading:

**`fct_returns[return_date_key] → dim_date` is inactive.** Returns reach the
calendar through `fct_order_lines`, giving the *original order date* — correct
for margin. A cash-basis view activates the second path explicitly with
`USERELATIONSHIP`. Two active paths would make every refund figure ambiguous.

**`[CM3]` returns blank when filtered by state, category or SKU.** Ad spend is
not reported at those grains, so `[CM2] - [Ad Spend]` sliced by category would
silently subtract *all* spend from *each* row. The measure guards against it and
returns nothing rather than something plausible and wrong.

Power BI has no unit tests. `golden_values.md` is the substitute — check every
measure against it before building a single visual.

---

## Findings

The client-facing deliverable is a one-page memo:
[`docs/findings_memo.md`](docs/findings_memo.md).

**$201,033/yr of recoverable contribution against FY2025 CM3 of $721,075 — 28%
of contribution margin, with no additional acquisition spend.**

The headline is margin compression: revenue tripled over three years while CM3
margin fell from 14.8% to 10.2%.

---

## Next stage

Build the `.pbix` in Power BI Desktop from `powerbi/data_model.md`, and record a
90-second walkthrough. Power BI Service requires an organisational email domain
to publish — see `powerbi/data_model.md` §1. The demo page above covers the gap
in the meantime and is the better link to send from a phone regardless.

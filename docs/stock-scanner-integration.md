# User scanner: recovered selection criteria

The supplied stock_scanner.py is the reference for stock-level screening.
Its SHA-256 is recorded in configs/stock_screen_v1.json. The original file was
inspected, not executed or changed. That JSON is a versioned specification;
the current event-study runner does not load or apply it yet.

## Adopted stock rules

All five must pass, with strict inequalities:

1. Latest close > average of the latest 50 closes, including that close.
2. Latest close > opening price of the first session in the calendar quarter.
3. Latest available quarterly revenue growth versus the same quarter a year
   earlier > 0%.
4. Last reported quarter EPS surprise > 0%, calculated as
   100 * (actual EPS - consensus EPS) / abs(consensus EPS). The original requires
   a nonzero estimate; zero estimates do not qualify through that formula.
5. PEG < 1.0. The original does not impose a positive lower bound.

The original requires at least 55 price rows and requests one year of daily
history with auto_adjust=False. It uses the last returned row as current price;
the research implementation must explicitly identify completed sessions.

## Industry policy and candidate pool

Per the owner's instruction, omit the original four industry buckets, the
AI/quantum keyword check, and the supplemental ticker lists selected for those
themes. Use the project's separate dynamic industry-ranking specification.
This document does not assert that the industry-ranking engine is implemented.

The original scanner starts with today's S&P 500 and Nasdaq-100 constituents,
deduplicated. That supplies a candidate-pool proposal, not historical membership
or a verified 100-stock universe. The original has no rule that produces exactly
100 stocks; all-five filtering may yield very few matches. Ranking/capping and
historical membership still need a declared definition before implementation.

## Required adaptations before research use

- Availability: Yahoo info and current quarterly tables in the original do not
  establish what was known at historical decisions. Require publication/as-of
  evidence for revenue, reported EPS, consensus, PEG and industry/membership
  records, or label the run exploratory. Retrieval time is not historical
  availability time.
- Quarter open: the original substitutes the latest daily open if the quarter
  has no data. Record an unavailable criterion instead of changing its meaning.
- Revenue: explicitly match fiscal quarters and publication times; positional
  columns zero and four and the info revenueGrowth fallback require validation.
- Earnings: select the latest published event explicitly rather than assuming
  provider row order. Match EPS basis and fiscal period. Capture the original
  pre-release consensus snapshot and its availability timestamp.
- PEG: retain the original threshold for comparability, but flag that negative
  PEG values pass it. The original also falls back from vendor PEG to trailing
  P/E divided by earnings growth in percentage points. These are potentially
  different definitions. A positive-PEG requirement or a different estimate
  horizon must be a separately versioned research variant.
- Prices: validate a consistent corporate-action basis across closes, SMA and
  quarter open; use the exchange calendar and reject missing/stale bars.
- Audit: preserve every candidate with per-rule pass/fail/unavailable reasons.
  The original silently drops several acquisition failures; the engine must
  retain exclusions and failed-source information.

## Relationship to earnings research

Keep the broad eligible universe for the general earnings beat/miss comparison.
This five-rule screen is a separate strategy variant. Requiring a beat on the
same event being studied would exclude misses and could use future information
in a pre-announcement decision. For a pre-earnings screen, only an earlier,
already published quarter's beat can be considered.

Record the full candidate pool, screen variant and all attempted hypotheses.
Do not scan today's winners and retrospectively call them the historical universe.

## Data-provider evaluation

The scanner now gives concrete data requirements: daily prices/corporate actions,
dated quarterly revenue, original EPS consensus and actuals, and a documented PEG
definition with availability history. Paid access is useful only if the required
fields and historical availability evidence are actually available on the chosen
plan. Provider selection remains open; no subscription or API call was made here.

# Quant Research Engine — Agent Instructions

## Mission and scope

Build a reproducible Python research engine for systematic equity strategy research across a defined universe of approximately 100 U.S.-listed stocks. The engine should support dynamic industry rotation, per-ticker strategy research and backtesting, event studies around earnings, and pairs/statistical-arbitrage research. Its purpose is research and paper trading only.

The system must make it possible to answer, reproducibly: what information was available at each decision time, what trade would have been formed, when it could have been executed, what costs it incurred, and how the result held up on unseen data.

Do not present research results as a promise of future returns or as investment advice. Do not add live order placement, broker credentials, or real-money execution. Future market-hours automation means scheduled data refresh, signal calculation, monitoring, and paper-trade recording only unless the owner explicitly changes the project’s safety scope.

## Research priorities

Implement and compare the following families, keeping each strategy independently configurable and reportable:

1. **Dynamic industry rotation:** rank industries from information available at each rebalance; define industry membership and classification source/version; select or weight eligible stocks within the strongest groups. Include turnover controls and an equal-weight or broad-market baseline.
2. **Per-ticker backtesting:** evaluate each eligible stock independently as well as in portfolio combinations. Preserve ticker-level results and avoid silently dropping failed or delisted names.
3. **Earnings event research:** study pre-earnings run-ups, event-window reversals, and post-earnings announcement drift (PEAD). Make event dates, announcement timestamps, fiscal periods, surprise definitions, and tradability assumptions explicit. Separate after-close, before-open, and intraday releases where the data supports it.
4. **Pairs trading and statistical arbitrage:** form pairs using training data only; test spread stationarity/cointegration and stability; specify entry, exit, hedge ratio, exposure, borrow/short assumptions, and maximum holding period. Re-estimate only at declared training/rebalance times.
5. **Benchmarks:** include transparent momentum and trend-following baselines, plus suitable passive and cash/zero-return references. Use identical dates, universe eligibility, and cost conventions when comparing strategies.

Research can evolve as evidence warrants, but do not silently change a strategy definition after examining its test-period results. Record hypotheses, parameters, data sources, and experiment identifiers.

## Data and point-in-time integrity

- Yahoo Finance (`yfinance`) is the initial market-data source for historical price and volume data. Isolate provider-specific code behind a data interface so sources can be replaced. Respect provider terms, rate limits, outages, and data limitations; cache raw downloads with retrieval timestamps and provenance.
- Treat Yahoo Finance data as convenient research input, not guaranteed institutional-grade or survivorship-bias-free data. Document adjusted versus unadjusted prices, corporate actions, missing bars, symbol changes, delistings, and any known limitations. Never silently forward-fill prices across suspensions or missing sessions.
- Keep raw, normalized, and derived data distinct. Store schema, timezone, currency, frequency, source, retrieval time, and transformation/version metadata. Make downloads idempotent and validate column/index types, duplicates, gaps, and impossible values.
- Use a versioned universe of about 100 stocks with effective dates and inclusion rationale. Do not use current index membership as a proxy for historical membership. When historical membership or delisted-stock data is unavailable, disclose the resulting survivorship limitation and avoid claiming survivorship-free results.
- Every feature used for a decision must be available by that decision timestamp. Enforce publication-time/effective-time semantics for earnings, fundamentals, industry classifications, and universe membership. A fiscal period end is not an availability timestamp. If point-in-time timestamps cannot be verified, mark the field unavailable for the affected test or label the analysis exploratory; do not imply strict point-in-time validity.
- Earnings event studies require announcement timestamps (or a clearly documented coarse-date assumption), a trading calendar, and an explicit mapping from announcement to the first executable bar. Avoid using revised consensus, revised fundamentals, or restated data as if known historically.
- Align all series to an explicit exchange calendar and timezone. Handle daylight saving time, holidays, early closes, and after-hours announcements deliberately. Never infer a tradable price from a daily close that occurred before the signal became known.
- Add data-quality checks and fail loudly on ambiguous alignment, unexpected duplicate records, future-dated observations, or missing critical fields. Preserve a machine-readable record of exclusions and reasons.

## Backtesting standards

- Make signal time, order/decision time, fill time, and return interval explicit. A signal computed from a bar’s close may not earn that same close-to-close return unless a feasible execution model supports it.
- Use chronological train/validation/test splits. Use rolling or expanding walk-forward evaluation for model/parameter selection and preserve a final untouched out-of-sample period where data permits. No random shuffling of time series.
- Fit scalers, thresholds, pair selection, feature selection, industry ranks, and any learned parameters on training data only. Freeze them for the following evaluation interval, then refit only at the declared walk-forward boundary.
- Prevent look-ahead, target leakage, survivorship bias, and overlapping-event contamination. Add explicit leakage checks where practical and document any irreducible data limitation.
- Model commissions/fees, bid-ask spread, slippage, turnover, and (for shorts) borrow availability/cost and financing where applicable. Use conservative, configurable assumptions, report them, and include sensitivity analysis across plausible cost levels. Gross results alone are not an acceptance result.
- Account for corporate actions consistently. Do not mix adjusted prices for returns with unadjusted prices for execution without a documented adjustment model.
- Report strategy and benchmark returns on comparable periods and capital/exposure conventions. Include annualized return and volatility where appropriate, Sharpe ratio with stated risk-free convention, maximum drawdown, turnover, exposure, trade count, win rate, average gain/loss, and per-period/per-ticker breakdowns. Include uncertainty estimates suitable for dependent financial returns (for example, block-based confidence intervals when justified); do not treat overlapping observations as independent.
- Clearly separate in-sample, validation, walk-forward, and final out-of-sample metrics. Do not select or advertise a strategy solely on the best historical Sharpe ratio.
- **Do not run or add Monte Carlo simulations.** This is an explicit project constraint. Use analytical diagnostics, chronological resampling methods only if explicitly permitted in the future, and genuine out-of-sample evidence; do not label bootstrapping as Monte Carlo to evade this rule.

## Statistical rigor and multiple testing

- Treat every tried ticker, pair, feature set, parameter combination, event window, and strategy variant as part of the research search. Track experiments and the number/family of hypotheses examined.
- Report raw p-values and apply a stated multiple-testing correction (at minimum Benjamini–Hochberg false discovery rate within a clearly defined family; consider stronger family-wise or dependence-aware methods when warranted). State assumptions and the correction family. Never report an unadjusted significant result as confirmatory after a broad search.
- Prefer effect sizes, confidence intervals, stability across time and names, and economic relevance to threshold-only significance. Avoid p-hacking, repeated test-set inspection, and undisclosed parameter tuning.
- Use appropriate time-series methods for serial correlation, heteroskedasticity, overlapping event windows, and cross-sectional dependence. Explain limitations where sample sizes are small.
- For pairs, distinguish formation and trading periods; test parameter and relationship stability, structural breaks, and sensitivity to formation window. Do not claim arbitrage from historical correlation alone.

## Paper-trading and future automation

- Keep the current system offline/batch-first unless the repository already establishes a safe scheduler. Design future market-hours operation as read-only data retrieval plus signal generation, alerts/logging, and simulated fills. Include idempotency, stale-data checks, retries/backoff, rate limiting, observability, and a kill switch before any scheduled service is introduced.
- Paper fills must use prices and timing that could plausibly have been observed, include the configured costs, and record signal/data versions. Clearly label simulated orders and P&L.
- Do not add production brokerage integration or real-money order execution. Do not store secrets in source control; use environment configuration for provider credentials if a future provider requires them.

## Recommended repository structure

Adapt to an existing repository if one is present. Do not move or rename working files just to match this suggestion. For a new repository, prefer a conventional `src` layout:

```text
quant-research-engine/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .gitignore
├── configs/
│   ├── universe.csv
│   └── research.yaml
├── data/                    # generated/cache data; normally git-ignored
├── notebooks/               # exploratory only; promote validated logic to src
├── reports/                 # generated output; normally git-ignored
├── src/quant_research/
│   ├── data/                # Yahoo Finance adapter, cache, schemas, validation
│   ├── universe/            # versioned membership and industry mapping
│   ├── features/            # point-in-time feature construction
│   ├── strategies/          # rotation, earnings, pairs, momentum, trend
│   ├── backtest/            # execution, costs, portfolio accounting
│   ├── evaluation/          # metrics, walk-forward, FDR, reports
│   └── paper/               # paper ledger and future monitoring interfaces
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

The referenced starter filenames `engine.py`, `download_prices.py`, `earnings_event_study.py`, and `universe.csv` may be retained or migrated incrementally after inspecting their contents. Do not assume they exist. Keep generated prices, credentials, large vendor datasets, and machine-specific outputs out of Git unless explicitly intended and appropriately licensed.

## Engineering conventions

- Inspect the repository, `README`, configuration, Git status, and relevant tests before editing. Preserve user changes and local conventions. Do not overwrite uncommitted work.
- Use Python type hints, focused modules, clear names, deterministic configuration, and small composable functions. Separate data acquisition, signal formation, execution simulation, accounting, and evaluation.
- Prefer explicit configuration over hidden constants. Record configuration and code revision with every result. Set random seeds only where relevant; do not add Monte Carlo.
- Make command-line jobs reproducible and safe to rerun. Keep network calls out of unit tests; tests should use small deterministic fixtures and injected data providers.
- Document setup, data acquisition, commands, assumptions, known data limitations, and result interpretation in `README.md` as the system becomes usable. Never commit API keys, personal data, or downloaded licensed data accidentally.
- Do not add dependencies without a clear need. Pin or constrain dependencies using the repository’s existing packaging conventions.

## Tests and acceptance criteria

When asked to implement or change code, add or update focused tests for the changed behavior and run the relevant existing checks. Do not claim tests passed unless they were actually run. If checks cannot run, report the exact blocker and the checks left unverified.

At minimum, the project’s acceptance suite should cover:

1. **Data:** schema and timezone normalization; duplicate/gap detection; adjusted-price and corporate-action handling; cache idempotency; explicit missing-data behavior; and no future timestamps in a decision dataset.
2. **Point-in-time safety:** a feature/event published after a decision cannot influence it; after-close earnings are not tradable at that day’s earlier close; universe and industry membership use effective dates.
3. **Backtest accounting:** known small fixture returns reconcile by hand; signals cannot earn pre-signal returns; costs reduce P&L as expected; turnover and exposure are accounted for; no-trade and missing-bar cases behave deliberately.
4. **Walk-forward:** chronological boundaries are respected; fit/selection data never includes evaluation rows; final holdout is not used for tuning; folds and output metadata are reproducible.
5. **Strategies:** earnings windows map announcements to feasible sessions; pair selection uses formation data only; rotation ranks use as-of information; benchmark and strategy intervals match.
6. **Statistics:** metrics handle edge cases; FDR adjustment is tested against known values; hypothesis-family counts and raw/adjusted results are retained; uncertainty methods state their assumptions.
7. **Paper mode:** outputs are visibly simulated, repeat runs are idempotent, stale data is rejected, and no live order route exists.

A research result is accepted only when its data provenance and assumptions are recorded; point-in-time and execution timing are defensible; costs are included; walk-forward/out-of-sample performance is reported separately from training; multiple testing is addressed; benchmarks and diagnostics are shown; and known limitations are stated. A passing software test suite alone does not validate a trading hypothesis.

## Autonomous working instructions

- Work autonomously on repository inspection, implementation, debugging, documentation, and relevant verification. Do not ask for approval for routine reversible edits or every command.
- Infer ordinary implementation details from the codebase, but do not invent historical data, claim unavailable point-in-time coverage, or conceal uncertainty. Record assumptions and choose conservative defaults.
- If scope is broad, make useful incremental progress: establish reproducible data contracts and validation first, then implement the smallest end-to-end research path, then expand strategy coverage.
- Before changing an established strategy or data definition, preserve comparability by versioning the configuration and explaining the change.
- Ask the owner only when a decision materially changes the research objective, requires unavailable credentials/data, or conflicts with these constraints. Never ask for confirmation to continue routine authorized work.
- Do not publish, push, deploy, or connect external services unless explicitly requested. Keep changes local and reviewable by default.
- At completion, summarize files changed, behavior and assumptions, checks actually run and their outcomes, and remaining data or validation limitations.

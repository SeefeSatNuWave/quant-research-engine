# Three-day goals: initial implementation and findings

## Data audit and frozen definitions

`configs/timing_audit_v1.csv` records three suspicious historical labels. Microsoft July 2023 conflicts with its official after-close schedule; NextEra April 2025 conflicts with its published morning release. Exxon April 2024 has morning-call evidence, but first-public-release time still requires verification.

Earlier pilot and AI-comparison results are preserved as vendor-timing version 1. They are provisional and should not be promoted as verified findings. A full release-time audit and a separately versioned corrected rerun remain required. No source timestamp has been invented and raw responses remain unchanged.

`configs/research_baseline_v1.json` was written before downloading February-October 2026 prices. This fixes eight AI-exposure names, a five-session post-event short, conservative next-date-close entry, four pair candidates, thresholds and cost scenarios. The same evaluation period is now inspected and cannot be called untouched in later tuning. No pre-earnings execution claim is made without historical scheduled-date availability.

## Executable research baseline

The accounting module models gross dollar exposure at most one, next-interval returns after a fill, daily target rebalancing with drift-aware turnover, total-return price units, transaction costs and 5% annual short borrow using calendar days. Cash and financing are zero. Trade sizing assigns each active earnings name one eighth of equity; unused capital remains cash. Results are conditional simulations: historical locates, exact closing fills and corporate-action-adjusted execution units have not been independently validated.

On the frozen February-October 2026 evaluation, the earnings short lost approximately 2.54%, 2.82% and 3.38% of strategy equity at 5, 10 and 20 basis points per side, respectively. Mean gross exposure was about 7.3%. The full-investment SPY reference has different exposure and should not be treated as a like-for-like alpha comparison. The no-trade cash reference returned zero. This supports a no-go decision for deploying this exact earnings rule; it is not a claim that all earnings approaches fail.

## Statistical arbitrage first milestone

Pairs tested in the training period only: NVDA/AMD, MSFT/ORCL, GOOGL/AMZN, AAPL/MSFT. Each has one declared log-price regression orientation. All four raw Engle-Granger p-values and BH-adjusted values are retained in `pair_formation.csv`; the family count is four. Level ADF diagnostics, positive hedge beta and half-sample beta stability are additional filters. Test assumptions and finite-sample limitations remain important; a low p-value alone would not prove a tradable relationship.

None passed the frozen selection rules. Consequently, no pairs positions were formed for the evaluation. The implemented signal path uses formation-only mean, standard deviation and hedge beta; yesterday's signal fills at today's close, with entry/exit thresholds, a divergence stop, a 20-session maximum hold and final liquidation. Future expansion should be a new registered candidate family with a chronological validation design, not repeated tuning of this evaluated sample.

## Readiness decision and remaining work

Research-only, no-go for scheduled paper execution of these strategies today. Before unattended paper operation:

- Complete timestamp verification or explicit exclusions and a versioned historical rerun.
- Add provider snapshot freshness checks, retry/backoff with quota classification, concurrent-safe cache/ledger handling and kill switch.
- Implement an idempotent paper ledger and simulated order lifecycle with stale-price rejection and exact signal/data versions.
- Add trade-level reconciliation, per-ticker attribution, walk-forward folds, and a prespecified dependent-return inference plan with multiple-testing correction before confirmatory claims.
- Validate short availability, adjusted-unit execution assumptions and spread/slippage/borrow sensitivity. The current one-shot formation/evaluation split is a baseline, not full walk-forward validation.

All code and reports remain local. No live routes, purchases, Monte Carlo or remote publication were introduced.

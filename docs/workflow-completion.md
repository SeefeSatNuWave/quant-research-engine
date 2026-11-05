# Research workflow completion record

## Deliverables and acceptance

1. **Audited timing:** `configs/timing_audit_v1.csv` and `reports/workflow_v2/audited_earnings.csv` preserve original vendor timing, source evidence, corrections and exclusions. One of 192 historical records has supported release-session evidence; 191 are explicitly excluded from the verified path. Most exclusions mean not independently verified, not proven incorrect. The Microsoft schedule conflict remains excluded because a schedule alone does not verify actual publication. NextEra's source-supported morning session is corrected with a documented boundary proxy. Exact announcement timestamps are not invented. Earlier exploratory reports remain unmodified.
2. **Accounting:** `account_v2` solves transaction charges against post-cost target weights, measures drift-aware turnover, charges configured fee/spread/slippage and calendar-day borrow, and prevents signals from earning returns before fills. Separate gross/net return, cash and passive-SPY references, matched net-exposure SPY diagnostics, exposure and drawdown are retained. Independent fixture tests reconcile cash and costs. Adjusted total-return units and hypothetical daily closing fills remain explicit research assumptions.
3. **Walk-forward pairs:** four fixed pairs across four expanding chronological folds, with training strictly before evaluation. Formation parameters are frozen in each fold. Raw/adjusted cointegration p-values, level ADF diagnostics, half-sample hedge stability, every failed candidate and family counts are retained. None passed; no pair trade was created. Each fold resets flat and liquidates at its last close. No outcomes are earned across the January 2026 gap. All periods were already examined in prior work, so this is retrospective validation, not a fresh untouched holdout.
4. **Reproducibility/reporting:** `configs/experiment_registry_v1.json` records all research families, including prior exploratory work. The v2 manifest records inputs, source hashes, package versions, Git revision, configuration and calendar. Offline replay reproduces result files. Earnings exclusions, position counts, cost sensitivities and all fold ledgers are machine-readable. No-trade return is zero; trade win rates and average trade gains/losses are undefined because the verified strategies entered no positions. No confidence interval or performance p-value is asserted for dependent, sparse selected observations.
5. **Offline paper ledger:** `PaperLedger` stores simulated fills in SQLite with atomic idempotency across concurrent callers, immutable order-ID content, signal-before-quote validation, future/stale-price rejection, versioned inputs, chronological history, cash/position reconciliation and a kill switch. Long-only cash-funded fills are supported; shorts are deliberately rejected until a borrow/locate ledger exists. Short strategy research remains available in the backtest. There is no live order route or scheduled service.

## Reproduce locally

From the repository root in PowerShell, with the project dependencies installed:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
.\.venv\Scripts\python.exe -m quant_research.workflow
.\.venv\Scripts\python.exe -m pytest -q
```

The workflow requires the cached, Git-ignored inputs already collected for this project. It performs no network calls. If inputs are absent or have calendar gaps it stops; it never fabricates or fills prices. The repository README documents the separate acquisition jobs. Tests use deterministic local fixtures and no API calls. The managed environment may require `--basetemp` in an allowed writable directory.

## Interpretation and next research decision

These deliverables complete the requested software/research workflow; they do not establish a profitable strategy or certify the source data. The strict earnings and selected-pairs portfolios remain flat. Earlier negative short-strategy performance was conditional on vendor dates and should not be substituted for the strict result.

Useful future work is additional source verification, a newly registered economically motivated pair family with a new evaluation protocol, actual borrow availability modeling, and a separately approved paper scheduler only after operational controls and data coverage suffice. No purchase or external communication is needed to reproduce the completed work.

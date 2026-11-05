# Research automation roadmap

Scope: local/batch research progressing to supervised, scheduled paper research.
No Monte Carlo or live order execution. This plan records intended work, not
completed capabilities or accepted research results.

## 1. Review and commit the foundation

- Review timing, validation, missing-data behavior, statistics, and provenance.
- Test the active worktree explicitly; retain deterministic fixtures.
- Record a reproducible environment and commit reviewed changes locally.
- Keep remote publication separate from local development.

Exit: reviewed local baseline, recorded checks, and reproducible setup instructions.

## 2. Establish data sources

- Keep Yahoo Finance behind the price-provider interface.
- Evaluate earnings source coverage before selecting a subscription.
- Verify historical announcement times, availability times, original consensus
  snapshots, EPS definitions, revisions, fiscal periods, and licensing.
- Preserve immutable inputs and retrieval metadata. Mark unverifiable fields
  unavailable or restrict the corresponding analysis to exploratory use.

Owner input: data budget and any existing provider subscriptions. Credentials
belong in local environment configuration, not chat or version control.

Exit: documented data contracts and a small real-data sample passing validation.

## 3. Define universe and exchange calendar

- Use the owner's recovered five-rule stock screen in configs/stock_screen_v1.json
  as a separately reported variant; see docs/stock-scanner-integration.md.
- Keep industry selection under the existing dynamic industry-ranking specification.
- Establish the dated candidate pool and the rule for any approximately 100-stock
  cap; the source scanner does not specify that cap or historical membership.
- Record inclusion rationale, effective dates, classification source/version,
  and survivorship limitations. Never backdate current membership as fact.
- Use a versioned exchange calendar covering holidays, daylight saving changes,
  and early closes; validate announcement-to-session alignment.

Exit: versioned, nonempty universe and validated session calendar.

## 4. Run the first reproducible real-data study

- Start with a small sample before expanding to approximately 100 stocks.
- Freeze hypotheses, windows, split boundaries, and correction families before
  inspecting evaluation results; preserve an untouched final holdout.
- Record exclusions, source/code/configuration identities, benchmark conventions,
  and dependence-aware inference limitations.
- Distinguish descriptive event returns from executable strategy returns.
- Require feasible execution, costs, benchmarks, and separate out-of-sample
  evidence before accepting any strategy result.

Exit: rerunnable report with traceable inputs and explicit limitations.

## 5. Add scheduled-run safeguards

- Implement idempotency, retries/backoff, rate limiting, stale-data rejection,
  structured logs, failure visibility, and a kill switch before scheduling.
- Test outage, duplicate-run, partial-write, and recovery behavior.
- Select the execution host and schedule only after the batch pipeline passes.

Owner input later: Windows PC or hosted environment, operating hours, and alert
destination. A local PC must be awake and connected during scheduled runs.

Exit: supervised scheduled runs with auditable failures and safe recovery.

## 6. Add the paper ledger

- Record simulated decisions, orders, feasible fills, costs, positions, and P&L.
- Bind every record to the signal, data, and configuration versions.
- Reconcile accounting and prevent duplicate fills or stale-input decisions.
- Validate paper behavior before unattended operation; retain a kill switch.

Exit: reconciled, visibly simulated ledger and a documented unattended-run gate.

## Immediate owner decisions

1. Free data only, or a maximum monthly data budget; existing provider names.
2. Stock-screen rules have been recovered from the supplied stock_scanner.py;
   exact candidate membership and any 100-stock ranking/cap remain to be defined.
3. Execution-host preference can wait until the scheduling milestone.

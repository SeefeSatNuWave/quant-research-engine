# FMP versus free sources for the five-rule screen

Reviewed 2026-11-04. This is a documentation assessment, not a measured data-quality
benchmark. No authenticated FMP sample was downloaded and no subscription selected.
The stock-screen definition remains configs/stock_screen_v1.json.

## Decision

Use free prices to develop and validate price-derived rules. SEC filings can
support revenue research with explicit filing availability and revision handling.
FMP is a candidate for simplifying financial and earnings collection, but paying
does not establish historical point-in-time validity. Keep historical tests of
unverified fields exploratory or unavailable.

## Requirements comparison

| Screen input | Free approach | FMP assessment |
|---|---|---|
| Close, SMA50, quarter open | Yahoo/yfinance daily history and actions; validate sessions and adjustments | Daily prices available; sample adjustment consistency before switching |
| Quarterly revenue YoY | Yahoo quarterly statements for current research; SEC filing history for explicit original filings | Financial statements/growth endpoints simplify collection; period labels alone do not establish availability |
| Last reported EPS beat | Yahoo exposes earnings dates/history, but completeness and original consensus provenance need validation | Earnings records contain actual/estimated EPS; whether historical estimates are frozen before release remains unverified |
| PEG < 1 | Scanner uses vendor PEG with a computed fallback; preserve the selected definition and retrieval evidence | Vendor documents trailing P/E divided by YoY EPS growth percent; do not assume equality with Yahoo's vendor PEG |
| Historical decision replay | Current Yahoo info fields are insufficient to reconstruct past snapshots | Standard analyst estimates cannot be queried as of a historical date according to FMP's FAQ |

The Yahoo interfaces are documented in [yfinance financials](https://ranaroussi.github.io/yfinance/reference/yfinance.financials.html)
and [yfinance overview](https://ranaroussi.github.io/yfinance/). This does not certify
coverage for our candidate universe. The [SEC API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
provides submissions and XBRL without API keys. Matching fiscal periods, amendments
and actual information availability is still our responsibility. SEC filings do
not supply the market's analyst consensus.

## Important FMP findings

The [FMP data FAQ](https://site.financialmodelingprep.com/faqs?code=data) explicitly
says historical as-of analyst-estimate snapshots cannot be queried through the
API on any plan. Its internal revisions are not equivalent to exposed historical
snapshots. This corrects the earlier tentative interpretation in this chat.
The FAQ also documents the trailing PEG formula. These findings do not resolve
the separate historical earnings-record epsEstimated retention policy.

The [earnings endpoint](https://site.financialmodelingprep.com/developer/docs/stable/earnings-company)
shows epsActual, epsEstimated, date and lastUpdated. lastUpdated must not be used
as proof of when the estimate was originally known.
The [June 5, 2026 changelog](https://site.financialmodelingprep.com/developer/docs/changelog)
documents includeReportTimes with report-period information, confirmed/estimated
status and estimated report time. Validate historical coverage and precision;
an estimated time is not a verified publication timestamp.

## Plan implications

The [pricing comparison](https://site.financialmodelingprep.com/developer/docs/pricing)
shows annual-billing equivalents of Starter $19/month and Premium $49/month.
Basic has 250 calls/day and restricted symbols/results. Financial Estimates is
annual-only on Basic/Starter; Premium removes that stated period restriction.
Calendar history limits are one month (Basic), one year (Starter), and five years
(Premium). Per-symbol earnings history is a separate endpoint. Premium is the
candidate to evaluate for the full quarterly workflow; it is not yet approved.

## Sample acceptance questions before purchase

1. Does historical earnings epsEstimated preserve the last consensus before
   publication, or can later changes overwrite it? What timestamps and EPS basis
   establish that? Request actual records, not only a verbal coverage claim.
2. What fraction of sampled historical events has confirmed timing, correct fiscal
   periods, and matching actual/consensus definitions?
3. Can original revenue filings and amendments be identified separately?
4. Which PEG definition, price date, and growth period applies to every value?
5. Are failed/delisted names and historical membership changes covered, and can
   raw data be retained locally under the selected license?

A sample comparison should report missing fields, duplicate events, revisions,
price/action discrepancies and issuer-source checks. Agreement between two
vendors alone is not proof that either is historically correct. Forward storage
of snapshots helps future research but cannot reconstruct missing past snapshots.

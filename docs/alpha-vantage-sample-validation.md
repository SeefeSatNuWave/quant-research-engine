# Alpha Vantage Apple sample validation

Reviewed 2026-11-04 America/Denver (2026-11-05 UTC). This is a three-event spot check, not certification of the provider or all 123 downloaded quarters. No new API requests were needed for this review.

## Input and method

Cached input: `data/raw/alpha_vantage_probe/AAPL_earnings.json` (Git-ignored).
SHA256: `053DC0A78743123CBA1203AC6375AA81F0B0AF7D4BF27651E20E75404ACF4CFB`.
Retrieval: `2026-11-05T01:02:39.8051846Z`. Provider function: `EARNINGS`.

Selected two ordinary quarters and the October 2024 special-charge quarter to inspect accounting-basis differences. Compared vendor records with original Apple releases and dated consensus reporting. Web pages were read today; their displayed historical dates are not independently archived pre-event snapshots. No claim of frozen historical consensus is made.

## Findings

| Report date | Vendor actual EPS | Apple diluted GAAP EPS | Vendor estimate | Recomputed surprise % | Vendor fiscal end / Apple fiscal end |
| --- | ---: | ---: | ---: | ---: | --- |
| 2024-10-31 | 0.97 | 0.97 | 0.95 | 2.1053 | 2024-09-30 / 2024-09-28 |
| 2025-01-30 | 2.40 | 2.40 | 2.34 | 2.5641 | 2024-12-31 / 2024-12-28 |
| 2025-05-01 | 1.65 | 1.65 | 1.62 | 1.8519 | 2025-03-31 / 2025-03-29 |

All three report dates and actual EPS match the Apple releases. Decimal arithmetic confirmed `surprise = actual - estimate` and `surprisePercentage = 100 * (actual - estimate) / abs(estimate)` to four decimals. This verifies internal arithmetic, not estimate provenance. The vendor period labels must be retained separately from verified fiscal period ends; do not silently equate them.

Original releases:

- [Apple fiscal Q4 2024](https://www.apple.com/newsroom/2024/10/apple-reports-fourth-quarter-results/)
- [Apple fiscal Q1 2025](https://www.apple.com/newsroom/2025/01/apple-reports-first-quarter-results/)
- [Apple fiscal Q2 2025](https://www.apple.com/newsroom/2025/05/apple-reports-second-quarter-results/)

### Consensus and accounting basis

- October 2024: Apple reported GAAP EPS of 0.97 and non-GAAP EPS of 1.64 excluding a one-time tax charge. [TipRanks' October 30 preview](https://www.tipranks.com/news/apple-aapl-q4-earnings-preview-heres-what-to-expect) reported consensus of 1.60. The vendor's 0.95 estimate is not corroborated by that source; its basis is unresolved. This does not prove the vendor is wrong: different accounting definitions and analyst panels can differ. Do not replace 0.95 with 1.60 while keeping GAAP actual 0.97; that would mix potentially incompatible measures.
- January 2025: [Benzinga's January 30 pre-release article](https://www.benzinga.com/25/01/43328477/tesla-apple-and-3-stocks-to-watch-heading-into-thursday) reports its own data service's consensus of 2.35 versus vendor 2.34. This is a discrepancy to retain, not evidence by itself of revision or error.
- May 2025: [Associated Press' same-day post-release report](https://apnews.com/article/70e4b60e081814ca11a75fe02622535b) attributes 1.62 consensus to FactSet, matching the vendor. This corroborates the number but is not a pre-release snapshot and does not establish the vendor's original availability time.

All three consensus values remain unverified for strict point-in-time use. The API sample contains no consensus publication timestamp or explicit EPS accounting-basis field.

### Announcement timing

All three vendor records say `post-market`. Apple pages identify the dates and 2 p.m. Pacific conference calls, but conference-call time is not release time. [Apple's October 2024 8-K mirror](https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/bdc78279-2e3b-4645-8116-9eb36dfe8000.html) and [January 2025 8-K mirror](https://d18rn0p25nwr6d.cloudfront.net/CIK-0000320193/015cb8c6-4d12-4e25-a5d1-ac2d37cc4e1b.html) are indexed with after-close receipt times. Filing receipt times do not establish first public release time. The [May 2025 Business Wire release syndicated by StreetInsider](https://www.streetinsider.com/Business%2BWire/Apple%2Breports%2Bsecond%2Bquarter%2Bresults/24728997.html) is indexed at 4:30 p.m. EDT; full-page retrieval timed out. These are supporting evidence for the session label, not sufficient verification of exact original release timestamps across the sample.

Preserve the coarse timing label and uncertainty. Never fabricate an exact timestamp from `post-market`; use an explicitly versioned coarse-timing policy and an exchange calendar, or obtain an authoritative timestamp. A release after the close cannot earn that day's earlier close-to-close return as an executable strategy.

## Disposition and next milestone

- Suitable for continued exploratory data engineering and a small manually verified event-date study.
- Not accepted as a strict point-in-time earnings-surprise dataset. No strategy results or trading conclusions were produced.
- Keep raw records immutable. Add separate fiscal-date, accounting-basis, announcement-time and consensus-verification fields, including exclusion reasons.
- Implement the provider adapter with cache/provenance, quota-aware behavior, credential-safe errors and deterministic tests. Resolve the IBM provider notice without assuming it was a quota error.
- First real-data baseline should use verified event dates with explicit timing assumptions; leave unverified surprise classifications out of confirmatory research. Broader coverage and original pre-event estimates require additional validation.

Owner action: none required now. No subscription purchase or new key is needed to implement the adapter and validation gates. Provider clarification may later be needed about estimate basis, revisions and availability history.

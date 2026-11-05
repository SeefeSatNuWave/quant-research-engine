"""Descriptive event consistency; no hypothesis tests or strategy selection."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def describe(values: pd.Series) -> dict:
    values = values.dropna().astype(float)
    if not np.isfinite(values).all():
        raise ValueError('Returns must be finite')
    n = len(values)
    trimmed = values.drop(values.abs().idxmax()) if n > 1 else pd.Series(dtype=float)
    return {'n': n, 'outperform_count': int((values > 0).sum()),
            'underperform_count': int((values < 0).sum()), 'tie_count': int((values == 0).sum()),
            'outperform_rate': float((values > 0).mean()) if n else float('nan'),
            'mean_excess': values.mean(), 'median_excess': values.median(),
            'min_excess': values.min(), 'max_excess': values.max(),
            'mean_without_largest_absolute_move': trimmed.mean()}


def summarize(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.duplicated(['event_id', 'window']).any():
        raise ValueError('Duplicate event/window')
    frame = frame.copy().reset_index(drop=True)
    frame['year'] = pd.to_datetime(frame.announcement_at_utc, utc=True).dt.tz_convert('America/New_York').dt.year
    valid = frame.exclusion_reason.isna() & frame.exclusion_reason_spy.isna() & ~frame.overlap_excluded
    frame.loc[~valid, 'excess_return'] = float('nan')
    annual = pd.DataFrame([{'symbol': symbol, 'window': window, 'year': year,
                           'excluded': int(group.excess_return.isna().sum()), **describe(group.excess_return)}
                          for (symbol, window, year), group in frame.groupby(['symbol', 'window', 'year'])])
    rows = []
    for (symbol, window), group in frame.groupby(['symbol', 'window']):
        years = annual.loc[(annual.symbol == symbol) & (annual.window == window) & (annual.n > 0)]
        rows.append({'symbol': symbol, 'window': window, **describe(group.excess_return),
                     'years_observed': len(years), 'positive_mean_years': int((years.mean_excess > 0).sum()),
                     'negative_mean_years': int((years.mean_excess < 0).sum())})
    return pd.DataFrame(rows), annual


def run(root: Path) -> None:
    source = root / 'event_windows.csv'
    overall, annual = summarize(pd.read_csv(source))
    overall.to_csv(root / 'consistency.csv', index=False)
    annual.to_csv(root / 'consistency_by_year.csv', index=False)
    lines = ['# Earnings pattern consistency', '',
             'Descriptive follow-up on the same exploratory sample. Positive excess means stock return exceeded SPY over identical dates. Ties are not wins. Years use the announcement boundary proxy in New York time. No inference, independent-observation assumption or trading-performance claim is made.', '',
             'Largest-move removal is a deterministic sensitivity diagnostic, not resampling or an alternative strategy result. Original observations remain intact. Each annual cell has only a few events; vendor timing remains unverified.', '',
             '| Stock | Window | Beats / events | Median excess | Mean excess | Positive-mean years | Mean excluding largest absolute move |',
             '|---|---|---:|---:|---:|---:|---:|']
    for r in overall.itertuples():
        lines.append(f'| {r.symbol} | {r.window} | {r.outperform_count}/{r.n} | {r.median_excess:.2%} | {r.mean_excess:.2%} | {r.positive_mean_years}/{r.years_observed} | {r.mean_without_largest_absolute_move:.2%} |')
    lines.extend(['', 'Full yearly counts, means, medians, ranges and exclusions are in consistency_by_year.csv. Percentages above express differences in returns (percentage points).'])
    (root / 'consistency.md').write_text('\n'.join(lines), encoding='utf-8')
    (root / 'consistency_manifest.json').write_text(json.dumps({
        'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'method': 'descriptive_v1', 'inference': 'none; same-sample follow-up, no holdout'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-dir', type=Path, default=Path('reports/pilot_v1'))
    run(parser.parse_args().report_dir)

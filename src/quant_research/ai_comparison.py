"""Descriptive, paired-event comparison of a frozen AI-exposure hypothesis."""
import hashlib
import json
from pathlib import Path

import pandas as pd


def paired_events(frame: pd.DataFrame, groups: dict) -> pd.DataFrame:
    data = frame.loc[frame.window.isin(['pre_runup', 'post_event'])].copy()
    if data.duplicated(['event_id', 'window']).any():
        raise ValueError('Duplicate event/window')
    bad = data.exclusion_reason.notna() | data.exclusion_reason_spy.notna() | data.overlap_excluded
    data.loc[bad, ['return', 'excess_return']] = float('nan')
    index = ['event_id', 'symbol', 'announcement_at_utc']
    pair = data.pivot(index=index, columns='window', values=['return', 'excess_return'])
    pair.columns = ['_'.join(c) for c in pair.columns]
    pair = pair.reset_index()
    pair['group'] = pair.symbol.map(groups)
    if pair.group.isna().any():
        raise ValueError('Unclassified company')
    pair['year'] = pd.to_datetime(pair.announcement_at_utc, utc=True).dt.tz_convert('America/New_York').dt.year
    pair['eligible'] = pair[['excess_return_pre_runup', 'excess_return_post_event']].notna().all(axis=1)
    pair['paired_pattern'] = (pair.excess_return_pre_runup > 0) & (pair.excess_return_post_event < 0)
    pair['raw_paired_pattern'] = (pair.return_pre_runup > 0) & (pair.return_post_event < 0)
    return pair


def metrics(group: pd.DataFrame) -> dict:
    eligible = group.loc[group.eligible]
    return {'events': len(group), 'eligible': len(eligible), 'excluded': int((~group.eligible).sum()),
            'paired_count': int(eligible.paired_pattern.sum()), 'paired_rate': eligible.paired_pattern.mean(),
            'raw_paired_rate': eligible.raw_paired_pattern.mean(),
            'pre_mean': eligible.excess_return_pre_runup.mean(),
            'post_mean': eligible.excess_return_post_event.mean(),
            'pre_median': eligible.excess_return_pre_runup.median(),
            'post_median': eligible.excess_return_post_event.median()}


def run() -> None:
    config_path = Path('configs/ai_hypothesis_v1.json')
    config = json.loads(config_path.read_text())
    root = Path('reports/ai_pilot_v1')
    source = root / 'event_windows.csv'
    groups = {s:g for g in ('ai_related', 'comparison') for s in config[g]}
    paired = paired_events(pd.read_csv(source), groups)
    paired.to_csv(root/'paired_events.csv', index=False)
    summary = pd.DataFrame([{'group':g, **metrics(v)} for g,v in paired.groupby('group')])
    annual = pd.DataFrame([{'group':g,'year':y, **metrics(v)} for (g,y),v in paired.groupby(['group','year'])])
    stock = pd.DataFrame([{'group':g,'symbol':s, **metrics(v)} for (g,s),v in paired.groupby(['group','symbol'])])
    for name, frame in [('cohort_summary',summary),('cohort_by_year',annual),('cohort_by_stock',stock)]:
        frame.to_csv(root/f'{name}.csv',index=False)
    lines = ['# AI earnings hypothesis comparison', '', config['hypothesis'], '', config['classification'], '', config['status'], '',
             'Primary pattern: the SAME event must outperform SPY before earnings and underperform SPY afterward. Rates use events with both valid windows. Raw pattern instead requires an actual price rise then decline. Reported means are event-weighted; no risk or sector matching has been applied.', '',
             '| Group | Eligible | Pattern count | Pattern rate | Raw rise/drop rate | Mean pre excess | Mean post excess |', '|---|---:|---:|---:|---:|---:|---:|']
    for r in summary.itertuples():
        lines.append(f'| {r.group} | {r.eligible} | {r.paired_count} | {r.paired_rate:.1%} | {r.raw_paired_rate:.1%} | {r.pre_mean:.2%} | {r.post_mean:.2%} |')
    lines += ['', 'Timing remains unverified. Results are descriptive, dependent and subject to survivorship, subjective classification and same-sample selection. No p-values, significance claims, costs or executable strategy performance. Apple and Microsoft were already inspected before this hypothesis was specified. Earlier pilot outputs are retained.', '', 'See cohort_by_year.csv and cohort_by_stock.csv for full breakdowns.']
    (root/'ai_comparison.md').write_text('\n'.join(lines),encoding='utf-8')
    (root/'ai_comparison_manifest.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [source,config_path,Path(__file__)]},indent=2))
    print(summary.to_string(index=False))
    print(annual[['group','year','eligible','paired_count','paired_rate']].to_string(index=False))


if __name__ == '__main__':
    run()

import pandas as pd
import pytest
from quant_research.consistency import describe, summarize


def test_counts_median_and_outlier_sensitivity():
    r = describe(pd.Series([.10, -.01, -.02, 0, None]))
    assert r['n'] == 4
    assert r['outperform_rate'] == .25
    assert r['tie_count'] == 1
    assert r['median_excess'] == pytest.approx(-.005)
    assert r['mean_without_largest_absolute_move'] == pytest.approx(-.01)


def test_local_year_and_exclusions():
    frame = pd.DataFrame({'event_id':['a','b'], 'symbol':['ABC']*2, 'window':['post']*2,
                          'announcement_at_utc':['2024-01-01T04:59:59Z','2024-02-01T04:59:59Z'],
                          'excess_return':[.1,.9], 'exclusion_reason':[None,'gap'],
                          'exclusion_reason_spy':[None,None], 'overlap_excluded':[False,False]})
    overall, annual = summarize(frame)
    assert overall.iloc[0]['n'] == 1
    assert annual.loc[annual.year == 2023,'n'].iloc[0] == 1
    assert annual.loc[annual.year == 2024,'excluded'].iloc[0] == 1

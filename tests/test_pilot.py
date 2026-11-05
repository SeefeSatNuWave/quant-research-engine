import pandas as pd
import pytest
from quant_research.pilot import calendar, compare


def test_holidays_early_close_dst_and_special_closure():
    sessions = calendar('2024-01-01', '2025-01-31').set_index('session_date')
    assert '2024-07-04' not in sessions.index
    assert '2025-01-09' not in sessions.index
    assert pd.Timestamp(sessions.loc['2024-11-29', 'close_at']).hour == 18
    assert pd.Timestamp(sessions.loc['2024-03-08', 'close_at']).hour == 21
    assert pd.Timestamp(sessions.loc['2024-03-11', 'close_at']).hour == 20


def test_spy_matches_intervals_and_missing_bars_exclude_pair():
    sessions = calendar('2024-01-02', '2024-02-15')
    dates = sessions.session_date.tolist()
    event = pd.DataFrame([{'event_id':'x','symbol':'ABC','fiscal_period':'2023Q4','announcement_at':'2024-01-16T23:59:59-05:00','source':'fixture'}])
    prices = pd.concat([pd.DataFrame({'symbol':symbol,'session_date':dates,'adj_close':[100 * growth**i for i in range(len(dates))]}) for symbol,growth in [('ABC',1.02),('SPY',1.01)]])
    result = compare(event, prices, sessions).set_index('window')
    assert result.loc['event_reaction','excess_return'] == pytest.approx(.01)
    assert result.loc['post_event','excess_return'] == pytest.approx(1.02**5 - 1.01**5)
    prices = prices.loc[~((prices.symbol == 'SPY') & (prices.session_date == '2024-01-17'))]
    result = compare(event, prices, sessions).set_index('window')
    assert pd.isna(result.loc['event_reaction','excess_return'])

import pandas as pd
import pytest
from test_earnings_event_study import inputs
from quant_research.earnings_event_study import EventStudyError, build_event_windows, validate_events, validate_calendar


def test_empty_inputs_fail_clearly():
    events, _, calendar = inputs()
    with pytest.raises(EventStudyError, match='at least one'):
        validate_events(events.iloc[:0])
    with pytest.raises(EventStudyError, match='contain sessions'):
        validate_calendar(calendar.iloc[:0])


@pytest.mark.parametrize('value', [float('inf'),float('-inf')])
def test_nonfinite_values_rejected(value):
    events, prices, calendar = inputs()
    prices['adj_close']=prices['adj_close'].astype(float)
    prices.loc[0,'adj_close']=value
    with pytest.raises(EventStudyError):
        build_event_windows(events,prices,calendar)
    events.loc[0,'actual_eps']=value
    with pytest.raises(EventStudyError):
        validate_events(events)


def test_missing_announcement_rejected():
    events, _, _ = inputs()
    events.loc[0,'announcement_at']=None
    with pytest.raises(EventStudyError):
        validate_events(events)

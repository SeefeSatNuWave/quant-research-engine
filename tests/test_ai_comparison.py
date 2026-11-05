import pandas as pd
from quant_research.ai_comparison import paired_events, metrics


def test_pattern_requires_same_event_and_valid_windows():
    rows=[]
    for event, pre, post in [('one', .1,.2),('two',-.1,-.2),('three',.1,-.2),('four',.1,-.2)]:
        for window,value in [('pre_runup',pre),('post_event',post)]:
            rows.append(dict(event_id=event,symbol='ABC',announcement_at_utc='2024-01-10T22:00:00Z',window=window,
                             excess_return=value,**{'return':value},exclusion_reason='gap' if event=='four' else None,
                             exclusion_reason_spy=None,overlap_excluded=False))
    pairs=paired_events(pd.DataFrame(rows),{'ABC':'ai_related'})
    result=metrics(pairs)
    assert result['eligible']==3
    assert result['paired_count']==1
    assert result['paired_rate']==1/3
    assert result['excluded']==1

import numpy as np
import pandas as pd
import pytest
from quant_research.workflow import account_v2, audited_events, daily_metrics, folds, select


def test_self_financing_costs_and_known_returns():
    prices=pd.DataFrame({'ABC':[100.,200.,220.]},index=pd.date_range('2024-01-01',periods=3))
    book=pd.DataFrame({'ABC':[0.,1.,0.]},index=prices.index)
    result=account_v2(prices,book,10,0)
    # Invest cash less fee: entry equity=1/(1+c); liquidation pays c.
    assert result.equity.iloc[-1]==pytest.approx(1.1/1.001*.999)
    assert result.iloc[0].gross_return==0
    assert np.allclose(result.cost_fraction,result.fee_fraction+result.half_spread_fraction+result.slippage_fraction)


def test_no_trade_and_missing_data():
    prices=pd.DataFrame({'ABC':[100.,101.]},index=pd.date_range('2024-01-01',periods=2))
    book=prices*0
    assert account_v2(prices,book,10,.05).equity.iloc[-1]==1
    prices.iloc[0,0]=np.nan
    with pytest.raises(ValueError,match='Missing'):
        account_v2(prices,book,10,.05)


def test_expanding_folds_are_disjoint_and_train_precedes_test():
    panel=pd.DataFrame({'ABC':range(10)},index=pd.date_range('2024-01-01',periods=10))
    config={'formation_start':'2024-01-01','folds':[{'id':'a','start':'2024-01-04','end':'2024-01-07'}, {'id':'b','start':'2024-01-07','end':'2024-01-11'}]}
    parts=list(folds(panel,config))
    assert len(parts[0][1])==3 and len(parts[1][1])==6
    assert not set(parts[0][2].index)&set(parts[1][2].index)
    for _,train,test in parts:
        assert train.index.max()<test.index.min()


def test_timing_requires_actual_release_evidence():
    events=pd.DataFrame({'symbol':['NEE','MSFT','ABC'], 'announcement_at':['2025-04-23T23:59:59-04:00','2023-07-25T00:00:00-04:00','2024-01-02T00:00:00-05:00']})
    review=pd.DataFrame([
        dict(symbol='NEE',reported_date='2025-04-23',status='conflicts_with_company_release',source_evidence='Company release available at 07:30 ET',source_url='https://example.test/release'),
        dict(symbol='MSFT',reported_date='2023-07-25',status='conflicts_with_company_schedule',source_evidence='planned',source_url='https://example.test/schedule')])
    audited=audited_events(events,review)
    assert audited.audit_exclusion.isna().sum()==1
    assert audited.loc[0,'corrected_release_session']=='pre-market'
    assert '00:00:00' in audited.loc[0,'announcement_at']
    assert audited.loc[1,'audit_exclusion']=='vendor_conflicts_with_schedule_actual_release_unverified'


def test_liquidation_cost_is_same_day_observation():
    prices=pd.DataFrame({'ABC':[100.,100.]},index=pd.date_range('2024-01-01',periods=2))
    book=pd.DataFrame({'ABC':[1.,0.]},index=prices.index)
    result=account_v2(prices,book,10,0)
    summary=daily_metrics(result)
    assert summary['daily_observations']==1
    assert summary['net_return']==pytest.approx(.999/1.001-1)

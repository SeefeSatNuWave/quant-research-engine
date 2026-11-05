import numpy as np
import pandas as pd
import pytest
from quant_research.research_baseline import account, formation, pair_targets


def test_fill_only_earns_following_interval_and_costs_reduce_equity():
    dates=pd.date_range('2024-01-01',periods=3)
    prices=pd.DataFrame({'ABC':[100.,200.,220.]},index=dates)
    targets=pd.DataFrame({'ABC':[0.,1.,0.]},index=dates)
    free=account(prices,targets,0,0)
    cost=account(prices,targets,10,0)
    assert free.equity.iloc[-1]==pytest.approx(1.1)
    assert cost.equity.iloc[-1]==pytest.approx(1.1*.999**2)
    assert free.turnover.sum()==pytest.approx(2)


def test_short_borrow_calendar_days_and_missing_price():
    dates=pd.to_datetime(['2024-01-05','2024-01-08'])
    prices=pd.DataFrame({'ABC':[100.,90.]},index=dates)
    targets=pd.DataFrame({'ABC':[-1.,0.]},index=dates)
    result=account(prices,targets,0,.05)
    assert result.equity.iloc[-1]==pytest.approx(1.1-.05*3/365)
    assert account(prices,targets*0,10,.05).equity.iloc[-1]==1
    prices.iloc[1,0]=np.nan
    with pytest.raises(ValueError,match='Missing'):
        account(prices,targets,0,0)


def test_pair_signal_uses_previous_close():
    dates=pd.date_range('2024-01-01',periods=5)
    prices=pd.DataFrame({'A':np.exp([0,2.5,0,0,0]),'B':np.ones(5)},index=dates)
    fit=pd.Series(dict(left='A',right='B',intercept=0,beta=1,spread_mean=0,spread_std=1))
    settings=dict(entry_z=2,exit_z=.5,stop_z=4,max_holding_sessions=20)
    target,_=pair_targets(prices,fit,settings)
    assert target.iloc[1].abs().sum()==0
    assert target.iloc[2]['A']==-.5
    assert target.iloc[3].abs().sum()==0


def test_formation_cannot_see_evaluation_prices():
    dates=pd.bdate_range('2023-01-02',periods=320)
    x=np.arange(320)/1000+np.sin(np.arange(320)/13)/100
    prices=pd.DataFrame({'A':np.exp(x+np.sin(np.arange(320))/200),'B':np.exp(x)},index=dates)
    cutoff=str(dates[280].date())
    before=formation(prices,[['A','B']],cutoff)
    prices.iloc[280:]*=100
    after=formation(prices,[['A','B']],cutoff)
    pd.testing.assert_frame_equal(before,after)

"""Conditional paper-research accounting and formation-only pairs baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint

from quant_research.data.prices import YahooFinanceSource, download_and_cache_prices
from quant_research.earnings_event_study import _bh
from quant_research.pilot import calendar


def account(prices: pd.DataFrame, weights: pd.DataFrame, bps: float, borrow: float) -> pd.DataFrame:
    """Targets filled at each close, earn only the NEXT close interval.

    Adjusted prices represent total-return units; shorts include negative total
    return (including dividend liability). Dollar weights rebalance daily.
    Costs charged on traded notional relative to pre-trade equity, with equity
    reduced before the next interval. Cash earns zero; no leverage above 1.
    """
    if not prices.index.equals(weights.index) or not prices.columns.equals(weights.columns):
        raise ValueError('Price/weight alignment mismatch')
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError('Missing or invalid price bars; no forward filling')
    if not np.isfinite(weights.to_numpy()).all() or (weights.abs().sum(axis=1) > 1.000001).any():
        raise ValueError('Invalid weights or gross exposure above one')
    if (weights.iloc[-1] != 0).any():
        raise ValueError('Final target must liquidate positions')
    prior = np.zeros(len(prices.columns))
    equity = 1.0
    rows = []
    for i in range(len(prices)):
        target = weights.iloc[i].to_numpy(dtype=float)
        turnover = float(np.abs(target-prior).sum())
        fee = turnover*bps/10000
        exposure = float(np.abs(target).sum())
        gross = 0.0
        financing = 0.0
        if i+1 < len(prices):
            returns = prices.iloc[i+1].to_numpy()/prices.iloc[i].to_numpy()-1
            gross = float(target @ returns)
            days = (prices.index[i+1]-prices.index[i]).days
            financing = float(-np.minimum(target,0).sum())*borrow*days/365
            growth = 1+gross-financing
            if growth <= 0:
                raise ValueError('Portfolio insolvency')
            prior = target*(1+returns)/growth
        else:
            prior = target
        net = (1-fee)*(1+gross-financing)-1
        equity *= 1+net
        rows.append({'fill_date':str(prices.index[i].date()),
                     'return_end':str(prices.index[min(i+1,len(prices)-1)].date()),
                     'gross_return':gross,'net_return':net,'turnover':turnover,
                     'exposure':exposure,'cost_fraction':fee,'borrow_fraction':financing,'equity':equity})
    return pd.DataFrame(rows)


def metrics(ledger: pd.DataFrame) -> dict:
    r=ledger.net_return
    eq=np.r_[1.,ledger.equity.to_numpy()]
    vol=float(r.std(ddof=1)*np.sqrt(252))
    return {'net_return':float(eq[-1]-1),'annualized_volatility':vol,
            'sharpe_zero_rf':float(r.mean()*252/vol) if vol>0 else None,
            'max_drawdown':float(np.min(eq/np.maximum.accumulate(eq)-1)),
            'turnover':float(ledger.turnover.sum()),'mean_gross_exposure':float(ledger.exposure.mean()),
            'positive_return_intervals':int((r>0).sum()),'negative_return_intervals':int((r<0).sum())}


def formation(prices: pd.DataFrame, candidates: list, cutoff: str) -> pd.DataFrame:
    train = prices.loc[prices.index < pd.Timestamp(cutoff)]
    rows=[]
    for a,b in candidates:
        row={'left':a,'right':b,'formation_n':len(train),'formation_last':str(train.index[-1].date()),'error':None}
        try:
            logs=np.log(train[[a,b]].to_numpy())
            if not np.isfinite(logs).all() or len(logs)<252:
                raise ValueError('Incomplete formation data')
            y,x=logs[:,0],logs[:,1]
            beta,intercept=np.polyfit(x,y,1)
            spread=y-intercept-beta*x
            halves=np.array_split(logs,2)
            betas=[np.polyfit(h[:,1],h[:,0],1)[0] for h in halves]
            row.update(beta=float(beta),intercept=float(intercept),spread_mean=float(spread.mean()),spread_std=float(spread.std(ddof=1)),
                       p_value=float(coint(y,x,trend='c',autolag='aic')[1]),
                       left_level_adf_p=float(adfuller(y,autolag='AIC')[1]),right_level_adf_p=float(adfuller(x,autolag='AIC')[1]),
                       half_beta_change=float(abs(betas[1]-betas[0])/max(abs(beta),1e-12)))
        except (ValueError,np.linalg.LinAlgError) as exc:
            row.update(error=str(exc),p_value=1.0)
        rows.append(row)
    result=pd.DataFrame(rows)
    result['bh_p']=_bh(result.p_value.tolist())
    result['hypothesis_family_count']=len(candidates)
    return result


def pair_targets(prices: pd.DataFrame, fit: pd.Series, settings: dict) -> tuple[pd.DataFrame,pd.DataFrame]:
    a,b=fit.left,fit.right
    z=(np.log(prices[a])-fit.intercept-fit.beta*np.log(prices[b])-fit.spread_mean)/fit.spread_std
    weights=pd.DataFrame(0.,index=prices.index,columns=prices.columns)
    state,age=0,0
    decisions=[]
    for i in range(1,len(prices)-1):
        signal=float(z.iloc[i-1])  # yesterday's close, filled at today's close
        if state and (abs(signal)<=settings['exit_z'] or abs(signal)>=settings['stop_z'] or age>=settings['max_holding_sessions']):
            state,age=0,0
        elif not state and settings['entry_z'] <= abs(signal) < settings['stop_z']:
            state=-int(np.sign(signal)); age=0
        if state:
            weights.loc[prices.index[i],a]=state/(1+abs(fit.beta))
            weights.loc[prices.index[i],b]=-state*fit.beta/(1+abs(fit.beta))
            age+=1
        decisions.append({'signal_date':str(prices.index[i-1].date()),'fill_date':str(prices.index[i].date()),'z':signal,'state':state})
    return weights,pd.DataFrame(decisions)


def earnings_targets(prices: pd.DataFrame, symbols: list, holding: int) -> tuple[pd.DataFrame,pd.DataFrame]:
    weights=pd.DataFrame(0.,index=prices.index,columns=prices.columns)
    rows=[]
    for symbol in symbols:
        raw=json.loads((Path('data/raw/alpha_vantage')/f'{symbol}.json').read_text())
        for event in raw['quarterlyEarnings']:
            day=pd.Timestamp(event['reportedDate'])
            if not prices.index[0] <= day <= prices.index[-1]:
                continue
            entry=int(prices.index.searchsorted(day,side='right'))
            exit_=entry+holding
            reason=None
            if exit_ >= len(prices):
                reason='holding_window_outside_evaluation'
            elif (weights.iloc[entry:exit_][symbol]!=0).any():
                reason='overlapping_event'
            else:
                weights.loc[prices.index[entry:exit_],symbol]=-1/len(symbols)
            rows.append({'symbol':symbol,'reported_date':str(day.date()),'vendor_timing':event.get('reportTime'),
                         'entry':str(prices.index[entry].date()) if entry<len(prices) else None,
                         'exit':str(prices.index[exit_].date()) if exit_<len(prices) else None,
                         'exclusion':reason,'timing_verified':False})
    weights.iloc[-1]=0
    return weights,pd.DataFrame(rows)


def run(download: bool=False) -> None:
    cp=Path('configs/research_baseline_v1.json'); config=json.loads(cp.read_text())
    out=Path('reports')/config['id']; out.mkdir(parents=True,exist_ok=True)
    symbols=config['earnings']['symbols']+['SPY']
    frames=[]
    paths=[]
    for symbol in symbols:
        old=Path('data/normalized/prices')/f'{symbol}_2022-12-01_2026-02-01_1d.csv'
        new=Path('data/normalized/prices')/f'{symbol}_2026-02-01_2026-11-01_1d.csv'
        if download:
            download_and_cache_prices(YahooFinanceSource(),symbol,'2026-02-01','2026-11-01')
        paths.extend([old,new])
        frames.extend([pd.read_csv(old),pd.read_csv(new)])
    data=pd.concat(frames)
    panel=data.pivot(index='session_date',columns='symbol',values='adj_close')
    panel.index=pd.to_datetime(panel.index)
    sessions=pd.to_datetime(calendar(config['formation_start'],config['evaluation_end_exclusive']).session_date)
    panel=panel.reindex(sessions)
    panel=panel.loc[panel.index<pd.Timestamp(config['evaluation_end_exclusive'])]
    if panel.isna().any().any():
        raise ValueError('Incomplete calendar-aligned prices; evaluation stopped')
    fits=formation(panel,config['pairs']['candidates'],config['formation_end'])
    fits['selected']=(fits.error.isna() & (fits.bh_p<=config['pairs']['fdr']) & (fits.beta>0) &
                      (fits.spread_std>0) & (fits.half_beta_change<=config['pairs']['max_beta_half_change']) &
                      (fits.left_level_adf_p>.05) & (fits.right_level_adf_p>.05))
    fits.to_csv(out/'pair_formation.csv',index=False)
    evaluation=panel.loc[panel.index>=pd.Timestamp(config['evaluation_start'])]
    weights,trades=earnings_targets(evaluation,config['earnings']['symbols'],config['earnings']['holding_sessions'])
    trades.to_csv(out/'earnings_events.csv',index=False)
    strategies={'earnings_short':weights}
    for _,fit in fits.loc[fits.selected].iterrows():
        targets,decisions=pair_targets(evaluation,fit,config['pairs'])
        name=f'pairs_{fit.left}_{fit.right}'
        strategies[name]=targets
        decisions.to_csv(out/f'{name}_decisions.csv',index=False)
    spy=pd.DataFrame(0.,index=evaluation.index,columns=evaluation.columns)
    spy['SPY']=1.; spy.iloc[-1]=0
    strategies['SPY_buy_hold']=spy
    strategies['cash']=spy*0
    summaries=[]
    for name,targets in strategies.items():
        targets.to_csv(out/f'{name}_targets.csv')
        for bps in config['cost_bps_each_side']:
            ledger=account(evaluation,targets,bps,config['borrow_annual'])
            ledger.to_csv(out/f'{name}_{bps}bps_ledger.csv',index=False)
            summaries.append({'strategy':name,'cost_bps':bps,**metrics(ledger)})
    pd.DataFrame(summaries).to_csv(out/'evaluation.csv',index=False)
    limits='SIMULATED conditional research. No historical borrow locates; shorts assumed available at 5% annual borrow. Adjusted total-return units and daily rebalancing; closing fills approximate, execution not validated. Earnings dates/times unverified; next-date-close delay reduces timing risk but cannot verify a wrong date. No pre-event strategy. Formation sample already explored; evaluation period now consumed. Four pairs tested in one BH family; I(1) and stability diagnostics are filters, not proof of arbitrage. No performance significance claim.'
    (out/'report.md').write_text('# Research baseline evaluation\n\n'+limits+'\n\nPairs passing frozen formation filters: '+str(int(fits.selected.sum()))+'\n\n'+pd.DataFrame(summaries).to_string(index=False)+'\n\nNo pairs passing means no pair trade is authorized by this specification. Keep the threshold fixed; report the null finding. Paper scheduling remains disabled pending verified data, locate modeling and operational safeguards.',encoding='utf-8')
    paths += [cp,Path(__file__),*Path('data/raw/alpha_vantage').glob('*.json')]
    (out/'manifest.json').write_text(json.dumps({'config':config,'limitations':limits,'input_code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},indent=2))
    print(fits[['left','right','p_value','bh_p','half_beta_change','selected']].to_string(index=False))
    print(pd.DataFrame(summaries).to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--download',action='store_true')
    run(parser.parse_args().download)

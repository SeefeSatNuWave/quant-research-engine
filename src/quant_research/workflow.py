"""Offline audited-event and chronological walk-forward research workflow v2."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from quant_research.earnings_event_study import build_event_windows, _bh
from quant_research.pilot import calendar
from quant_research.research_baseline import formation, pair_targets, metrics


def audited_events(events: pd.DataFrame, review: pd.DataFrame) -> pd.DataFrame:
    data=events.copy()
    data['reported_date']=data.announcement_at.str[:10]
    if review.duplicated(['symbol','reported_date']).any():
        raise ValueError('Duplicate timing review')
    fields=['symbol','reported_date','status','source_evidence','source_url']
    data=data.merge(review[fields],on=['symbol','reported_date'],how='left',validate='many_to_one')
    data['audit_exclusion']='release_timing_not_independently_verified'
    # The review records actual-release evidence; a planned schedule alone is
    # insufficient. Preserve the vendor field and make corrections explicit.
    accepted=(data.status=='conflicts_with_company_release') & data.source_evidence.eq('Company release available at 07:30 ET') & data.source_url.notna()
    data['corrected_release_session']=None
    data.loc[accepted,'corrected_release_session']='pre-market'
    data.loc[accepted,'announcement_at']=[pd.Timestamp(d+' 00:00:00',tz='America/New_York').isoformat() for d in data.loc[accepted,'reported_date']]
    data.loc[accepted,'audit_exclusion']=None
    data.loc[data.status.eq('conflicts_with_company_schedule'),'audit_exclusion']='vendor_conflicts_with_schedule_actual_release_unverified'
    data.loc[data.status.eq('requires_release_verification'),'audit_exclusion']='actual_release_time_requires_verification'
    data['audit_policy']='source_supported_session_v2; midnight is a boundary proxy, not publication time'
    return data


def account_v2(prices: pd.DataFrame, targets: pd.DataFrame, bps: float, borrow: float) -> pd.DataFrame:
    if prices.empty or not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError('Prices require unique increasing sessions')
    if not prices.index.equals(targets.index) or not prices.columns.equals(targets.columns):
        raise ValueError('Alignment mismatch')
    if not np.isfinite(prices.to_numpy()).all() or (prices<=0).any().any():
        raise ValueError('Missing/invalid prices')
    if not np.isfinite(targets.to_numpy()).all() or (targets.abs().sum(axis=1)>1.000001).any():
        raise ValueError('Invalid exposure')
    if not 3<=bps<=100 or not 0<=borrow<=1 or (targets.iloc[-1]!=0).any():
        raise ValueError('Invalid costs or missing liquidation')
    prior=np.zeros(len(prices.columns)); equity=1.; rows=[]
    rate=bps/10000
    for i in range(len(prices)):
        target=targets.iloc[i].to_numpy(dtype=float)
        # Solve transaction charge on pre-trade equity while target weights are
        # fractions of post-cost equity. Contraction for the bounded cost rate.
        fee=0.
        for _ in range(100):
            next_fee=float(np.abs((1-fee)*target-prior).sum())*rate
            if abs(next_fee-fee)<1e-14:
                fee=next_fee; break
            fee=next_fee
        turnover=fee/rate
        gross=borrow_cost=0.
        if i+1<len(prices):
            r=prices.iloc[i+1].to_numpy()/prices.iloc[i].to_numpy()-1
            gross=float(target@r)
            days=(prices.index[i+1]-prices.index[i]).days
            borrow_cost=float(-np.minimum(target,0).sum())*borrow*days/365
            growth=1+gross-borrow_cost
            if growth<=0:
                raise ValueError('Insolvent simulation')
            prior=target*(1+r)/growth
        net=(1-fee)*(1+gross-borrow_cost)-1
        equity*=1+net
        rows.append(dict(fill_date=str(prices.index[i].date()),return_end=str(prices.index[min(i+1,len(prices)-1)].date()),
                         gross_return=gross,net_return=net,turnover=turnover,exposure=float(abs(target).sum()),
                         cost_fraction=fee,fee_fraction=fee/bps,half_spread_fraction=fee*2/bps,
                         slippage_fraction=fee*(bps-3)/bps,borrow_fraction=borrow_cost,equity=equity))
    return pd.DataFrame(rows)


def select(fits: pd.DataFrame, settings: dict) -> pd.Series:
    return (fits.error.isna() & fits.bh_p.le(settings['fdr']) & fits.beta.gt(0) & fits.spread_std.gt(0)
            & fits.half_beta_change.le(settings['max_beta_half_change']) & fits.left_level_adf_p.gt(.05) & fits.right_level_adf_p.gt(.05))


def daily_metrics(ledger: pd.DataFrame) -> dict:
    # Final liquidation and preceding interval may end on the same date.
    # Compound them into one observation before annualizing daily statistics.
    grouped=ledger.groupby('return_end',sort=True)
    daily=grouped.agg(turnover=('turnover','sum'),exposure=('exposure','max'))
    daily['net_return']=grouped.net_return.apply(lambda x: (1+x).prod()-1)
    daily['equity']=(1+daily.net_return).cumprod()
    result=metrics(daily.reset_index())
    result['daily_observations']=len(daily)
    return result


def folds(panel: pd.DataFrame, config: dict):
    previous_end=None
    for fold in config['folds']:
        start,end=pd.Timestamp(fold['start']),pd.Timestamp(fold['end'])
        if start>=end or (previous_end is not None and start<previous_end):
            raise ValueError('Overlapping or reversed folds')
        train=panel.loc[(panel.index>=pd.Timestamp(config['formation_start'])) & (panel.index<start)]
        test=panel.loc[(panel.index>=start) & (panel.index<end)]
        if train.empty or test.empty or train.index.max()>=test.index.min():
            raise ValueError('Invalid chronological boundary')
        yield fold,train,test
        previous_end=end


def run() -> None:
    config_path=Path('configs/workflow_v2.json'); config=json.loads(config_path.read_text())
    base=json.loads(Path(config['base_config']).read_text())
    root=Path('reports/workflow_v2'); root.mkdir(parents=True,exist_ok=True)
    source=Path('reports/ai_pilot_v1/event_audit.csv')
    audit=audited_events(pd.read_csv(source),pd.read_csv('configs/timing_audit_v1.csv'))
    audit.to_csv(root/'audited_earnings.csv',index=False)
    eligible=audit.loc[audit.audit_exclusion.isna()].copy()
    eligible.to_csv(root/'eligible_earnings.csv',index=False)
    if not eligible.empty:
        historical=pd.read_csv('reports/ai_pilot_v1/prices.csv')
        windows=build_event_windows(eligible,historical,pd.read_csv('reports/ai_pilot_v1/calendar.csv'))
        windows.to_csv(root/'audited_event_windows.csv',index=False)
    symbols=base['earnings']['symbols']+['SPY']
    paths=[source,Path('configs/timing_audit_v1.csv'),Path('configs/experiment_registry_v1.json'),config_path,Path(config['base_config'])]
    frames=[]
    for symbol in symbols:
        for start,end in [('2022-12-01','2026-02-01'),('2026-02-01','2026-11-01')]:
            path=Path('data/normalized/prices')/f'{symbol}_{start}_{end}_1d.csv'
            paths.append(path); frames.append(pd.read_csv(path))
    panel=pd.concat(frames).pivot(index='session_date',columns='symbol',values='adj_close')
    panel.index=pd.to_datetime(panel.index)
    sessions=calendar('2023-01-01','2026-10-31')
    sessions.to_csv(root/'calendar.csv',index=False)
    panel=panel.reindex(pd.to_datetime(sessions.session_date))
    if panel.isna().any().any():
        raise ValueError('Calendar price gaps; no filling allowed')
    hypotheses=[]; results=[]; trades=[]; exclusions=[]
    for fold,train,test in folds(panel,config):
        directory=root/fold['id']; directory.mkdir(exist_ok=True)
        fit=formation(train,base['pairs']['candidates'],fold['start'])
        fit['selected']=select(fit,base['pairs']); fit['fold']=fold['id']
        fit['formation_start']=str(train.index[0].date()); fit['evaluation_start']=str(test.index[0].date())
        hypotheses.append(fit)
        strategies={}
        pair_books=[]
        for _,candidate in fit.loc[fit.selected].iterrows():
            book,decisions=pair_targets(test,candidate,base['pairs'])
            name=f'pairs_{candidate.left}_{candidate.right}'
            strategies[name]=book; pair_books.append(book)
            decisions.to_csv(directory/f'{name}_decisions.csv',index=False)
        zero=pd.DataFrame(0.,index=test.index,columns=test.columns)
        strategies['pairs_portfolio']=sum(pair_books,zero.copy())/len(pair_books) if pair_books else zero.copy()
        # Audited earnings simulation remains flat for excluded records. Every
        # raw event receives a reason instead of silently disappearing.
        earnings=zero.copy()
        for symbol in base['earnings']['symbols']:
            raw_path=Path('data/raw/alpha_vantage')/f'{symbol}.json'; paths.append(raw_path)
            for event in json.loads(raw_path.read_text())['quarterlyEarnings']:
                day=pd.Timestamp(event['reportedDate'])
                if not pd.Timestamp(fold['start'])<=day<pd.Timestamp(fold['end']): continue
                reviewed=eligible.loc[(eligible.symbol==symbol)&eligible.reported_date.eq(event['reportedDate'])]
                reason='release_timing_not_independently_verified'
                if not reviewed.empty:
                    entry=int(test.index.searchsorted(day,side='right')); end=entry+base['earnings']['holding_sessions']
                    if end>=len(test): reason='holding_window_outside_fold'
                    else:
                        earnings.loc[test.index[entry:end],symbol]=-1/len(base['earnings']['symbols']); reason=None
                exclusions.append(dict(fold=fold['id'],symbol=symbol,reported_date=event['reportedDate'],exclusion=reason))
        strategies['audited_earnings']=earnings
        spy=zero.copy(); spy['SPY']=1.; spy.iloc[-1]=0
        strategies['SPY']=spy; strategies['cash']=zero
        for name,book in strategies.items():
            book.to_csv(directory/f'{name}_targets.csv')
            # Matched net-exposure SPY comparison for each strategy; passive SPY
            # and cash are also shown. Pairs may be beta-hedged, not dollar neutral.
            for bps in base['cost_bps_each_side']:
                ledger=account_v2(test,book,bps,base['borrow_annual'])
                ledger.to_csv(directory/f'{name}_{bps}bps.csv',index=False)
                summary=daily_metrics(ledger)
                summary['gross_compounded_return']=float((1+ledger.gross_return).prod()-1)
                summary['annualized_return']=float(ledger.equity.iloc[-1]**(365/max(1,(test.index[-1]-test.index[0]).days))-1)
                results.append(dict(fold=fold['id'],strategy=name,cost_bps=bps,**summary))
            for ticker in book.columns:
                position=book[ticker].ne(0)
                starts=position & ~position.shift(1,fill_value=False)
                trades.append(dict(fold=fold['id'],strategy=name,symbol=ticker,position_entries=int(starts.sum()),active_sessions=int(position.sum())))
            if name not in ('SPY','cash'):
                matched=zero.copy(); matched['SPY']=book.sum(axis=1)
                ledger=account_v2(test,matched,10,base['borrow_annual'])
                ledger.to_csv(directory/f'{name}_matched_net_SPY_10bps.csv',index=False)
                results.append(dict(fold=fold['id'],strategy=name+'_matched_net_SPY',cost_bps=10,**daily_metrics(ledger)))
    all_fits=pd.concat(hypotheses,ignore_index=True)
    all_fits['global_bh_diagnostic']=_bh(all_fits.p_value.tolist())
    all_fits.to_csv(root/'all_pair_hypotheses.csv',index=False)
    pd.DataFrame(exclusions).to_csv(root/'earnings_exclusions.csv',index=False)
    pd.DataFrame(trades).to_csv(root/'position_counts.csv',index=False)
    summary=pd.DataFrame(results); summary.to_csv(root/'evaluation.csv',index=False)
    limitations='Retrospective expanding walk-forward; no uninspected holdout remains. Fixed rules, no tuning. All unverified earnings excluded. Current-name universe has survivorship bias. Cointegration assumes integrated series; ADF non-rejection does not prove I(1). BH across four pairs per fold is the selection rule; all sixteen tests also reported with global BH diagnostic. Fold tests are dependent. No performance significance claims. Research shorts assume borrow availability at 5%; no actual locates. Daily adjusted-unit closing execution is approximate. Offline paper ledger is long-only pending borrow accounting.'
    lines=['# Completed research workflow v2','',limitations,'',f'Audited historical events: {len(audit)}; source-supported corrected sessions: {len(eligible)}; explicit exclusions: {int(audit.audit_exclusion.notna().sum())}.',
           f'Pair hypotheses: {len(all_fits)}; passing per-fold selection: {int(all_fits.selected.sum())}.','',
           'See audited_earnings.csv, earnings_exclusions.csv, all_pair_hypotheses.csv, position_counts.csv, and fold ledgers for complete diagnostics. Previous exploratory results remain unchanged. No trade is a valid outcome.','',
           summary.loc[(summary.cost_bps==10)&summary.strategy.isin(['pairs_portfolio','audited_earnings','SPY','cash'])].to_string(index=False)]
    (root/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    paths.extend(Path('src/quant_research').rglob('*.py'))
    paths.append(root/'calendar.csv')
    revision=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,check=False)
    versions={package:importlib.metadata.version(package) for package in ['pandas','numpy','scipy','statsmodels','exchange-calendars']}
    (root/'manifest.json').write_text(json.dumps({'config':config,'limitations':limitations,'package_versions':versions,
        'git_revision':revision.stdout.strip(),'working_tree_note':'Uncommitted implementation captured by source hashes; commit alone is insufficient',
        'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}},indent=2))
    print(f'Workflow complete: {len(all_fits)} pair tests, {int(all_fits.selected.sum())} selected; {len(eligible)}/{len(audit)} audited events eligible')


if __name__=='__main__':
    run()

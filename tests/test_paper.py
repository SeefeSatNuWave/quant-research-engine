from concurrent.futures import ThreadPoolExecutor
import pytest
from quant_research.paper import PaperLedger


def order(**changes):
    return dict(dict(order_id='one', symbol='ABC', quantity=10., price=100.,
                     signal_at='2026-01-02T14:29:00Z', quote_at='2026-01-02T14:30:00Z',
                     now='2026-01-02T14:31:00Z', data_version='fixture-v1', signal_version='test-v1'), **changes)


def test_atomic_idempotency_and_restart(tmp_path):
    path=tmp_path/'paper.db'
    ledger=PaperLedger(path)
    first=ledger.fill(**order())
    assert first['mode']=='SIMULATED'
    assert first['fill_price']==pytest.approx(100.075)
    assert ledger.fill(**order(now='2026-01-03T14:31:00Z'))==first
    with pytest.raises(ValueError, match='different'):
        ledger.fill(**order(quantity=20))
    ledger.close()
    ledger=PaperLedger(path)
    assert ledger.snapshot()['fill_count']==1
    assert ledger.snapshot()['cash']==first['cash_after']
    ledger.close()


@pytest.mark.parametrize('change,message', [
    ({'now':'2026-01-02T15:00:00Z'},'Stale'),
    ({'now':'2026-01-02T14:29:00Z'},'future'),
    ({'signal_at':'2026-01-02T14:30:00Z'},'signal'),
    ({'quantity':-1},'shorting'),
    ({'quantity':10000},'cash')])
def test_rejection_leaves_no_fill(tmp_path,change,message):
    ledger=PaperLedger(tmp_path/'paper.db')
    with pytest.raises(ValueError,match=message):
        ledger.fill(**order(**change))
    assert ledger.snapshot()['fill_count']==0
    assert ledger.snapshot()['cash']==100000
    ledger.close()


def test_kill_switch_and_cash_reconciliation(tmp_path):
    ledger=PaperLedger(tmp_path/'paper.db')
    buy=ledger.fill(**order())
    sell=ledger.fill(**order(order_id='two',quantity=-10,price=110))
    assert ledger.snapshot()['cash']==pytest.approx(100000-10*buy['fill_price']-buy['fee']+10*sell['fill_price']-sell['fee'])
    ledger.halt()
    with pytest.raises(ValueError,match='kill'):
        ledger.fill(**order(order_id='three'))
    ledger.close()


def test_concurrent_duplicate_fills_once(tmp_path):
    path=tmp_path/'paper.db'
    PaperLedger(path).close()
    def worker(_):
        ledger=PaperLedger(path)
        try:
            return ledger.fill(**order())
        finally:
            ledger.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(worker,range(2)))
    assert results[0]==results[1]
    ledger=PaperLedger(path)
    assert ledger.snapshot()['fill_count']==1
    ledger.close()


def test_no_backdated_fill_or_missing_timezone(tmp_path):
    ledger=PaperLedger(tmp_path/'paper.db')
    ledger.fill(**order())
    with pytest.raises(ValueError,match='precedes'):
        ledger.fill(**order(order_id='old',signal_at='2026-01-02T14:20:00Z',quote_at='2026-01-02T14:25:00Z',now='2026-01-02T14:26:00Z'))
    with pytest.raises(ValueError,match='timezone'):
        ledger.fill(**order(order_id='naive',signal_at='2026-01-02T14:29:00'))
    assert ledger.snapshot()['fill_count']==1
    ledger.close()

"""Offline-only SQLite simulated fills with atomic idempotency and validation."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must be timezone aware')
    return parsed.astimezone(timezone.utc)


class PaperLedger:
    """No network or broker integration. Prices must be supplied explicitly.

    This minimal ledger supports cash-funded long positions; short research
    remains in the backtest until a borrow/locate ledger is implemented.
    """

    def __init__(self, path: Path, initial_cash: float = 100_000):
        if not math.isfinite(initial_cash) or initial_cash <= 0:
            raise ValueError('Initial cash must be positive')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS account(id INTEGER PRIMARY KEY CHECK(id=1),
                initial_cash REAL NOT NULL, cash REAL NOT NULL, halted INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS positions(symbol TEXT PRIMARY KEY, quantity REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS fills(order_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
                record TEXT NOT NULL);
        ''')
        self.connection.execute('INSERT OR IGNORE INTO account(id,initial_cash,cash) VALUES(1,?,?)', (initial_cash, initial_cash))
        if self.connection.execute('SELECT initial_cash FROM account').fetchone()[0] != initial_cash:
            self.connection.close()
            raise ValueError('Existing ledger initial capital differs')

    def close(self) -> None:
        self.connection.close()

    def halt(self, value: bool = True) -> None:
        self.connection.execute('UPDATE account SET halted=? WHERE id=1', (int(value),))

    def snapshot(self) -> dict:
        cash, halted = self.connection.execute('SELECT cash,halted FROM account WHERE id=1').fetchone()
        return {'mode': 'SIMULATED', 'cash': cash, 'halted': bool(halted),
                'positions': dict(self.connection.execute('SELECT symbol,quantity FROM positions')),
                'fill_count': self.connection.execute('SELECT count(*) FROM fills').fetchone()[0]}

    def fill(self, *, order_id: str, symbol: str, quantity: float, price: float,
             signal_at: str, quote_at: str, now: str, data_version: str, signal_version: str,
             spread_bps: float = 5, slippage_bps: float = 5, fee_bps: float = 1,
             max_age_seconds: float = 300) -> dict:
        if not order_id or not data_version or not signal_version:
            raise ValueError('Order ID and data/signal versions required')
        if not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,9}', symbol):
            raise ValueError('Invalid symbol')
        values = [quantity, price, spread_bps, slippage_bps, fee_bps, max_age_seconds]
        if not all(math.isfinite(v) for v in values) or quantity == 0 or price <= 0:
            raise ValueError('Invalid numeric input')
        if min(spread_bps, slippage_bps, fee_bps, max_age_seconds) < 0:
            raise ValueError('Negative cost or freshness limit')
        # spread_bps is full bid/ask spread, so one fill pays half the spread.
        impact = (spread_bps/2 + slippage_bps)/10_000
        if impact >= 1 or fee_bps >= 10_000:
            raise ValueError('Invalid costs')
        signal, quote, clock = map(timestamp, [signal_at, quote_at, now])
        request = dict(symbol=symbol, quantity=quantity, price=price, signal_at=signal.isoformat(),
                       quote_at=quote.isoformat(), data_version=data_version, signal_version=signal_version,
                       spread_bps=spread_bps, slippage_bps=slippage_bps, fee_bps=fee_bps,
                       max_age_seconds=max_age_seconds)
        fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        db = self.connection
        db.execute('BEGIN IMMEDIATE')
        try:
            existing = db.execute('SELECT fingerprint,record FROM fills WHERE order_id=?', (order_id,)).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise ValueError('Order ID reused with different content')
                db.execute('COMMIT')
                return json.loads(existing[1])
            cash, halted = db.execute('SELECT cash,halted FROM account WHERE id=1').fetchone()
            if halted:
                raise ValueError('Paper kill switch is active')
            if not signal < quote <= clock:
                raise ValueError('Require signal before quote and no future quote')
            if (clock-quote).total_seconds() > max_age_seconds:
                raise ValueError('Stale quote')
            latest = db.execute('SELECT record FROM fills ORDER BY rowid DESC LIMIT 1').fetchone()
            if latest and quote < timestamp(json.loads(latest[0])['filled_at']):
                raise ValueError('Fill precedes existing ledger history')
            previous = db.execute('SELECT quantity FROM positions WHERE symbol=?', (symbol,)).fetchone()
            position = (previous[0] if previous else 0.) + quantity
            if position < -1e-9:
                raise ValueError('Paper shorting unavailable: no borrow ledger')
            fill_price = price*(1+impact if quantity > 0 else 1-impact)
            fee = abs(quantity)*fill_price*fee_bps/10_000
            cash_after = cash-quantity*fill_price-fee
            if cash_after < 0:
                raise ValueError('Insufficient simulated cash')
            record = dict(mode='SIMULATED', order_id=order_id, **request,
                          filled_at=quote.isoformat(), recorded_at=clock.isoformat(),
                          fill_price=fill_price, fee=fee, cash_after=cash_after, position_after=position)
            db.execute('UPDATE account SET cash=? WHERE id=1', (cash_after,))
            db.execute('INSERT INTO positions VALUES(?,?) ON CONFLICT(symbol) DO UPDATE SET quantity=excluded.quantity', (symbol, position))
            db.execute('INSERT INTO fills VALUES(?,?,?)', (order_id, fingerprint, json.dumps(record, sort_keys=True)))
            db.execute('COMMIT')
            return record
        except Exception:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise

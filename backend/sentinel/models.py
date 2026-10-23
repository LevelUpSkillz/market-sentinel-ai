from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import time
from math import isfinite

D = Decimal

def decimal(value) -> Decimal:
    try:
        out = D(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Invalid decimal') from None
    if not out.is_finite():
        raise ValueError('Non-finite market number')
    return out

def timestamp(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        n = float(value)
        if not isfinite(n):raise ValueError('Non-finite source timestamp')
        return n / 1000 if n > 1e11 else n
    parsed=datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:raise ValueError('Source timestamp must specify a timezone')
    return parsed.astimezone(timezone.utc).timestamp()

@dataclass
class Book:
    provider: str
    symbol: str
    instrument: str = 'spot'
    quote: str = 'USD'
    bids: dict[Decimal, Decimal] = field(default_factory=dict)
    asks: dict[Decimal, Decimal] = field(default_factory=dict)
    source_at: float | None = None
    received_at: float = 0
    valid: bool = False
    integrity: str = 'awaiting_snapshot'

    def update(self, bids, asks, source_at, received_at=None, snapshot=False, depth=None):
        received_at = time.time() if received_at is None else received_at
        if not snapshot and not self.valid:
            raise ValueError('Update before snapshot')
        if source_at is not None and self.source_at is not None and not snapshot and source_at < self.source_at:
            self.valid = False
            raise ValueError('Out-of-order book update')
        if snapshot:
            self.bids.clear()
            self.asks.clear()
        for target, levels in [(self.bids, bids), (self.asks, asks)]:
            for p, q in levels:
                p, q = decimal(p), decimal(q)
                if p <= 0 or q < 0:
                    self.valid = False
                    raise ValueError('Invalid order-book level')
                if q == 0:
                    target.pop(p, None)
                else:
                    target[p] = q
        if depth:
            self.bids = dict(sorted(self.bids.items(), reverse=True)[:depth])
            self.asks = dict(sorted(self.asks.items())[:depth])
        self.source_at, self.received_at = source_at, received_at
        self.valid = bool(self.bids and self.asks and max(self.bids) < min(self.asks))
        self.integrity = 'ordered_stream' if self.valid else 'invalid_book'
        if not self.valid:
            raise ValueError('Empty or crossed book')

    def fresh(self, now=None, max_age=5):
        now = time.time() if now is None else now
        return (self.valid and self.source_at is not None and
                -1 <= now - self.source_at <= max_age and 0 <= now - self.received_at <= max_age)

    def levels(self, side, depth=10):
        return sorted((self.asks if side == 'buy' else self.bids).items(), reverse=side != 'buy')[:depth]

    def fill(self, side, quantity):
        quantity = decimal(quantity)
        if quantity <= 0 or not self.valid:
            raise ValueError('Invalid fill request')
        left, cost = quantity, D(0)
        for price, available in self.levels(side, 100000):
            take = min(left, available)
            cost += take * price
            left -= take
            if left == 0:
                return cost / quantity
        raise ValueError('Insufficient visible liquidity')

    def view(self, now=None):
        now = time.time() if now is None else now
        bid = max(self.bids) if self.bids else None
        ask = min(self.asks) if self.asks else None
        bq = sum((p*q for p,q in self.levels('sell')), D(0))
        aq = sum((p*q for p,q in self.levels('buy')), D(0))
        return {'provider':self.provider,'symbol':self.symbol,'instrument':self.instrument,'quote':self.quote,
                'bid':str(bid) if bid else None,'ask':str(ask) if ask else None,
                'mid':str((ask+bid)/2) if ask and bid else None,
                'spread_bps':str((ask-bid)/((ask+bid)/2)*10000) if ask and bid else None,
                'imbalance':str((bq-aq)/(bq+aq)) if bq+aq else None,
                'visible_depth_usd':str(bq+aq),'source_at':self.source_at,'received_at':self.received_at,
                'age_seconds':max(0,now-self.source_at) if self.source_at else None,
                'status':'live' if self.fresh(now) else 'stale' if self.received_at else 'unavailable',
                'integrity':self.integrity,'bids':[[str(p),str(q)] for p,q in self.levels('sell')],
                'asks':[[str(p),str(q)] for p,q in self.levels('buy')]}

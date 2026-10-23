"""Public WebSocket adapters. No exchange order endpoints are implemented."""
from decimal import Decimal as D
import zlib
from .models import Book, decimal, timestamp

class Adapter:
    name = ''
    url = ''
    def __init__(self):
        self.books = {}
    def book(self,symbol,instrument='spot',quote='USD'):
        if symbol not in self.books:
            self.books[symbol] = Book(self.name,symbol,instrument,quote)
        return self.books[symbol]
    def invalidate(self):
        for b in self.books.values():
            b.valid = False
            b.integrity = 'disconnected'

class Kraken(Adapter):
    name, url = 'kraken','wss://ws.kraken.com/v2'
    def subscriptions(self):
        return [{'method':'subscribe','params':{'channel':c,'symbol':['BTC/USD','ETH/USD','SOL/USD'],**({'depth':10} if c=='book' else {})}} for c in ['book','ticker','trade']]
    @staticmethod
    def checksum(book):
        def fmt(value):
            return format(value,'f').replace('.','').lstrip('0')
        parts = [fmt(p)+fmt(q) for side in ['buy','sell'] for p,q in book.levels(side)]
        return zlib.crc32(''.join(parts).encode()) & 0xffffffff
    def consume(self,m,received_at):
        if m.get('success') is False or m.get('error'):
            raise ValueError('Kraken subscription rejected')
        events = []
        channel = m.get('channel')
        for row in m.get('data',[]) if isinstance(m.get('data'),list) else []:
            symbol = row.get('symbol','').replace('/','-')
            if channel=='book':
                b = self.book(symbol)
                b.update([(x['price'],x['qty']) for x in row.get('bids',[])],
                         [(x['price'],x['qty']) for x in row.get('asks',[])],timestamp(row.get('timestamp')),
                         received_at,snapshot=m.get('type')=='snapshot',depth=10)
                if 'checksum' not in row or self.checksum(b) != int(row['checksum']):
                    b.valid = False
                    b.integrity = 'checksum_failed'
                    raise ValueError('Kraken checksum mismatch; fresh snapshot required')
                b.integrity = 'crc32_verified'
                events.append(('book',b))
            elif channel=='trade' and m.get('type')!='snapshot':
                events.append(('trade',{'provider':self.name,'symbol':symbol,'price':str(decimal(row['price'])),
                    'quantity':str(decimal(row['qty'])),'source_at':timestamp(row['timestamp']),
                    'received_at':received_at,'side':row['side'],'trade_id':str(row['trade_id'])}))
            elif channel=='ticker':
                events.append(('ticker',{'provider':self.name,'symbol':symbol,'source_at':timestamp(row.get('timestamp')),
                    'received_at':received_at,'last':str(row.get('last')),'note':'Ticker receipt does not refresh the book.'}))
        return events

class Coinbase(Adapter):
    name,url = 'coinbase','wss://ws-feed.exchange.coinbase.com'
    def subscriptions(self):
        return [{'type':'subscribe','product_ids':['BTC-USD','ETH-USD','SOL-USD'],'channels':['level2_batch','ticker','matches','heartbeat']}]
    def consume(self,m,received_at):
        kind = m.get('type')
        if kind=='error':
            raise ValueError('Coinbase subscription rejected')
        symbol = m.get('product_id')
        if not symbol:
            return []
        if kind in ['snapshot','l2update']:
            b = self.book(symbol)
            if kind=='snapshot':
                bids,asks = m['bids'],m['asks']
            else:
                bids = [(p,q) for side,p,q in m['changes'] if side=='buy']
                asks = [(p,q) for side,p,q in m['changes'] if side=='sell']
            b.update(bids,asks,timestamp(m.get('time')),received_at,snapshot=kind=='snapshot')
            return [('book',b)]
        if kind=='match':
            return [('trade',{'provider':self.name,'symbol':symbol,'price':str(decimal(m['price'])),
                'quantity':str(decimal(m['size'])),'source_at':timestamp(m['time']),'received_at':received_at,
                'side':'buy' if m['side']=='sell' else 'sell','trade_id':str(m['trade_id'])})]
        if kind=='ticker':
            return [('ticker',{'provider':self.name,'symbol':symbol,'source_at':timestamp(m.get('time')),
                'received_at':received_at,'last':str(m.get('price'))})]
        return []

class Hyperliquid(Adapter):
    name,url = 'hyperliquid','wss://api.hyperliquid.xyz/ws'
    def subscriptions(self):
        return [{'method':'subscribe','subscription':{'type':kind,'coin':coin}} for coin in ['BTC','ETH','SOL'] for kind in ['l2Book','trades','activeAssetCtx']]
    def consume(self,m,received_at):
        channel,data = m.get('channel'),m.get('data')
        if channel=='error':
            raise ValueError('Hyperliquid subscription rejected')
        if channel=='l2Book':
            b = self.book(data['coin']+'-USDC-PERP','perpetual','USDC')
            b.update([(r['px'],r['sz']) for r in data['levels'][0]],[(r['px'],r['sz']) for r in data['levels'][1]],timestamp(data['time']),received_at,snapshot=True)
            return [('book',b)]
        if channel=='trades':
            return [('trade',{'provider':self.name,'symbol':r['coin']+'-USDC-PERP','price':str(decimal(r['px'])),
                'quantity':str(decimal(r['sz'])),'source_at':timestamp(r['time']),'received_at':received_at,
                'side':'buy' if r['side']=='B' else 'sell','trade_id':str(r.get('tid',r.get('hash'))),
                'public_participants':r.get('users',[])}) for r in data]
        if channel=='activeAssetCtx':
            return [('funding',{'provider':self.name,'symbol':data['coin']+'-USDC-PERP',
                'received_at':received_at,'source_at':None,'funding':str(decimal(data['ctx']['funding'])) if data['ctx'].get('funding') is not None else None,
                'open_interest':str(decimal(data['ctx']['openInterest'])) if data['ctx'].get('openInterest') is not None else None,
                'mark_price':str(decimal(data['ctx']['markPx'])) if data['ctx'].get('markPx') is not None else None,
                'day_notional_volume':str(decimal(data['ctx']['dayNtlVlm'])) if data['ctx'].get('dayNtlVlm') is not None else None,
                'oracle_price':str(decimal(data['ctx']['oraclePx'])) if data['ctx'].get('oraclePx') is not None else None,
                'note':'Context has no event timestamp; receipt-time only. OI is in base units; volume and mark/oracle are USDC-denominated.'})]
        return []

ADAPTERS = {c.name:c for c in [Kraken,Coinbase,Hyperliquid]}

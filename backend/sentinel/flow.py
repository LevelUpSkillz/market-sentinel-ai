"""Causal anomalies from observed public trades; no gap filling or invented volume."""
from collections import OrderedDict
from decimal import Decimal as D
from .models import decimal

class FlowDetector:
    def __init__(self):
        self.buckets={}
        self.seen=OrderedDict()
        self.last_emitted={}
    def reset(self,provider):
        for key in list(self.buckets):
            if key[0]==provider:del self.buckets[key]
    def observe(self,trade):
        source,received=trade.get('source_at'),trade['received_at']
        if source is None or not -1<=received-source<=10:return
        identity=(trade['provider'],trade['symbol'],trade['trade_id'])
        if identity in self.seen:return
        self.seen[identity]=True
        if len(self.seen)>50000:self.seen.popitem(last=False)
        price,quantity=decimal(trade['price']),decimal(trade['quantity'])
        if price<=0 or quantity<=0:return
        key=(trade['provider'],trade['symbol'])
        index=int(source//30)
        bins=self.buckets.setdefault(key,{})
        row=bins.setdefault(index,{'notional':D(0),'buy':D(0),'sell':D(0),'count':0,'first':price,'last':price,'first_at':source,'last_at':source})
        row['notional']+=price*quantity
        row[trade['side']]+=price*quantity
        row['count']+=1
        if source<row['first_at']:row.update(first=price,first_at=source)
        if source>=row['last_at']:row.update(last=price,last_at=source)
        for old in list(bins):
            if old<index-14:del bins[old]
    def anomalies(self,now):
        completed=int(now//30)-1
        out=[]
        for key,bins in self.buckets.items():
            if self.last_emitted.get(key)==completed:continue
            prior=[bins.get(i) for i in range(completed-10,completed)]
            current=bins.get(completed)
            if current is None or any(row is None for row in prior):continue
            baseline=sum((r['notional'] for r in prior),D(0))/10
            if baseline<=0 or current['count']<10:continue
            facts=[]
            ratio=current['notional']/baseline
            if ratio>=4:facts.append(f'Observed 30-second trade notional was {ratio:.2f} times the mean of ten prior complete observed windows.')
            change=(current['last']/current['first']-1)*10000
            delta=(current['buy']-current['sell'])/current['notional']
            if abs(change)>50 and change*delta<0:
                facts.append(f'Observed price changed {change:.2f} bps while aggressive-flow imbalance was {delta:.3f}, in the opposite direction.')
            if facts:
                self.last_emitted[key]=completed
                out.append({'provider':key[0],'symbol':key[1],'facts':facts,'window_start':completed*30,
                    'window_end':(completed+1)*30,'baseline_windows':10,'trade_count':current['count'],
                    'observed_notional':str(current['notional']),'volume_ratio':str(ratio),
                    'price_change_bps':str(change),'source_at':current['last_at'],'received_at':now,
                    'note':'Observed public feed sample; missing windows are unknown. No manipulation or profitability conclusion.'})
        return out

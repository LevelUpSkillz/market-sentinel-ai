"""Expanding-window validation of a fixed long/cash momentum family on supplied bars."""
from math import sqrt
from statistics import mean, pstdev
from .models import decimal

def validate_bars(bars):
    if not 120 <= len(bars) <= 5000:
        raise ValueError('Provide 120–5000 chronological bars')
    times = [float(b['timestamp']) for b in bars]
    prices = [float(decimal(b['close'])) for b in bars]
    if any(p<=0 for p in prices) or any(t!=t or abs(t)==float('inf') for t in times):
        raise ValueError('Bars contain invalid prices or timestamps')
    if any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Timestamps must be unique and strictly increasing')
    intervals = [b-a for a,b in zip(times,times[1:])]
    if max(intervals)-min(intervals)>0.001:
        raise ValueError('Use regularly spaced bars; gaps must be resolved explicitly')
    return prices

def replay(prices,start,end,lookback,fee_bps=60,slippage_bps=5,latency_bars=1):
    if start < lookback+latency_bars+1 or end>len(prices):
        raise ValueError('Insufficient causal warm-up')
    equity,position,trades = 1.0,0,0
    peak,drawdown = 1.0,0.0
    returns,curve = [],[]
    cost = (fee_bps+slippage_bps)/10000
    for t in range(start,end):
        # A signal at close t-latency-1 can affect only the subsequent return interval.
        observed = t-latency_bars-1
        desired = int(prices[observed]>prices[observed-lookback])
        before = equity
        if desired!=position:
            equity *= 1-cost
            trades += 1
        position = desired
        equity *= 1+position*(prices[t]/prices[t-1]-1)
        returns.append(equity/before-1)
        peak = max(peak,equity)
        drawdown = min(drawdown,equity/peak-1)
        curve.append({'bar':t,'equity':equity})
    if position:
        equity *= 1-cost
        trades += 1
        peak = max(peak,equity)
        drawdown = min(drawdown,equity/peak-1)
        curve[-1]['equity'] = equity
        returns[-1] = (1+returns[-1])*(1-cost)-1
    volatility = pstdev(returns) if len(returns)>1 else 0
    return {'return':equity-1,'max_drawdown':drawdown,'transactions':trades,
            'mean_return_volatility_ratio':mean(returns)/volatility if volatility else None,'curve':curve}

def walk_forward(bars,source,fee_bps=60,slippage_bps=5,latency_bars=1):
    prices = validate_bars(bars)
    if not source.strip() or len(source)>500:
        raise ValueError('State the historical data source and whether it is synthetic')
    if not 0<=fee_bps<=500 or not 0<=slippage_bps<=500 or latency_bars not in [0,1,2,3]:
        raise ValueError('Invalid execution assumptions')
    candidates = [3,6,12]
    gap = max(candidates)+latency_bars+1
    initial = len(prices)//2
    fold_size = max(20,len(prices)//6)
    folds = []
    for test_start in range(initial,len(prices),fold_size):
        train_end = test_start-gap
        train_scores = [(replay(prices,gap,train_end,k,fee_bps,slippage_bps,latency_bars)['return'],k) for k in candidates]
        chosen = max(train_scores)[1]
        end = min(test_start+fold_size,len(prices))
        result = replay(prices,test_start,end,chosen,fee_bps,slippage_bps,latency_bars)
        cost = (fee_bps+slippage_bps)/10000
        hold = prices[end-1]/prices[test_start-1]*(1-cost)**2-1
        sensitivity = {str(delay):replay(prices,test_start,end,chosen,fee_bps,slippage_bps,delay)['return'] for delay in [0,1,2,3]}
        folds.append({'training_end_exclusive':train_end,'embargo_bars':gap,'test_start':test_start,
            'test_end_exclusive':end,'selected_lookback':chosen,'selection':'training return only',
            'strategy':result,'buy_and_hold_return':hold,'no_trade_return':0,'latency_sensitivity':sensitivity})
    equity,hold = 1.0,1.0
    for f in folds:
        equity *= 1+f['strategy']['return']
        hold *= 1+f['buy_and_hold_return']
    return {'strategy_version':'momentum-lab-v1','source':source,'data_label':'USER-SUPPLIED HISTORICAL DATA — provenance not independently verified',
        'fee_bps_per_transaction':fee_bps,'slippage_bps_per_transaction':slippage_bps,'latency_bars':latency_bars,
        'folds':folds,'out_of_sample_return':equity-1,'buy_and_hold_return':hold-1,'no_trade_return':0,
        'limitations':['Results are hypothetical; close-based fills do not model intrabar liquidity.',
                      'Each fold liquidates at its end, including the hold benchmark; returns compound across folds.',
                      'Training selection over three fixed candidates is subject to multiple-testing bias.',
                      'No statistical significance or profitability claim. No automatic live strategy promotion.']}

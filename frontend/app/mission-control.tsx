'use client';

import type {Dashboard, Market} from './types';

export function bookFresh(market:Market, online:boolean, now:number) {
  return online && market.status==='live' && market.source_at!=null &&
    now-market.source_at>=-1 && now-market.source_at<=5 &&
    now-market.received_at>=0 && now-market.received_at<=5 &&
    ['crc32_verified','ordered_stream'].includes(market.integrity);
}
const at=(time:number)=>new Date(time*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
const price=(value:string)=>Number(value).toLocaleString('en-US',{maximumSignificantDigits:8});

export function FeedStatus({data,online,now}:{data:Dashboard|null;online:boolean;now:number}) {
  return <section className="feed-status" aria-label="Provider connections">
    <div className="feed-status-title"><span className="eyebrow">DATA CONNECTIONS</span><span>Exchange feeds are separate from the app connection.</span></div>
    <div className="feed-status-grid">{['kraken','hyperliquid','coinbase'].map(provider=>{
      const connection=data?.providers[provider];
      const books=data?.markets.filter(m=>m.provider===provider)||[];
      const fresh=books.filter(m=>bookFresh(m,online,now)).length;
      const state=!data?'unavailable':!online?'disconnected':connection?.state==='connected'?fresh?'fresh':books.some(m=>m.received_at>0)?'old':'unavailable':connection?.state==='disabled'?'unavailable':connection?'disconnected':'unavailable';
      const label={fresh:'Fresh data',old:'Old data',disconnected:'Disconnected',unavailable:'Unavailable'}[state];
      const latest=Math.max(0,...books.map(m=>m.source_at||0));
      return <details key={provider} className={'feed-chip '+state}><summary><span className="feed-light"/><strong>{provider==='kraken'?'Kraken':provider==='hyperliquid'?'Hyperliquid':'Coinbase'}</strong><span>{label}</span><span aria-hidden="true">⌄</span></summary><p>{state==='fresh'?fresh+' detailed books passed source-time and integrity checks.':state==='old'?'The connection exists, but detailed prices need a fresh observation.':connection?.reason||'No verified detailed price is available from this source.'}</p><small>Last source event: {latest?at(latest):'unavailable'}. Fresh means source and receipt ages of five seconds or less.</small></details>;
    })}</div>
  </section>;
}

export function MissionObservations({data,online,now,onIdeas}:{data:Dashboard|null;online:boolean;now:number;onIdeas:()=>void}) {
  const signals=data?.signals||[];
  const usable=(s:Dashboard['signals'][number])=>online&&s.snapshots.length>0&&s.snapshots.every(m=>bookFresh(m,online,now));
  const ready=signals.filter(s=>usable(s)&&s.decision==='GO').length;
  const waiting=signals.filter(s=>usable(s)&&s.decision==='WAIT').length;
  const skipped=signals.length-ready-waiting;
  const trades=(data?.trades||[]).filter(t=>Number.isFinite(t.source_at)&&t.source_at<=now+1&&Number(t.price)>0&&Number(t.quantity)>0).slice().sort((a,b)=>b.source_at-a.source_at).slice(0,4);
  return <div className="mission-observations">
    <section className="panel observation-radar" aria-label="Observed opportunity summary"><div className="panel-head"><div><span className="eyebrow">OPPORTUNITY RADAR</span><h2>Evidence before entry</h2></div><span className="badge research">Practice research</span></div><div className="observation-radar-body"><div className="evidence-orbit" aria-hidden="true"><span/><span/><i/><strong>{data?signals.length:'—'}<small>recorded ideas</small></strong></div><dl><div><dt><span className="feed-light fresh"/>Practice checks passed</dt><dd>{data?ready:'—'}</dd></div><div><dt><span className="feed-light old"/>Waiting for conditions</dt><dd>{data?waiting:'—'}</dd></div><div><dt><span className="feed-light disconnected"/>Skip or refresh evidence</dt><dd>{data?skipped:'—'}</dd></div></dl></div><div className="panel-foot"><span>{signals.length?'Current recorded cross-exchange checks. Passing risk checks does not establish a profitable strategy.':'No cross-exchange ideas recorded. Trade Ideas also checks observed spot activity.'}</span><button className="text-button" onClick={onIdeas}>Explore Trade Ideas →</button></div></section>
    <section className="panel market-activity" aria-label="Recorded market activity"><div className="panel-head"><div><span className="eyebrow">MARKET ACTIVITY</span><h2>Latest observed trades</h2></div><span className={'badge '+(online?'research':'stale')}>{online?'Recorded prints':'Feed disconnected'}</span></div>{trades.length?<div className="activity-list">{trades.map((trade,i)=><article key={trade.provider+trade.symbol+trade.source_at+i}><div><strong>{trade.symbol}</strong><small>{trade.provider} · {trade.side||'side unavailable'}</small></div><div><strong>{price(trade.price)}</strong><small>{price(trade.quantity)} units</small></div><div><time dateTime={new Date(trade.source_at*1000).toISOString()}>{at(trade.source_at)}</time><small>{online&&now-trade.source_at<=10?'Recent observation':'Old observation'}</small></div></article>)}</div>:<div className="empty"><h3>No trade prints available</h3><p>Only actual provider trades appear here. A changing quote is not a completed trade.</p></div>}<div className="panel-foot">Prices use each market’s own quote currency. Records describe trades already observed.</div></section>
  </div>;
}

const HELP:Record<number,{title:string;text:string}>={
  0:{title:'How to read this workspace',text:'Start with the chart. Open Trade Ideas to see conditions and costs, then test a plan with practice money. Live Money is a separate workspace for your own Kraken account.'},
  1:{title:'How prices and charts work',text:'A chart uses actual exchange candles or verified book observations. The price line shows closes; candles show the open, high, low and close. Volume counts traded units. Use + and − to zoom, drag across the chart to inspect, or use arrow keys. Old or disconnected data is for reference only.'},
  4:{title:'What an idea lets you do',text:'Watch means wait for the listed conditions. Practice ready means modeled risk checks passed for a virtual-money experiment. Skip means a condition failed or evidence is old. Checking a plan places no trade. A percentage describing a trader’s past history is not a forecast of your success.'},
  2:{title:'What public trader evidence means',text:'Big Traders shows anonymous public accounts and the actions the app observed. A position snapshot does not prove a new trade, real identity or future profit. Public perpetual positions differ from Kraken spot trades. Inspect the timestamps and available history before drawing a conclusion.'},
  10:{title:'What happens before a real order',text:'Connecting reads your own account. Setting a budget records your limits. Validate and review checks one exact spot order without placing it. Only the separate final approval can send that reviewed order. A planned stop is not a protective order. Unknown submissions stay blocked until reconciliation.'},
  7:{title:'Practice money explained',text:'Practice buys and closes change only the simulated account. The app models visible liquidity and fees; it never sends these trades to an exchange. The emergency stop also blocks new real orders. Existing exchange orders must be managed directly in Kraken.'}
};
export function ContextHelp({screen}:{screen:number}) {
  const help=HELP[screen];
  return help?<details className="context-help"><summary>{help.title}<span>Quick explanation ⌄</span></summary><p>{help.text}</p></details>:null;
}

'use client';
import { useState } from 'react';
import type { Intelligence, Trader, JournalRecord, Dashboard } from './types';

const n=(value:unknown,digits=2)=>value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumFractionDigits:digits});
const date=(value?:number|null)=>value?new Date(value*1000).toLocaleString():'unavailable';
const usdc=(value:unknown)=>n(value)+' USDC';
const quotePrice=(value:unknown)=>value==null||!Number.isFinite(Number(value))?'Unavailable':Number(value).toLocaleString('en-US',{maximumSignificantDigits:9})+' USDC';
const assetNames:Record<string,string>={BTC:'Bitcoin',ETH:'Ethereum',SOL:'Solana',HYPE:'Hyperliquid',DOGE:'Dogecoin',XRP:'XRP',AVAX:'Avalanche',LINK:'Chainlink',LTC:'Litecoin',SUI:'Sui',AAVE:'Aave',BNB:'BNB'};
const assetName=(symbol:string)=>{const token=symbol.replace(/-USDC-PERP$/,'');return assetNames[token]&&assetNames[token]!==token?assetNames[token]+' ('+token+')':token};
const shortAddress=(address:string)=>address.slice(0,8)+'…'+address.slice(-6);

function PublicWalletAddress({address}:{address:string}) {
  const [copyStatus,setCopyStatus]=useState<'idle'|'copied'|'failed'>('idle');
  async function copyAddress() {
    try {await navigator.clipboard.writeText(address);setCopyStatus('copied')}
    catch {setCopyStatus('failed')}
  }
  return <><code title={address}>{address}</code><button type="button" className="secondary" onClick={copyAddress}>Copy public wallet address</button><small role="status">{copyStatus==='copied'?'Public wallet address copied.':copyStatus==='failed'?'Copy unavailable. Select the full address above to copy it.':''}</small></>;
}

export function ActionBriefing({intel,online,now,onInspectWallet}:{intel:Intelligence|null;online:boolean;now:number;onInspectWallet?:(address:string)=>void}) {
  return <section className="panel" aria-label="Next action briefing"><div className="panel-head"><div><span className="eyebrow">PUBLIC TRADERS · INDEPENDENT REVIEW</span><h2>Your next action briefing</h2></div></div>
    <div className="wallet-details"><p>Observed large-trader positions inform research. An entry requires your own risk plan; another wallet’s trade is not an instruction.</p></div>
    {intel?.actions.length?intel.actions.slice(0,6).map(a=>{
      const positionFresh=online&&Number.isFinite(a.received_at)&&now-a.received_at>=0&&now-a.received_at<=90;
      const marketFresh=online&&a.market_received_at!=null&&a.market_source_at!=null&&Number.isFinite(a.market_received_at)&&Number.isFinite(a.market_source_at)&&now-a.market_received_at>=0&&now-a.market_received_at<=5&&now-a.market_source_at>=0&&now-a.market_source_at<=5;
      const fresh=positionFresh&&marketFresh;
      const odds=a.follow_evidence;
      const validated=fresh&&odds.estimated_success_pct!=null&&Number.isFinite(odds.estimated_success_pct)&&odds.estimated_success_pct>=0&&odds.estimated_success_pct<=100;
      const interval=validated&&odds.interval_95_pct&&odds.interval_95_pct.every(x=>Number.isFinite(x)&&x>=0&&x<=100)&&odds.interval_95_pct[0]<=odds.interval_95_pct[1]?odds.interval_95_pct:null;
      const entryDifference=a.entry_drift_bps==null?null:Number(a.entry_drift_bps);
      const hasEntryDifference=fresh&&entryDifference!=null&&Number.isFinite(entryDifference);
      const hasComparisonPrices=a.reported_average_entry_price!==undefined||a.current_executable_price!==undefined;
      const positionSize=Math.abs(Number(a.position_size_native_units));
      const nextStep=!fresh?'Wait for fresh market observations':a.decision==='NO-GO'?'Skip this observed entry':'Research only — no validated trade recommendation';
      return <article className="action-card" key={a.address+a.symbol}>
        <div className="action-heading"><div><span className="eyebrow">PUBLIC POSITION OBSERVATION</span><h3>{assetName(a.symbol)}</h3></div><span className={'badge '+(fresh&&a.decision==='WAIT'?'wait':'no-go')}>{fresh?a.decision:'NO-GO'}</span></div>
        <p>Public wallet holds a position for a {a.side==='long'?'price rise (long)':a.side==='short'?'price fall (short)':'direction that has not been verified'}.</p>
        {Number.isFinite(positionSize)&&positionSize>0&&<p>Observed position size: {positionSize.toLocaleString('en-US',{maximumSignificantDigits:9})} {a.asset||a.symbol.replace(/-USDC-PERP$/,'')}. This snapshot does not establish the size of an individual execution.</p>}
        <button type="button" className="secondary" disabled={!onInspectWallet} onClick={()=>onInspectWallet?.(a.address)}>View this wallet’s actions</button>
        <p>Perpetual contract · USDC · not a Kraken spot order.</p>
        <p>{a.timing_note||'Current public position snapshot; an opening or exact execution time is not established.'}</p>
        <h4>{nextStep}</h4>
        {fresh&&<p>{a.next_action}</p>}
        {!positionFresh?<p>The position observation is unavailable or older than 90 seconds. Refresh the evidence before assessing an entry.</p>:!marketFresh&&<p>A current matching market quote is unavailable or older than five seconds. Refresh the evidence before assessing an entry.</p>}
        {fresh&&a.decision_cause==='nearby_liquidation'&&hasEntryDifference&&entryDifference!<0&&<p>A more favorable entry price does not remove the nearby liquidation risk.</p>}
        {a.reasons.map(r=><p key={r}>{r}</p>)}
        {hasComparisonPrices&&<div className="evidence-metrics"><div><small>Wallet’s reported average entry</small><strong>{a.reported_average_entry_price==null?'Unavailable':quotePrice(a.reported_average_entry_price)}</strong></div><div><small>Current market quote (before costs)</small><strong>{fresh&&a.current_executable_price!=null?quotePrice(a.current_executable_price):'Unavailable'}</strong><small>Visible best bid or ask; fees, size and fill risk apply.</small><small>Quote receipt: {date(a.market_received_at)}</small></div></div>}
        <div className="evidence-metrics"><div><small>Success odds · next hour</small><strong>{validated?n(odds.estimated_success_pct,1)+'%':fresh?'Not validated':'Unavailable'}</strong></div><div><small>Learning progress</small><strong>{odds.completed} of {odds.minimum_sample} minimum completed</strong>{!validated&&<small>Sample threshold alone is insufficient.</small>}</div>{interval&&<div><small>95% outcome interval</small><strong>{interval.map(x=>n(x,1)+'%').join(' – ')}</strong></div>}<div><small>Entry compared with wallet</small><strong>{hasEntryDifference?n(Math.abs(entryDifference!)/100,4)+'%':'Unavailable'}</strong><small>{hasEntryDifference?entryDifference!<0?'Favorable versus the observed average entry':entryDifference!>0?'Adverse versus the observed average entry':'Unchanged versus the observed average entry':'A matching executable price is required.'}</small></div></div>
        <details><summary>How the success estimate is validated</summary><p>{odds.meaning}</p><p>Historical shadow success: {odds.historical_success_pct==null?'unavailable':n(odds.historical_success_pct,1)+'%'} · missing outcomes: {odds.missing} · pending: {odds.pending} · held-out predictions: {odds.held_out_predictions}</p>{odds.reasons.map(r=><p key={r}>{r}</p>)}{odds.limitations.map(r=><p key={r}>{r}</p>)}</details>
        <small>Position observation: {positionFresh?'recent':'unavailable or stale'} · received {date(a.received_at)}</small>
        <details><summary>Source and wallet details · {shortAddress(a.address)}</summary><p>Public address, not a verified identity:</p><PublicWalletAddress address={a.address}/><p>Instrument: {a.symbol}</p><p>Source: {a.source}</p><p>Position received: {date(a.received_at)}</p><p>Position source time: {date(a.source_at)}</p>{hasComparisonPrices&&<p>Market quote received: {date(a.market_received_at)} · source time: {date(a.market_source_at)}</p>}{hasEntryDifference&&<p>Direction-adjusted entry difference: {n(entryDifference,2)} bps. A positive difference is a worse entry for the observed direction; a negative difference is more favorable. This comparison does not establish a profitable trade.</p>}</details>
      </article>
    }):<div className="empty-state"><h3>Waiting for public large-trader observations</h3><p>The collector discovers wallets from actual Hyperliquid prints of at least 100,000 USDC, then retrieves positions and available history. No successful traders or odds are invented.</p></div>}
    <div className="panel-foot">Research and paper review only. A high historical win rate does not establish positive expected profit or a follower’s probability of success.</div>
  </section>;
}

export default function SmartMoneyView({traders,events,intel,online,now,auth,busy,onAdd,onInspectWallet,readOnly=false}:{readOnly?:boolean;traders:Trader[];events:JournalRecord[];intel:Intelligence|null;online:boolean;now:number;auth:boolean;busy:boolean;onAdd:(address:string,label:string)=>Promise<void>;onInspectWallet?:(address:string)=>void}) {
  const [address,setAddress]=useState(''),[label,setLabel]=useState('');
  return <>
    <ActionBriefing intel={intel} online={online} now={now} onInspectWallet={onInspectWallet}/>
    <section className="panel"><div className="panel-head"><div><span className="eyebrow">AUTOMATIC DISCOVERY + YOUR WATCHLIST</span><h2>Investigate a public wallet</h2></div></div><div className="wallet-details"><p>Up to five wallets are discovered from genuine large public trade prints. Both buyer and seller are investigated; print size does not establish skill, wealth, identity or directional intent.</p></div>
      {!readOnly&&<form className="inline-form" onSubmit={async e=>{e.preventDefault();await onAdd(address,label||'Public wallet');setAddress('');setLabel('')}}><input aria-label="Public wallet address" placeholder="Public address · 0x…" value={address} onChange={e=>setAddress(e.target.value)} pattern="0x[0-9a-fA-F]{40}" required/><input aria-label="Wallet label" placeholder="Your label, not verified identity" maxLength={60} value={label} onChange={e=>setLabel(e.target.value)}/><button className="primary" disabled={!auth||busy}>Add public wallet</button></form>}
      <div className="panel-foot">Hyperliquid public data · ten wallets total · position rounds approximately 30 seconds at full capacity · available history refreshes every six hours · gaps possible on free hosting</div>
    </section>
    {traders.map(t=>{
      const h=t.history;
      const walletEvents=events.filter(r=>r.address?.toLowerCase()===t.address.toLowerCase()).slice(0,20);
      const fresh=online&&t.snapshot&&now-t.snapshot.received_at<90;
      return <section className="panel" key={t.id} id={'wallet-'+t.address} tabIndex={-1} aria-label={'Public wallet '+shortAddress(t.address)}>
        <div className="panel-head"><div><span className="eyebrow">{t.origin==='auto_large_trade'?'DISCOVERED LARGE-TRADE PARTICIPANT':'USER WATCHLIST'}</span><h2>{t.label}</h2></div><span className={'badge '+(fresh?'live':'unavailable')}>{fresh?'recent snapshot':t.snapshot?'stale':'awaiting data'}</span></div>
        <div className="wallet-details"><code>{t.address}</code><p>Observed account value: {usdc(t.snapshot?.account_value)} · identity and external hedges unknown.</p>{t.discovery&&<p>Discovery print: {usdc(t.discovery.observed_notional_usdc)} · {t.discovery.symbol} · participant was the {t.discovery.role_in_print} · {date(t.discovery.source_at)}</p>}<small>Positions source: {t.snapshot?.source||'Hyperliquid, awaiting data'} · received {date(t.snapshot?.received_at)} · source time {date(t.snapshot?.source_at)}</small>{t.error&&<p className="negative">Latest position request: {t.error.error} at {date(t.error.at)}</p>}</div>
        {t.snapshot?.positions.length?<div className="table-scroll"><table><thead><tr><th>Asset / direction</th><th>Observed position</th><th>Average entry</th><th>Unrealized P&L</th><th>Liquidation price</th></tr></thead><tbody>{t.snapshot.positions.map(p=><tr key={p.coin}><td>{p.coin} · {Number(p.szi)>0?'long':'short'}</td><td>{n(p.szi,6)}</td><td>{usdc(p.entryPx)}</td><td>{usdc(p.unrealizedPnl)}</td><td>{usdc(p.liquidationPx)}</td></tr>)}</tbody></table></div>:<div className="wallet-details"><p>{t.snapshot?'No current public positions returned.':'Waiting for the first provider snapshot; no position is assumed.'}</p></div>}
        <div className="history-section"><span className="eyebrow">ANALYSIS OF ACTUAL PAST ACTIONS · NATIVE PERPETUALS</span><h3>Historical completed-position record</h3>
        {h?<><div className="evidence-metrics"><div><small>Historical win rate · before funding</small><strong>{h.historical_win_rate_pct==null?'Unavailable':n(h.historical_win_rate_pct,1)+'%'}</strong><small>{h.complete_cycles} complete position cycles</small></div><div><small>Net P&L after trading fees · before funding</small><strong>{usdc(h.net_before_funding_usdc)}</strong></div><div><small>Realized P&L drawdown · not account drawdown</small><strong>{usdc(h.realized_pnl_drawdown_usdc)}</strong></div><div><small>Median holding time</small><strong>{h.median_holding_seconds==null?'—':n(h.median_holding_seconds/3600,2)+' hours'}</strong></div></div><p>{h.fills_analyzed} fills analyzed · {h.unclosed_cycles} unfinished cycles · {h.position_gaps} position gaps · {h.provider_limit_reached?'Provider’s 2,000-fill cap reached; history is truncated.':'Available provider window; lifetime completeness is not established.'}</p><small>Source: {h.source} · retrieved {date(h.received_at)} · observed fill range {date(h.first_fill_at)} → {date(h.last_fill_at)}</small>
          {h.cycles.length>0&&<div className="table-scroll"><table><thead><tr><th>Completed position</th><th>Closed</th><th>Trading fees</th><th>Net before funding</th></tr></thead><tbody>{h.cycles.slice(-6).reverse().map((c,i)=><tr key={i}><td>{c.coin} · {c.side}</td><td>{date(c.closed_at)}</td><td>{usdc(c.trading_fees_usdc)}</td><td>{usdc(c.net_before_funding_usdc)}</td></tr>)}</tbody></table></div>}
          {h.recent_fills?.length>0&&<><h3>Recent actual trader executions</h3><div className="table-scroll"><table><thead><tr><th>Provider action</th><th>Source time</th><th>Price / size</th><th>Closed P&L · before fees</th></tr></thead><tbody>{h.recent_fills.slice(-8).reverse().map((f,i)=><tr key={i}><td>{f.coin} · {f.action}</td><td>{date(f.source_at)}</td><td>{usdc(f.price)} / {n(f.quantity,6)}</td><td>{usdc(f.closed_pnl_before_fees_usdc)}</td></tr>)}</tbody></table></div><p>Executions can be partial fills. This list is not a count of completed trades or a follower backtest.</p></>}
          <details><summary>Historical evidence limits</summary>{h.limitations.map(r=><p key={r}>{r}</p>)}</details>
        </>:<p>Retrieving actual public fills. A win percentage will appear only if complete position cycles can be reconstructed.</p>}
        {t.history_error&&<p className="negative">History request unavailable: {t.history_error.error} at {date(t.history_error.at)}. Retained history is not refreshed by this error.</p>}
        </div>
        <div className="history-section"><h3>Observed position changes for this wallet</h3><p>Changes occurred between position polls; exact execution time is unknown. These are historical observations, not current entry approvals.</p>{walletEvents.length?walletEvents.map(r=><article key={r.id} className="journal-item"><span className="badge no-go">{r.analysis?.decision||'NO-GO'} · HISTORICAL</span><h4>{r.coin} · {r.action}</h4><p>Observed quantity: {r.before_size} → {r.after_size}</p><small>{r.source} · {date(r.recorded_at)}</small>{r.analysis?.reasons.map(reason=><p key={reason}>{reason}</p>)}</article>):<p>No subsequent position changes for this wallet in the available event window. The first snapshot is a baseline.</p>}</div>
      </section>;
    })}
  </>;
}

export function MarketContext({data,now,online}:{data:Dashboard|null;now:number;online:boolean}) {
  const prints=data?.trades.filter(t=>Number(t.price)*Number(t.quantity)>=100000).slice(-12).reverse()||[];
  return <><section className="panel"><div className="panel-head"><div><span className="eyebrow">HYPERLIQUID · RECEIPT-TIME CONTEXT</span><h2>Funding, open interest & activity</h2></div></div>{data?.funding.length?<div className="table-scroll"><table><thead><tr><th>Market</th><th>Funding / hour</th><th>Open interest · base units</th><th>24h notional volume · USDC</th><th>Freshness</th></tr></thead><tbody>{data.funding.map(f=><tr key={f.symbol}><td>{f.symbol}</td><td>{f.funding==null?'—':n(Number(f.funding)*100,5)+'%'}</td><td>{n(f.open_interest)}</td><td>{n(f.day_notional_volume,0)}</td><td>{online&&now-f.received_at<30?'recent context':'stale'} · {date(f.received_at)}</td></tr>)}</tbody></table></div>:<div className="wallet-details"><p>Awaiting actual public asset context.</p></div>}<div className="panel-foot">Source: Hyperliquid activeAssetCtx. Provider event time unavailable; receipt age is displayed. Funding can change and is not a guaranteed future cost.</div></section><section className="panel"><div className="panel-head"><div><span className="eyebrow">ACTUAL EXECUTED PRINTS · CURRENT FEED BUFFER</span><h2>Large public trades</h2></div></div>{prints.length?<div className="table-scroll"><table><thead><tr><th>Venue / asset</th><th>Aggressor</th><th>Observed quote notional</th><th>Source time</th></tr></thead><tbody>{prints.map((p,i)=><tr key={i}><td>{p.provider} · {p.symbol}</td><td>{p.side}</td><td>{n(Number(p.price)*Number(p.quantity),0)} {p.provider==='hyperliquid'?'USDC':'USD'}</td><td>{date(p.source_at)}</td></tr>)}</tbody></table></div>:<div className="wallet-details"><p>No print over 100,000 quote units in the current feed buffer. This does not establish an absence of large trading elsewhere.</p></div>}<div className="panel-foot">A public trade shows an execution, not the participant’s intent or complete exposure. Quotes are not substituted for executions.</div></section></>;
}


'use client';
import type {Market} from './types';
import {bookFresh} from './mission-control';
import {tokenName,tokenSymbol} from './token-labels';
export default function ProviderMonitor({markets,symbol,online,now,trades=[]}:{markets:Market[];symbol:string;online:boolean;now:number;trades?:{provider:string;symbol:string;source_at:number}[]}) {
 const token=tokenSymbol(symbol);
 return <section className="provider-monitor" aria-label="Simultaneous provider monitor"><div className="monitor-heading"><span className="eyebrow">THREE SOURCES / ONE TOKEN</span><h3>{tokenName(symbol)} across your feeds</h3></div><div className="monitor-grid">{['coinbase','kraken','hyperliquid'].map(provider=>{
  const market=markets.find(m=>m.provider===provider&&tokenSymbol(m.symbol)===token);
  const fresh=market&&bookFresh(market,online,now),old=!!market?.received_at&&!fresh;
  const state=fresh?'fresh':!online?'disconnected':old?'old':'unavailable';
  const prints=trades.filter(t=>t.provider===provider&&tokenSymbol(t.symbol)===token&&now-t.source_at>=0&&now-t.source_at<=10).length;
  const price=(value:string|null|undefined)=>value==null?'—':Number(value).toLocaleString('en-US',{maximumSignificantDigits:8});
  return <article key={provider} className={'monitor-card '+state}><div><span className="feed-light"/><strong>{provider==='coinbase'?'Coinbase':provider==='kraken'?'Kraken':'Hyperliquid'}</strong><span className={'badge '+(fresh?'live':old?'stale':'unavailable')}>{fresh?'Fresh':old?'Old':!online?'Disconnected':'Unavailable'}</span></div>{provider==='hyperliquid'?<><small>Public trader research</small><p>{fresh?'Market observations arriving':'Waiting for verified observations'}</p><span>{prints?prints+' recent trade records':'No recent trade records available'}</span></>:<><small>Token prices · US dollars</small><dl><div><dt>Buyers offer</dt><dd>${price(market?.bid)}</dd></div><div><dt>Sellers ask</dt><dd>${price(market?.ask)}</dd></div></dl></>}
  <details><summary>Source details</summary><p>{market?.received_at?'Last observation received '+new Date(market.received_at*1000).toLocaleString():'This source has not supplied a verified quote.'}</p>{provider==='hyperliquid'&&<p>Price-contract research in USDC. It is separate from buying the token with US dollars.</p>}<p>{market?.symbol||token} · {market?.integrity||'No verified data'}</p></details></article>;
 })}</div></section>;
}

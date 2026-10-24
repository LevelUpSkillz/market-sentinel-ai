'use client';
import { useEffect, useState } from 'react';

type Quote = {price:string|null;status:string;source_at:number|null;received_at:number|null;volume_24h?:string|null;market_cap?:string|null;change_24h_pct?:string|null;price_kind?:string;timestamp_basis?:string;context_received_at?:number};
type Asset = {id:string;provider_id:string;source:string;symbol:string;name:string;active:boolean;instrument:string;quote_currency:string;watch_symbol:string|null;quote:Quote};
type Directory = {items:Asset[];page:number;limit:number;total:number;counts:{catalogue:number;global_prices:number;venue_markets:number;streaming_quotes:number};as_of:number;watched_markets:{id:string;provider:string;symbol:string}[];extra_book_limit:number;sessions:Record<string,{state:string}>;errors:Record<string,{http_status:number|null;error:string}>;catalogue_received_at:number|null;global_quotes_received_at:number|null;coverage:string;attribution:{label:string;url:string;license:string}};
const BASE = process.env.NEXT_PUBLIC_API_BASE || '';
function num(value:unknown,max=2){return value===null||value===undefined?'—':Number(value).toLocaleString('en-US',{maximumFractionDigits:max})}
function at(value:number|null|undefined){return value?new Date(value*1000).toLocaleString():'Unavailable'}
function status(row:Asset,connected:boolean,now:number){
  const q=row.quote;if(!connected&&q.price)return 'stale';if(!q.price)return 'unavailable';
  const age=now-(q.source_at??q.received_at??0),receipt=now-(q.received_at??0);
  if(age>(row.source==='coinpaprika'?1200:30)||receipt>(row.source==='coinpaprika'?1200:30)||age< -1)return 'stale';
  return q.status;
}

export default function AllMarkets({auth,online,now,onMarketChange,focus,onChart,readOnly=false}:{readOnly?:boolean;auth:boolean;online:boolean;now:number;onMarketChange:()=>void;focus?:{provider:string;symbol:string}|null;onChart?:(market:{provider:string;symbol:string})=>void}){
  const [query,setQuery]=useState(''),[search,setSearch]=useState(''),[source,setSource]=useState('live'),[active,setActive]=useState('active'),[page,setPage]=useState(1);
  useEffect(()=>{setQuery(focus?.symbol.split('-')[0]||'');if(focus)setSource(focus.provider);setPage(1)},[focus]);
  const [data,setData]=useState<Directory|null>(null),[connected,setConnected]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(''),[revision,setRevision]=useState(0);
  useEffect(()=>{const timer=setTimeout(()=>{setSearch(query);setPage(1)},300);return()=>clearTimeout(timer)},[query]);
  useEffect(()=>{
    if(!auth){setData(null);setConnected(false);return}
    let disposed=false,running=false;
    let controller:AbortController|null=null;
    const refresh=async()=>{
      if(running||document.visibilityState!=='visible')return;
      running=true;controller=new AbortController();const timeout=setTimeout(()=>controller?.abort(),15000);
      try{
        const params=new URLSearchParams({q:search,source,active,page:String(page),limit:'25'});
        const response=await fetch(BASE+'/api/assets?'+params,{credentials:'include',signal:controller.signal});
        if(!response.ok)throw new Error(response.status===404?'The broad market feed is waiting for the backend update.':response.status===401?'Sign in to view market coverage.':'Market directory unavailable; retained quotes are stale.');
        const next:Directory=await response.json();
        if(!Array.isArray(next.items))throw new Error('Market directory unavailable.');
        if(!disposed){setData(next);setConnected(true);setError('')}
      }catch(e){if(!disposed){setConnected(false);setError((e as Error).message)}}
      finally{clearTimeout(timeout);running=false}
    };
    setConnected(false);setData(null);refresh();const timer=setInterval(refresh,2000);
    return()=>{disposed=true;controller?.abort();clearInterval(timer)};
  },[auth,search,source,active,page,revision]);
  async function watch(row:Asset,enabled:boolean){
    setBusy(row.id);setError('');
    try{
      const response=await fetch(BASE+'/api/markets/watch',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({market_id:row.id,enabled}),signal:AbortSignal.timeout(15000)});
      if(!response.ok){const body=await response.json();throw new Error(typeof body.detail==='string'?body.detail:'Market selection could not be saved.')}
      setRevision(v=>v+1);onMarketChange();
    }catch(e){setError((e as Error).message)}finally{setBusy('')}
  }
  const pages=data?Math.max(1,Math.ceil(data.total/data.limit)):1;
  return <section className="panel all-markets" aria-label="All crypto markets">
    <div className="panel-head"><div><span className="eyebrow">EXPLORE THE MARKET</span><h2>All crypto markets</h2></div><span className="badge research">READ-ONLY</span></div>
    <div className="catalogue-intro"><p>Search every crypto market published by our connected venues, or explore the broader token catalogue. Venue prices stream through WebSockets while the free backend is awake. This screen refreshes every two seconds while visible.</p>
      <div className="coverage-grid"><div><strong>{num(data?.counts.venue_markets,0)}</strong><small>Venue markets</small></div><div><strong>{num(data?.counts.streaming_quotes,0)}</strong><small>Recently updated quotes</small></div><div><strong>{num(data?.counts.catalogue,0)}</strong><small>Catalogue assets</small></div><div><strong>{num(data?.counts.global_prices,0)}</strong><small>Aggregate USD prices</small></div></div>
    </div>
    <div className="catalogue-filters"><label>Find a token or pair<input aria-label="Search all crypto markets" placeholder="Bitcoin, XRP, DOGE, token ID…" value={query} maxLength={100} onChange={e=>setQuery(e.target.value)}/></label><label>Coverage<select aria-label="Market coverage" value={source} onChange={e=>{setSource(e.target.value);setPage(1)}}><option value="live">Live venues · all markets</option><option value="kraken">Kraken · spot</option><option value="hyperliquid">Hyperliquid · perpetuals</option><option value="coinpaprika">Global token catalogue</option><option value="all">All sources</option></select></label><label>Listings<select aria-label="Listing status" value={active} onChange={e=>{setActive(e.target.value);setPage(1)}}><option value="active">Active</option><option value="all">All, including inactive</option><option value="inactive">Inactive</option></select></label></div>
    {error&&<div role="status" className="catalogue-message">{error}</div>}
    {!auth?<div className="empty"><h3>Sign in to explore the market</h3><p>Market coverage and prices are loaded from the authenticated backend.</p></div>:!data?<div className="empty"><p>{error?'Waiting for verified market data.':'Loading market coverage…'}</p></div>:<>
      <div className="catalogue-results"><span>{num(data.total,0)} matching listings</span><span>{Object.entries(data.sessions).map(([p,s])=>p+': '+s.state).join(' · ')}</span></div>
      {data.items.length?<div className="catalogue-list">{data.items.map(row=>{
        const q=row.quote,state=status(row,connected&&online,now),watching=data.watched_markets.some(r=>r.id===row.id);
        const core=['BTC','ETH','SOL'].includes(row.symbol)&&row.watch_symbol!==null;
        return <article className="catalogue-row" key={row.id}>
          <div className="catalogue-identity"><span className="token-monogram">{row.symbol.slice(0,3)}</span><div><strong>{row.name}</strong><small>{row.symbol} · {row.source} · {row.instrument}{!row.active?' · inactive':''}</small><small className="catalogue-id">{row.id}</small></div></div>
          <div className="catalogue-price"><strong key={q.price} className={state==='live'||state==='streaming'?'quote-tick':''}>{num(q.price,Number(q.price)<1?12:6)} <small>{row.quote_currency}</small></strong><span className={'badge '+state}>{state==='streaming'?'streaming · receipt time':state}</span>{q.price_kind&&<small>{q.price_kind}</small>}</div>
          <div className="catalogue-stat"><small>24h change</small><strong className={Number(q.change_24h_pct)<0?'negative':''}>{num(q.change_24h_pct)}{q.change_24h_pct!=null?'%':''}</strong><small>Volume {num(q.volume_24h)} {row.quote_currency}</small>{q.market_cap!=null&&<small>Market cap {num(q.market_cap)} USD</small>}</div>
          <div className="catalogue-provenance"><small>Source time: {at(q.source_at)}</small><small>Received: {at(q.received_at)}</small>{row.source==='hyperliquid'&&<small>No provider timestamp · context {at(q.context_received_at)}</small>}{row.source==='coinpaprika'&&<small>Aggregate estimate · up to 10 min updates</small>}
            {row.watch_symbol&&<button type="button" className="text-button" onClick={()=>onChart?.({provider:row.source,symbol:row.watch_symbol!})}>View token chart →</button>}
            {!readOnly&&row.watch_symbol&&<button className="secondary compact" disabled={!!busy||!online||core||!row.active} onClick={()=>watch(row,!watching)}>{core?'Core detailed book':busy===row.id?'Saving…':watching?'Remove detailed book':'Add detailed book'}</button>}
          </div>
        </article>
      })}</div>:<div className="empty"><h3>{search?'No matching listings':'Waiting for provider coverage'}</h3><p>{search?'Try another name, native symbol or source. Identical symbols can belong to different tokens.':'The catalogue fills from actual provider responses; no sample prices are substituted.'}</p></div>}
      <div className="catalogue-pagination"><button className="secondary compact" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>Previous</button><span>Page {page} / {pages}</span><button className="secondary compact" disabled={page>=pages} onClick={()=>setPage(p=>p+1)}>Next</button></div>
      {Object.entries(data.errors).length>0&&<div className="catalogue-message">{Object.entries(data.errors).map(([s,e])=><p key={s}>{s}: {e.http_status?'HTTP '+e.http_status:e.error}. Last available data is retained with its original timestamp.</p>)}</div>}
      {data.watched_markets.length>0&&<div className="catalogue-watches"><strong>Additional detailed books · {data.watched_markets.length}/{data.extra_book_limit}</strong><div>{data.watched_markets.map(row=><button className="secondary compact" key={row.id} disabled={!!busy||!online} onClick={()=>watch({id:row.id} as Asset,false)}>{row.symbol} · {row.provider} <span aria-hidden="true">×</span><span className="sr-only">Remove detailed book</span></button>)}</div></div>}
      <div className="panel-foot catalogue-foot"><p>{data.coverage}</p><p>Indicative quotes do not establish executable liquidity or a GO signal. Up to {data.extra_book_limit} extra USD spot or native perpetual books can be selected for depth analysis. Paper entries require a fresh USD spot book.</p><p><a href={data.attribution.url} target="_blank" rel="noreferrer">{data.attribution.label}</a> · {data.attribution.license}</p><small>Catalogue received {at(data.catalogue_received_at)} · aggregate prices received {at(data.global_quotes_received_at)}</small></div>
    </>}
  </section>
}

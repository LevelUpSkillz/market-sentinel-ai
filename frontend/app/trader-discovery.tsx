'use client';

import { useEffect, useRef, useState } from 'react';
import type { JournalRecord, Trader } from './types';

type ReportedWindow = {pnl:string|null;roi_pct:string|null;roi_raw?:string|null;volume:string|null};
type Candidate = {
  address:string;
  label:string;
  account_value:string|null;
  windows:{day?:ReportedWindow;week?:ReportedWindow;month?:ReportedWindow;allTime?:ReportedWindow};
  independent_rank:null;
  data_completeness:string;
};
type Directory = {
  traders:Candidate[];
  total:number;
  page:number;
  limit:number;
  source:string;
  received_at:number|null;
  source_at:null;
  status:string;
  limitations:string[];
  selection_basis:string;
};
type ObservedEvent = JournalRecord & {observed_at?:number;side?:string|null;timing?:string;confidence?:string};
type Props = {readOnly?:boolean;auth:boolean;online:boolean;now:number;events:JournalRecord[];traders:Trader[];onTrack:(address:string,label:string)=>Promise<void>};

const BASE = process.env.NEXT_PUBLIC_API_BASE || '';
const date = (value:number|null|undefined) => value!=null&&Number.isFinite(value)?new Date(value*1000).toLocaleString():'Unavailable';
const n = (value:unknown,digits=2) => value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumFractionDigits:digits});
const reportedRoi = (window:ReportedWindow|undefined) => window?.roi_pct!=null&&Number.isFinite(Number(window.roi_pct))?n(window.roi_pct)+'%':window?.roi_raw!=null&&Number.isFinite(Number(window.roi_raw))?window.roi_raw:'Unavailable';
const roiUnits = (window:ReportedWindow|undefined) => window?.roi_pct!=null?'Provider-reported percentage':window?.roi_raw!=null?'Provider value · unit unverified':'ROI unavailable';
const units = (value:string|null|undefined) => value==null||!Number.isFinite(Number(value))?'Unavailable':n(value)+' provider units';
const short = (address:string) => address.length>18?address.slice(0,8)+'…'+address.slice(-6):address;
const age = (value:number|null|undefined,now:number) => value==null?'Unavailable':Math.max(0,Math.floor(now-value)).toLocaleString('en-US')+'s ago';
const receivedRecently = (value:number|undefined,now:number) => value!=null&&Number.isFinite(value)&&now-value>=0&&now-value<=90;

function direction(before:string|undefined,after:string|undefined,reported:string|null|undefined){
  if(reported==='long'||reported==='short')return reported;
  const current=Number(after),prior=Number(before);
  if(after!=null&&Number.isFinite(current)&&current!==0)return current>0?'long':'short';
  if(before!=null&&Number.isFinite(prior)&&prior!==0)return (prior>0?'long':'short')+' position closed';
  return 'Direction unavailable';
}

export default function TraderDiscovery({auth,online,now,events,traders,onTrack,readOnly=false}:Props){
  const [query,setQuery]=useState(''),[search,setSearch]=useState(''),[page,setPage]=useState(1);
  const [data,setData]=useState<Directory|null>(null),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(''),[loading,setLoading]=useState(false),[connected,setConnected]=useState(false);
  const sequence=useRef(0);
  useEffect(()=>{const timer=setTimeout(()=>{setSearch(query);setPage(1)},300);return()=>clearTimeout(timer)},[query]);
  useEffect(()=>{
    if(!auth){sequence.current+=1;setData(null);setQuery('');setSearch('');setPage(1);setError('');setNotice('');setConnected(false);setLoading(false);return}
    let disposed=false,running=false;
    let controller:AbortController|null=null;
    const refresh=async()=>{
      if(running||document.visibilityState!=='visible')return;
      running=true;setLoading(true);
      const requestNumber=++sequence.current,requestController=new AbortController();controller=requestController;
      const timeout=setTimeout(()=>requestController.abort(),15000);
      try{
        const params=new URLSearchParams({q:search,page:String(page),limit:'12'});
        const response=await fetch(BASE+'/api/trader-directory?'+params,{credentials:'include',signal:requestController.signal});
        if(response.status===401){if(!disposed&&requestNumber===sequence.current){setData(null);setConnected(false);setError('Sign in again to view the public-trader directory.')}return}
        if(!response.ok)throw new Error(response.status===404?'The public-trader directory is waiting for the backend update.':'The experimental provider directory is unavailable.');
        const next:Directory=await response.json();
        if(!Array.isArray(next.traders)||!Number.isFinite(next.total))throw new Error('The provider directory response is unavailable.');
        if(!disposed&&requestNumber===sequence.current){setData(next);setConnected(true);setError('')}
      }catch(e){if(!disposed&&requestNumber===sequence.current){setConnected(false);setError((e as Error).name==='AbortError'?'The provider directory request timed out. Retained metrics are historical.':(e as Error).message)}}
      finally{clearTimeout(timeout);running=false;if(!disposed&&requestNumber===sequence.current)setLoading(false)}
    };
    setData(null);setConnected(false);setError('');refresh();
    const timer=setInterval(refresh,60000);
    const onVisible=()=>{if(document.visibilityState==='visible')refresh()};
    document.addEventListener('visibilitychange',onVisible);
    return()=>{disposed=true;sequence.current+=1;controller?.abort();clearInterval(timer);document.removeEventListener('visibilitychange',onVisible)};
  },[auth,search,page]);

  const tracked=auth?traders:[];
  const addresses=new Set(tracked.map(trader=>trader.address.toLowerCase()));
  const names=new Map(tracked.map(trader=>[trader.address.toLowerCase(),trader.label]));
  const actions=auth?[...(events as ObservedEvent[])].sort((a,b)=>(b.observed_at??b.recorded_at)-(a.observed_at??a.recorded_at)).slice(0,20):[];
  const directory=auth?data:null;
  const pages=directory?Math.max(1,Math.ceil(directory.total/Math.max(1,directory.limit))):1;

  async function track(candidate:Candidate){
    if(busy||!auth||!online)return;
    setBusy(candidate.address);setNotice('');
    try{
      await onTrack(candidate.address,(candidate.label||'Public candidate '+short(candidate.address)).slice(0,60));
      setNotice('Address added for observation. Public positions and subsequent changes will appear after collector polling. No trade was placed.');
    }catch(e){setNotice((e as Error).message)}finally{setBusy('')}
  }

  return <section className="panel" aria-label="Trader Actions">
    <div className="panel-head"><div><span className="eyebrow">PUBLIC CANDIDATES · OBSERVED POSITION CHANGES</span><h2>Trader Actions</h2></div><span className="badge">RESEARCH ONLY</span></div>
    <div className="wallet-details"><p>Discover public Hyperliquid leaderboard candidates and inspect actions from addresses you monitor. This covers one provider’s public sample; no worldwide “best trader” ranking or verified identity is implied.</p>
      <div className="evidence-metrics" style={{marginBottom:0}}><div><small>Monitored public addresses</small><strong>{auth?tracked.length:'—'}{auth?' / 10':''}</strong></div><div><small>Saved action observations shown</small><strong>{auth?actions.length:'—'}</strong></div></div>
    </div>
    {!auth?<div className="empty"><h3>Sign in to investigate trader actions</h3><p>The directory and your private watchlist load through the authenticated API. No trader metrics or positions are invented.</p></div>:<>
      <div className="wallet-details" style={{paddingTop:0,paddingBottom:12}}><span className="eyebrow">OBSERVED ACTION FEED</span><h3>What monitored wallets changed</h3><p>Position rounds take approximately 30 seconds at full watchlist capacity. Changes are observed between polls; their exact execution time and execution prices are unknown.</p></div>
      {actions.length?<div className="table-scroll"><table><thead><tr><th>Observed action / direction</th><th>Wallet</th><th>Position size change</th><th>Observed time / source</th><th>Review at observation</th></tr></thead><tbody>{actions.map(event=>{
        const observedAt=event.observed_at??event.recorded_at;
        const recent=online&&receivedRecently(observedAt,now);
        return <tr key={event.id}><td><strong>{event.coin||'Asset unavailable'} · {event.action||'Change observed'}</strong><small className="source-detail">{direction(event.before_size,event.after_size,event.side)}</small><span className={'badge '+(recent?'live':'stale')}>{recent?'recent observation':'historical observation'}</span></td><td><strong>{event.address?names.get(event.address.toLowerCase())||'Public wallet':'Wallet unavailable'}</strong>{event.address&&<code className="source-detail" title={event.address}>{short(event.address)}</code>}</td><td>{n(event.before_size,8)} → {n(event.after_size,8)}<small className="source-detail">native position units</small></td><td>{date(observedAt)}<small className="source-detail">{event.source||'Source unavailable'}<br/>{event.timing||'Exact execution time is unknown.'}</small></td><td><span className={'badge '+(event.analysis?.decision||'unavailable').toLowerCase()}>{event.analysis?.decision||'UNAVAILABLE'} · HISTORICAL</span><small className="source-detail">Review at {date(observedAt)}. Any current entry requires fresh market and risk checks.</small>{event.analysis?.reasons?.slice(0,2).map((reason,index)=><small className="source-detail" key={index}>{reason}</small>)}</td></tr>;
      })}</tbody></table></div>:<div className="empty"><h3>{tracked.length?'Waiting for a subsequent position change':'Track a public address to observe its actions'}</h3><p>The first position snapshot is a baseline. Openings, increases, reductions, reversals and closures appear only when later public snapshots show a change.</p></div>}
      {tracked.some(trader=>trader.snapshot)&&<details className="wallet-details"><summary style={{cursor:'pointer'}}>Current monitored-position previews</summary><p>Snapshot receipt age is shown below. An observation is not proof of a new entry, a complete portfolio or an executable copy trade.</p>{tracked.filter(trader=>trader.snapshot).map(trader=>{
        const snapshot=trader.snapshot!;
        const recent=online&&receivedRecently(snapshot.received_at,now);
        return <article key={trader.address} style={{padding:'16px 0',borderTop:'1px solid var(--line)'}}><div className="action-heading"><div><strong>{trader.label}</strong><small className="source-detail" title={trader.address}>{short(trader.address)}</small></div><span className={'badge '+(recent?'live':'stale')}>{recent?'recent snapshot':'stale snapshot'}</span></div>
          {snapshot.positions.length?<div className="table-scroll"><table><thead><tr><th>Asset / direction</th><th>Observed position</th><th>Provider average entry</th></tr></thead><tbody>{snapshot.positions.slice(0,3).map(position=><tr key={position.coin}><td>{position.coin} · {Number(position.szi)>0?'long':Number(position.szi)<0?'short':'flat'}</td><td>{n(position.szi,8)} native units</td><td>{n(position.entryPx,8)} provider quote units</td></tr>)}</tbody></table>{snapshot.positions.length>3&&<small>{snapshot.positions.length-3} additional public positions in the full wallet investigation below.</small>}</div>:<p>No current public positions were returned in this snapshot.</p>}
          <small>Source: {snapshot.source} · received {date(snapshot.received_at)} ({age(snapshot.received_at,now)}) · provider time {date(snapshot.source_at)}</small>
        </article>;
      })}</details>}
      <div className="panel-head" style={{borderTop:'1px solid var(--line)'}}><div><span className="eyebrow">EXPERIMENTAL PUBLIC PROVIDER DIRECTORY</span><h3 style={{fontSize:16,fontWeight:500}}>Discover addresses to investigate</h3></div><input className="search-input" aria-label="Search public trader candidates" placeholder="Provider label or public address…" value={query} onChange={event=>setQuery(event.target.value)} maxLength={100}/></div>
      <div className="wallet-details"><p>Leaderboard metrics are reported by the provider and may be incomplete, delayed or affected by deposits, withdrawals, selection and survivorship bias. Following a reported winner does not establish profitable execution for you.</p>{directory&&<small>{directory.total.toLocaleString('en-US')} matching provider candidates · showing {directory.traders.length} on this page · {loading?'refreshing':'directory '+directory.status.replaceAll('_',' ')}{!online||!connected?' · refresh unavailable':''}</small>}</div>
      {error&&<div className="hosting-note" role="status" style={{margin:'0 20px 18px'}}>{error} Monitored action evidence remains separate from this provider directory.</div>}
      {notice&&<div className="hosting-note" role="status" style={{margin:'0 20px 18px'}}>{notice}</div>}
      {directory?.traders.length?<div className="signal-grid">{directory.traders.map(candidate=>{
        const alreadyTracked=addresses.has(candidate.address.toLowerCase());
        const full=tracked.length>=10;
        const valid=/^0x[0-9a-fA-F]{40}$/.test(candidate.address);
        return <article className="signal-card" key={candidate.address} style={{cursor:'default'}}><div className="action-heading"><span className="eyebrow">PROVIDER-REPORTED CANDIDATE</span><span className="badge">UNVALIDATED SKILL</span></div><h3 style={{overflowWrap:'anywhere'}}>{candidate.label||short(candidate.address)}</h3><small>Provider label · identity unverified</small><code style={{display:'block',fontSize:10,overflowWrap:'anywhere',margin:'12px 0'}}>{candidate.address}</code>
          <div className="evidence-metrics" style={{gap:12,margin:'18px 0'}}><div style={{padding:12}}><small>Reported month ROI</small><strong style={{fontSize:17}}>{reportedRoi(candidate.windows.month)}</strong><small>{roiUnits(candidate.windows.month)}</small><small>Reported P&amp;L: {units(candidate.windows.month?.pnl)}</small></div><div style={{padding:12}}><small>Reported all-time ROI</small><strong style={{fontSize:17}}>{reportedRoi(candidate.windows.allTime)}</strong><small>{roiUnits(candidate.windows.allTime)}</small><small>Reported P&amp;L: {units(candidate.windows.allTime?.pnl)}</small></div></div>
          <p>Reported account value: {units(candidate.account_value)}.</p><p>Skill ranking: not independently validated.</p><small style={{display:'block',lineHeight:1.8,margin:'12px 0'}}>{candidate.data_completeness}</small><p>Reported ROI is historical provider data, not a forecast or a probability of winning.</p>
          {!readOnly&&<button className="secondary" style={{width:'100%',marginTop:14}} disabled={!!busy||!online||alreadyTracked||full||!valid} onClick={()=>track(candidate)}>{alreadyTracked?'Tracking actions':busy===candidate.address?'Adding for observation…':full?'Watchlist limit reached':'Track actions'}</button>}
        </article>;
      })}</div>:<div className="empty"><h3>{loading?'Loading provider-reported candidates':error||directory?.status==='unavailable'?'Provider directory currently unavailable':directory&&search?'No matching provider candidates':'Waiting for a provider directory response'}</h3><p>No candidate identities, positions or performance are fabricated. The experimental public frontend feed may change or stop responding.</p></div>}
      {directory&&<><div className="panel-foot" style={{justifyContent:'center'}}><button className="secondary compact" disabled={page<=1||loading} onClick={()=>setPage(value=>value-1)}>Previous</button><span>Page {directory.page} / {pages}</span><button className="secondary compact" disabled={page>=pages||loading} onClick={()=>setPage(value=>value+1)}>Next</button></div>
        <div className="wallet-details"><small>Directory source: {directory.source} · received {date(directory.received_at)} ({age(directory.received_at,now)}) · source time {date(directory.source_at)}. Provider directory data is delayed/receipt-time only, not a live position feed.</small><p>{directory.selection_basis}</p>{directory.limitations.length>0&&<details style={{marginTop:15}}><summary style={{cursor:'pointer'}}>Provider coverage and ranking limits</summary>{directory.limitations.map((limitation,index)=><p key={index}>{limitation}</p>)}</details>}</div>
      </>}
    </>}
    <div className="panel-foot"><span>Experimental Hyperliquid public frontend dependency · undocumented stability · no worldwide skill ranking, verified identity or automatic trade execution.</span></div>
  </section>;
}

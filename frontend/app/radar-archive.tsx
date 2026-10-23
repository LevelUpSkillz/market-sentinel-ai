'use client';

import { useEffect, useRef, useState } from 'react';
import type { RadarSetup } from './radar';

type Snapshot = {source_at?:number|null;received_at?:number|null;integrity?:string;provider?:string;symbol?:string};
type RiskPlan = {maximum_modeled_loss?:string|null;risk_reward?:string|null;decision?:string};
type Transition = {at:number;decision:string;state:string;reasons:string[];source_at:number|null;received_at:number|null};
type Evidence = RadarSetup & {
  recorded_at?:number;
  strategy_version?:string;
  baseline?:{end_at:number;high:string;low:string;momentum_bps:string;range_bps:string;bins?:unknown[]};
  transitions?:Transition[];
  first_paper_ready?:{at:number;entry_vwap:string|null;source_at?:number|null;received_at?:number|null;snapshot?:Snapshot|null;risk_plan?:RiskPlan|null;risk_inputs?:Record<string,unknown>;note?:string};
  snapshot?:Snapshot|null;
  risk_plan?:RiskPlan|null;
  cost_model?:string;
  stages?:{finder?:{facts?:string[]};skeptic?:{objections?:string[]};risk?:{rules?:string[]};decision?:{reason?:string;result?:string}};
};

const BASE = process.env.NEXT_PUBLIC_API_BASE || '';
const date = (value:number|null|undefined) => value!=null&&Number.isFinite(value)?new Date(value*1000).toLocaleString():'Unavailable';
const number = (value:unknown,digits=2) => value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumFractionDigits:digits});
const usd = (value:string|null|undefined) => value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumSignificantDigits:9})+' USD';
const label = (value:string|undefined) => value?value.replaceAll('_',' '):'Unavailable';
const decision = (value:string) => ['GO','WAIT','NO-GO'].includes(value)?value:'UNAVAILABLE';

function interpretation(state:string){
  switch(state){
    case 'expired':return 'The saved entry window expired. This does not establish a winning or losing trade.';
    case 'stale':return 'Fresh comparable observations were unavailable. No outcome can be inferred from a data gap.';
    case 'rejected':return 'The saved entry failed one or more price, cost or deterministic risk checks.';
    case 'invalidated':return 'Observed prices moved beyond the stored hypothesis levels. This does not establish a realized trade outcome.';
    case 'needs_depth':return 'A matching fresh execution book was missing. A catalogue quote could not authorize an entry.';
    case 'waiting_for_trigger':return 'The required observed entry condition had not been satisfied at this saved check.';
    case 'paper_ready':return 'A paper hypothesis passed the recorded checks. This is not evidence that a position was opened or profitable.';
    default:return 'This document preserves the observed setup and its saved checks. It does not establish a realized trading return.';
  }
}

function ArchiveRecord({record}:{record:Evidence}){
  const storedDecision=decision(record.decision);
  const objections=Array.from(new Set([...(record.reasons||[]),...(record.stages?.skeptic?.objections||[])]));
  const facts=Array.from(new Set([...(record.facts||[]),...(record.stages?.finder?.facts||[])]));
  const transitions=[...(record.transitions||[])].sort((a,b)=>a.at-b.at);
  const first=record.first_paper_ready;
  return <details style={{borderTop:'1px solid var(--line)'}}>
    <summary style={{padding:'18px 22px',cursor:'pointer',overflowWrap:'anywhere'}}>
      <span style={{display:'inline-flex',gap:12,alignItems:'center',flexWrap:'wrap',maxWidth:'100%',verticalAlign:'middle'}}>
        <strong>{record.symbol}</strong><span className={'badge '+storedDecision.toLowerCase()}>{storedDecision} · HISTORICAL</span><small>{record.provider} · {label(record.state)} · {date(record.recorded_at??record.created_at)}</small>
      </span>
    </summary>
    <div className="wallet-details" style={{paddingTop:0}}>
      <span className="eyebrow">SAVED SETUP AUTOPSY · LIFECYCLE EVIDENCE</span>
      <h3>{interpretation(record.state)}</h3>
      <p>Saved action text at that check: {record.next_action}</p>
      <small>Created {date(record.created_at)} · expiry {date(record.expires_at)} · first trigger {date(record.triggered_at)} · entry deadline {date(record.entry_deadline)}</small>
      <div className="evidence-metrics">
        <div><small>Original entry trigger / maximum entry</small><strong>{usd(record.entry_trigger)} / {usd(record.entry_limit)}</strong></div>
        <div><small>Frozen stop / target hypotheses</small><strong>{usd(record.stop)} / {usd(record.target)}</strong></div>
        <div><small>Paper notional / modeled loss at saved check</small><strong>{usd(record.notional_usd)} / {usd(record.maximum_modeled_loss)}</strong></div>
        <div><small>Net reward / risk at saved check</small><strong>{number(record.risk_reward)}{record.risk_reward!=null?':1':''}</strong><small>Success probability: not validated</small></div>
      </div>
      <details style={{margin:'18px 0'}}><summary style={{cursor:'pointer'}}>Observed baseline and original evidence</summary>
        {record.baseline?<><p>Observed sampled-price range: {usd(record.baseline.low)} → {usd(record.baseline.high)} · baseline end {date(record.baseline.end_at)}.</p><p>Observed momentum {number(record.baseline.momentum_bps)} bps · sampled range {number(record.baseline.range_bps)} bps{record.baseline.bins?' · '+record.baseline.bins.length+' saved observation bins':''}.</p><p>This range comes from received price samples. It is not a complete exchange candle history, a future forecast or an outcome.</p></>:<p>No baseline was included in this historical document.</p>}
        {facts.map((fact,index)=><p key={index}>{fact}</p>)}
      </details>
      <details style={{margin:'18px 0'}}><summary style={{cursor:'pointer'}}>Saved rejection and risk reasoning</summary>
        {objections.length?objections.map((reason,index)=><p key={index}>{reason}</p>):<p>No additional rejection reason was stored. This does not establish a validated trading edge.</p>}
        {record.stages?.risk?.rules?.map((rule,index)=><p key={'risk'+index}>{rule}</p>)}
        {record.stages?.decision?.reason&&<p>Saved decision: {record.stages.decision.reason}</p>}
        <p>Estimated round-trip cost at the saved check: {number(record.estimated_round_trip_cost_bps)}{record.estimated_round_trip_cost_bps!=null?' bps':''}.</p>
        {record.cost_model&&<p>{record.cost_model}</p>}
      </details>
      {first&&<details style={{margin:'18px 0'}}><summary style={{cursor:'pointer'}}>First eligible paper hypothesis snapshot</summary>
        <p>First recorded paper eligibility: {date(first.at)} · modeled entry VWAP {usd(first.entry_vwap)}.</p>
        <p>Modeled loss at the hypothetical stop {usd(first.risk_plan?.maximum_modeled_loss)} · net modeled reward/risk {number(first.risk_plan?.risk_reward)}{first.risk_plan?.risk_reward!=null?':1':''}.</p>
        <small>Source time {date(first.snapshot?.source_at??first.source_at)} · received {date(first.snapshot?.received_at??first.received_at)} · integrity {first.snapshot?.integrity||'Unavailable'} · historical snapshot.</small>
        {first.risk_inputs&&<p>Paper risk inputs at that check: exposure {usd(typeof first.risk_inputs.exposure==='string'?first.risk_inputs.exposure:null)}, cash {usd(typeof first.risk_inputs.cash==='string'?first.risk_inputs.cash:null)}, daily realized P&amp;L {usd(typeof first.risk_inputs.daily_pnl==='string'?first.risk_inputs.daily_pnl:null)}, emergency stop {first.risk_inputs.stopped===true?'active':first.risk_inputs.stopped===false?'inactive':'unavailable'}.</p>}
        <p>{first.note||'This eligibility snapshot is not an account fill, a real-money approval or a profit measurement.'}</p>
      </details>}
    </div>
    {transitions.length>0&&<><div className="wallet-details" style={{paddingTop:0,paddingBottom:10}}><span className="eyebrow">RECORDED LIFECYCLE</span><p>{transitions.length} stored transition{transitions.length===1?'':'s'} shown. Historical decisions cannot be reused as current entry instructions.</p></div>
      <div className="table-scroll"><table><thead><tr><th>Recorded</th><th>Saved decision / state</th><th>Reason</th><th>Observation provenance</th></tr></thead><tbody>{transitions.map((transition,index)=><tr key={index}><td>{date(transition.at)}</td><td><span className={'badge '+decision(transition.decision).toLowerCase()}>{decision(transition.decision)} · HISTORICAL</span><small className="source-detail">{label(transition.state)}</small></td><td style={{whiteSpace:'normal',minWidth:220}}>{transition.reasons?.length?transition.reasons.map((reason,i)=><p key={i} style={{margin:'4px 0'}}>{reason}</p>):'No additional reason recorded.'}</td><td><small className="source-detail">Source {date(transition.source_at)}<br/>Received {date(transition.received_at)}</small></td></tr>)}</tbody></table></div>
    </>}
    <div className="wallet-details" style={{paddingTop:18}}><small>Latest saved observation: {record.provider} · source time {date(record.snapshot?.source_at??record.source_at)} · received {date(record.snapshot?.received_at??record.received_at)} · integrity {record.snapshot?.integrity||'Unavailable'}. Historical record; not a live quote.</small><p>Strategy: {record.strategy_version||'Unavailable'} · evidence ID <code>{record.id}</code></p></div>
  </details>;
}

export default function RadarArchive({auth,online}:{auth:boolean;online:boolean}){
  const [query,setQuery]=useState(''),[search,setSearch]=useState('');
  const [records,setRecords]=useState<Evidence[]>([]);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  const [loadedAt,setLoadedAt]=useState<number|null>(null);
  const sequence=useRef(0);

  useEffect(()=>{const timer=setTimeout(()=>setSearch(query),300);return()=>clearTimeout(timer)},[query]);
  useEffect(()=>{
    if(!auth){sequence.current+=1;setQuery('');setSearch('');setRecords([]);setLoadedAt(null);setError('');setLoading(false);return}
    let disposed=false,running=false;
    let controller:AbortController|null=null;
    const refresh=async()=>{
      if(running||document.visibilityState!=='visible')return;
      running=true;setLoading(true);
      const requestNumber=++sequence.current;
      const requestController=new AbortController();controller=requestController;
      const timeout=setTimeout(()=>requestController.abort(),15000);
      try{
        const params=new URLSearchParams({limit:'40',q:search});
        const response=await fetch(BASE+'/api/records/radar_signal?'+params,{credentials:'include',signal:requestController.signal});
        if(response.status===401){
          if(!disposed&&requestNumber===sequence.current){setRecords([]);setLoadedAt(null);setError('Sign in again to view saved radar evidence.')}
          return;
        }
        if(!response.ok)throw new Error(response.status===404?'Radar evidence memory is waiting for the backend update.':'Saved radar evidence could not be refreshed.');
        const data:{records:Evidence[]}=await response.json();
        if(!Array.isArray(data.records))throw new Error('Saved radar evidence is unavailable.');
        if(!disposed&&requestNumber===sequence.current){setRecords(data.records);setLoadedAt(Date.now()/1000);setError('')}
      }catch(e){if(!disposed&&requestNumber===sequence.current)setError((e as Error).name==='AbortError'?'Archive request timed out. Retained documents remain historical.':(e as Error).message)}
      finally{clearTimeout(timeout);running=false;if(!disposed&&requestNumber===sequence.current)setLoading(false)}
    };
    setRecords([]);setLoadedAt(null);setError('');refresh();
    const timer=setInterval(refresh,30000);
    const onVisible=()=>{if(document.visibilityState==='visible')refresh()};
    document.addEventListener('visibilitychange',onVisible);
    return()=>{disposed=true;sequence.current+=1;controller?.abort();clearInterval(timer);document.removeEventListener('visibilitychange',onVisible)};
  },[auth,search]);

  const visibleRecords=auth?records:[];
  return <section className="panel" aria-label="Radar evidence memory">
    <div className="panel-head"><div><span className="eyebrow">SEARCHABLE OBSERVATIONS · FROZEN HYPOTHESES</span><h2>Radar evidence memory</h2></div><input className="search-input" aria-label="Search radar evidence" placeholder="Token, reason, state, strategy…" value={auth?query:''} maxLength={200} onChange={event=>setQuery(event.target.value)} disabled={!auth}/></div>
    <div className="wallet-details"><p>Review why an observed setup became eligible, was rejected, lost fresh evidence or expired. Saved GO decisions are historical paper-risk checks, not current entry instructions.</p><small>{auth?`${visibleRecords.length} saved document${visibleRecords.length===1?'':'s'} shown · latest 40 matching records only`:'Sign in to load private evidence.'}{auth&&loadedAt?' · archive loaded '+date(loadedAt):''}{loading?' · refreshing…':''}</small></div>
    {auth&&(error||!online)&&<div className="hosting-note" role="status" style={{margin:'0 20px 18px'}}>{error||'The API is offline. Retained documents are historical evidence.'} No live freshness or trading outcome is inferred.</div>}
    {!auth?<div className="empty"><h3>Private radar history</h3><p>Authenticate to inspect recorded hypotheses and their original evidence.</p></div>:visibleRecords.length?visibleRecords.map(record=><ArchiveRecord key={record.id} record={record}/>):<div className="empty"><h3>{loading?'Loading saved radar evidence':search?'No matching radar evidence':'No radar setups saved yet'}</h3><p>{search?'Try a token, recorded rejection or lifecycle state.':'Actual observed setups are saved after the baseline warms up. No example trades or synthetic outcomes are seeded into this history.'}</p></div>}
    <div className="panel-foot"><span>Lifecycle autopsies explain saved signal behavior. They do not measure realized profit, win rate or validated future success odds.</span></div>
  </section>;
}

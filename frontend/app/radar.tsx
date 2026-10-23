'use client';

import { useEffect, useState } from 'react';

export type RadarSetup = {
  id:string;
  market_id:string;
  provider:string;
  symbol:string;
  decision:string;
  state:string;
  next_action:string;
  created_at:number;
  expires_at:number;
  triggered_at:number|null;
  entry_deadline:number|null;
  entry_trigger:string|null;
  entry_limit:string|null;
  entry_vwap:string|null;
  stop:string|null;
  target:string|null;
  notional_usd:string;
  estimated_round_trip_cost_bps:string|null;
  risk_reward:string|null;
  maximum_modeled_loss:string|null;
  success_probability_pct:null;
  validation_status:string;
  reasons:string[];
  facts:string[];
  source_at:number|null;
  received_at:number|null;
};

export type RadarPayload = {
  as_of:number;
  strategy_version:string;
  mode:'paper_only';
  status:string;
  coverage:{universe:number;observed:number;warming_up:number;ready:number;candidates:number};
  setups:RadarSetup[];
  limitations:string[];
};

type Props = {
  auth:boolean;
  online:boolean;
  now:number;
  onWatch:(marketId:string)=>Promise<void>;
  onPaper:(signalId:string)=>Promise<void>;
  onReal?:(setup:RadarSetup)=>Promise<void>;
};

const BASE = process.env.NEXT_PUBLIC_API_BASE || '';
const date = (value:number|null|undefined) => value&&Number.isFinite(value)?new Date(value*1000).toLocaleString():'Unavailable';
const number = (value:unknown,digits=2) => value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumFractionDigits:digits});
const price = (value:string|null) => value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumSignificantDigits:9})+' USD';
const age = (value:number|null,now:number) => value==null?'unavailable':Math.max(0,Math.floor(now-value))+'s ago';

function recent(value:number|null|undefined,now:number){
  return value!=null&&Number.isFinite(value)&&now-value>=-1&&now-value<=5;
}

function eligibility(setup:RadarSetup,data:RadarPayload,connected:boolean,now:number){
  if(!connected||!recent(data.as_of,now)||!recent(setup.source_at,now)||!recent(setup.received_at,now)){
    return {decision:'NO-GO',reason:'Wait for fresh provider observations. Retained prices cannot authorize a paper entry.',fresh:false};
  }
  if(!Number.isFinite(setup.expires_at)||now>=setup.expires_at){
    return {decision:'NO-GO',reason:'This setup has expired. Wait for a new observed setup.',fresh:true};
  }
  if(setup.entry_deadline!=null&&now>=setup.entry_deadline){
    return {decision:'NO-GO',reason:'The entry window has closed. Do not chase the earlier trigger.',fresh:true};
  }
  if(!['GO','WAIT','NO-GO'].includes(setup.decision)){
    return {decision:'NO-GO',reason:'This setup is unavailable for entry.',fresh:true};
  }
  return {decision:setup.decision,reason:null,fresh:true};
}

function timeLeft(until:number,now:number){
  const seconds=Math.max(0,Math.ceil(until-now));
  return seconds>=60?Math.floor(seconds/60)+'m '+seconds%60+'s':seconds+'s';
}

function RadarGlyph({active}:{active:boolean}){
  return <div className={'radar-glyph '+(active?'is-scanning':'')} aria-hidden="true">
    <svg viewBox="0 0 100 100" fill="none"><circle cx="50" cy="50" r="43"/><circle cx="50" cy="50" r="28"/><circle cx="50" cy="50" r="13"/><path d="M50 7v86M7 50h86"/><circle className="radar-center" cx="50" cy="50" r="3"/></svg>
    <span className="radar-sweep"/>
  </div>;
}

export default function RadarView({auth,online,now,onWatch,onPaper,onReal}:Props){
  const [data,setData]=useState<RadarPayload|null>(null);
  const [connected,setConnected]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [busy,setBusy]=useState('');
  const [revision,setRevision]=useState(0);
  const [clock,setClock]=useState(0);

  useEffect(()=>{
    setClock(Date.now()/1000);
    const timer=setInterval(()=>setClock(Date.now()/1000),1000);
    return()=>clearInterval(timer);
  },[]);

  useEffect(()=>{
    if(!auth){setData(null);setConnected(false);setError('');setNotice('');return}
    let disposed=false,running=false;
    let controller:AbortController|null=null;
    const refresh=async()=>{
      if(running||document.visibilityState!=='visible')return;
      running=true;
      const requestController=new AbortController();
      controller=requestController;
      const timeout=setTimeout(()=>requestController.abort(),15000);
      try{
        const response=await fetch(BASE+'/api/radar',{credentials:'include',signal:requestController.signal});
        if(response.status===401){
          if(!disposed){setData(null);setConnected(false);setError('Sign in again to view the radar.')}
          return;
        }
        if(!response.ok)throw new Error(response.status===404?'The radar is waiting for the backend update.':'The radar is unavailable. Retained setups cannot authorize an entry.');
        const next:RadarPayload=await response.json();
        if(next.mode!=='paper_only'||!Array.isArray(next.setups)||!next.coverage||!Number.isFinite(next.as_of)){
          throw new Error('The radar response is unavailable for paper decisions.');
        }
        if(!disposed){setData(next);setConnected(true);setError('')}
      }catch(e){
        if(!disposed){setConnected(false);setError((e as Error).name==='AbortError'?'Radar request timed out. Wait for a fresh response.':(e as Error).message)}
      }finally{clearTimeout(timeout);running=false}
    };
    setConnected(false);
    refresh();
    const timer=setInterval(refresh,5000);
    const onVisible=()=>{if(document.visibilityState==='visible')refresh()};
    document.addEventListener('visibilitychange',onVisible);
    return()=>{disposed=true;controller?.abort();clearInterval(timer);document.removeEventListener('visibilitychange',onVisible)};
  },[auth,revision]);

  const currentNow=Math.max(now,clock);
  const currentData=auth?data:null;
  const ready=auth&&online&&connected&&!!currentData&&recent(currentData.as_of,currentNow);
  const scanning=ready&&currentData?.status!=='stopped'&&currentData?.status!=='paused';

  async function act(kind:'watch'|'paper'|'real',setup:RadarSetup){
    if(busy)return;
    // A click can follow a delayed render; validate the client clock again.
    if(kind==='paper'&&(!currentData||eligibility(setup,currentData,ready,Math.max(currentNow,Date.now()/1000)).decision!=='GO')){
      setNotice('The paper entry window is no longer current. Wait for a fresh radar check.');
      return;
    }
    setBusy(setup.id);setNotice('');
    try{
      if(kind==='paper')await onPaper(setup.id);
      else if(kind==='real'){if(!onReal)throw new Error('Real-capital planning is unavailable.');await onReal(setup)}
      else await onWatch(setup.market_id);
      setNotice(kind==='paper'?'Paper entry recorded using virtual capital. No exchange order was placed.':kind==='real'?'Real-capital sizing calculated; no order was placed.':'Live depth requested. The radar will check the actual book before evaluating entry.');
      setRevision(v=>v+1);
    }catch(e){setNotice((e as Error).message)}finally{setBusy('')}
  }

  return <section className="panel opportunity-radar" aria-label="Opportunity radar">
    <div className="panel-head"><div><span className="eyebrow">OBSERVE → CHALLENGE → CHECK RISK</span><h2>Opportunity radar</h2></div><span className="badge radar-paper-label">RESEARCH SETUPS</span></div>
    <div className="radar-overview">
      <RadarGlyph active={scanning}/>
      <div className="radar-overview-copy"><span className={'radar-live-label '+(scanning?'is-active':'')}><span/>{!auth?'Private workspace':error?'Feed unavailable':!ready?'Waiting for fresh evidence':currentData?.status?.replaceAll('_',' ')||'Observing markets'}</span>
        <h3>A token. A trigger. A reason to wait.</h3><p>Entries depend on an observed price condition and fresh liquidity. The radar does not predict an exact future minute to buy.</p>
        <small>Five minutes of continuous observed prices establish the baseline. Collection gaps reset it. Free hosting can pause collection.</small>
      </div>
    </div>
    <div className="radar-coverage" aria-label="Radar coverage">
      <div><strong>{number(currentData?.coverage.universe,0)}</strong><small>USD spot markets</small></div>
      <div><strong>{number(currentData?.coverage.observed,0)}</strong><small>Observed this scan</small></div>
      <div><strong>{number(currentData?.coverage.warming_up,0)}</strong><small>Baselines warming up</small></div>
      <div><strong>{number(currentData?.coverage.ready,0)}</strong><small>Baselines ready</small></div>
    </div>
    {error&&<div className="radar-message" role="status">{error}</div>}
    {notice&&<div className="radar-message" role="status">{notice}</div>}
    {!auth?<div className="empty"><h3>Sign in to view observed setups</h3><p>No sample trades or invented opportunities appear here.</p></div>:!currentData?<div className="empty"><h3>Waiting for the radar feed</h3><p>Actual observations, entry conditions and rejections will appear when the backend is available.</p></div>:currentData.setups.length?<div className="radar-setups">
      {currentData.setups.map(setup=>{
        const current=eligibility(setup,currentData,ready,currentNow);
        const deadline=setup.entry_deadline??setup.expires_at;
        const expired=deadline<=currentNow;
        const decision=current.decision;
        const action=current.reason||(decision==='GO'?'Paper entry conditions met':setup.next_action);
        return <article className={'radar-setup '+(decision==='GO'?'paper-ready':'')} key={setup.id} aria-label={setup.symbol+' radar setup'}>
          <div className="radar-setup-heading"><div><span className="eyebrow">{setup.provider} · LONG HYPOTHESIS</span><h3>{setup.symbol}</h3><small>Research hypothesis · execution disabled</small></div><span className={'badge '+decision.toLowerCase().replaceAll(' ','-')}>{decision==='GO'?'GO · PAPER ONLY':decision}</span></div>
          <div className="radar-action"><span className="radar-action-marker"/><div><strong>{action}</strong><p>{setup.triggered_at==null?'Wait until the observed price crosses the trigger, then recheck the executable book.':'Trigger first observed '+date(setup.triggered_at)+'. Entry must still fit the price limit and open window.'}</p></div></div>
          <div className="radar-levels"><div><small>Entry trigger</small><strong>{price(setup.entry_trigger)}</strong></div><div><small>Maximum entry</small><strong>{price(setup.entry_limit)}</strong></div><div><small>Current entry VWAP</small><strong>{price(setup.entry_vwap)}</strong></div><div><small>Stop hypothesis</small><strong>{price(setup.stop)}</strong></div><div><small>Target hypothesis</small><strong>{price(setup.target)}</strong></div><div><small>Paper notional</small><strong>{price(setup.notional_usd)}</strong></div></div>
          <div className="radar-economics"><div><small>Net modeled reward / risk</small><strong>{number(setup.risk_reward)}{setup.risk_reward!=null?':1':''}</strong></div><div><small>Modeled loss at stop</small><strong>{price(setup.maximum_modeled_loss)}</strong></div><div><small>Round-trip cost estimate</small><strong>{number(setup.estimated_round_trip_cost_bps)}{setup.estimated_round_trip_cost_bps!=null?' bps':''}</strong></div><div><small>Success odds</small><strong className="radar-unvalidated">Not validated</strong></div></div>
          <div className={'radar-window '+(expired?'is-expired':'')}><span>{setup.entry_deadline!=null?'Entry window':'Setup expiry'}<strong>{expired?'Closed':timeLeft(deadline,currentNow)+' remaining'}</strong></span><small>{date(deadline)}<br/>{expired?'Wait for a new setup.':'Reject any entry above the maximum entry price.'}</small></div>
          <details className="radar-evidence"><summary>Why this setup was found or rejected</summary><h4>Observed facts</h4>{setup.facts.length?setup.facts.map((fact,i)=><p key={'fact'+i}>{fact}</p>):<p>No additional observed fact was supplied.</p>}<h4>Evidence against entry</h4>{current.reason&&<p>{current.reason}</p>}{setup.reasons.length?setup.reasons.map((reason,i)=><p key={'reason'+i}>{reason}</p>):<p>No additional risk rejection was supplied. Predictive edge remains unvalidated.</p>}<h4>Interpretation</h4><p>Trigger, stop and target are calculated hypothesis levels, not price forecasts. A 2:1 reward/risk ratio does not mean a two-thirds chance of success. Gaps or execution conditions can cause losses beyond the modeled stop.</p><small>Validation: {setup.validation_status.replaceAll('_',' ')} · strategy {currentData.strategy_version}</small></details>
          <div className="radar-setup-actions">{onReal&&setup.stop&&setup.target&&<button className="secondary" disabled={!!busy||!online||expired||!ready} onClick={()=>act('real',setup)}>Size with my real budget</button>}{setup.state==='needs_depth'&&<button className="secondary" disabled={!!busy||!online||expired||!ready} onClick={()=>act('watch',setup)}>{busy===setup.id?'Checking…':'Inspect live depth'}</button>}{decision==='GO'&&<button className="primary" disabled={!!busy||!ready} onClick={()=>act('paper',setup)}>{busy===setup.id?'Recording…':'Record paper entry'}</button>}<small>Source: {setup.provider} · source time {date(setup.source_at)} · received {date(setup.received_at)} ({age(setup.received_at,currentNow)})</small></div>
        </article>;
      })}
    </div>:<div className="empty radar-empty"><h3>{currentData.coverage.ready>0?'No setup currently meets the observation rules':'Building the observed baseline'}</h3><p>{currentData.coverage.ready>0?'A quiet radar is a valid result. The app will show a token only when actual observations support a conditional paper hypothesis.':'The radar needs five minutes of continuous fresh observations. It will not fill missing history or invent a trade.'}</p></div>}
    <div className="radar-explanation"><details><summary>What is a paper trade?</summary><p>A paper trade uses virtual money and real market prices. It records a simulated entry and exit with estimated fees and slippage. No real money moves and no exchange order is placed.</p><p>It helps test a hypothesis before relying on a signal. Paper performance can differ from real trading. A paper GO does not approve a real-money trade. The separate real-budget planner sizes a manual hypothesis against your declared limits and places no order.</p></details></div>
    <div className="panel-foot radar-foot"><p>GO means eligible for a paper experiment after current deterministic risk checks. Predictive edge and success probability remain unvalidated.</p>{currentData?.limitations.length?<details><summary>Coverage and model limits</summary>{currentData.limitations.map((line,i)=><p key={i}>{line}</p>)}</details>:null}<small>Source-aware observations · {currentData?.strategy_version||'strategy unavailable'} · last scan {date(currentData?.as_of)}</small></div>
  </section>;
}

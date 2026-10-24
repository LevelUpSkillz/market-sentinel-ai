'use client';

import { useEffect, useRef, useState } from 'react';

type CapitalFields = {
  capital_usd:string;
  available_cash_usd:string;
  existing_crypto_exposure_usd:string;
  daily_realized_pnl_usd:string;
  risk_per_trade_pct:string;
  max_position_pct:string;
  max_crypto_exposure_pct:string;
  daily_loss_limit_pct:string;
};

export type RealCapitalProfile = CapitalFields & {
  currency:'USD';
  source:'USER_DECLARED_UNVERIFIED';
  confirmed_at:number;
  stale:boolean;
  stale_reasons:string[];
  execution_enabled:false;
};

export type RealPlan = {
  risk_decision:'PASS'|'FAIL';
  trade_decision:'WAIT';
  provider?:string;
  symbol?:string;
  notional_usd:string|null;
  entry_cost_usd:string|null;
  modeled_loss_usd:string|null;
  net_target_profit_usd:string|null;
  net_reward_risk:string|null;
  risk_budget_usd:string|null;
  remaining_daily_loss_budget_usd:string|null;
  quantity:string|null;
  entry_vwap:string|null;
  stop:string|null;
  target:string|null;
  expires_at:number;
  profile_confirmed_at?:number;
  snapshot?:{provider:string;symbol:string;source_at:number|null;received_at:number};
  reasons:string[];
  limitations:string[];
  source:'USER_DECLARED_UNVERIFIED';
  validation_status:'unvalidated';
  execution_enabled?:false;
};

type CapitalResponse = {
  profile:RealCapitalProfile|null;
  execution_enabled:false;
  connection?:{provider:string|null;status:string};
};

const BASE = process.env.NEXT_PUBLIC_API_BASE || '';
const emptyFields = ():CapitalFields => ({
  capital_usd:'',available_cash_usd:'',existing_crypto_exposure_usd:'',daily_realized_pnl_usd:'',
  risk_per_trade_pct:'0.5',max_position_pct:'5',max_crypto_exposure_pct:'25',daily_loss_limit_pct:'2',
});
const amount = (value:unknown,digits=2) => value===null||value===undefined||value===''||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumFractionDigits:digits});
const usd = (value:unknown) => value===null||value===undefined||value===''||!Number.isFinite(Number(value))?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(Number(value));
const date = (value?:number|null) => value?new Date(value*1000).toLocaleString():'Unavailable';

async function request<T>(body?:unknown,signal?:AbortSignal):Promise<T> {
  const response = await fetch(BASE+'/api/capital',{
    method:body===undefined?'GET':'POST',credentials:'include',signal:signal??AbortSignal.timeout(15000),
    headers:body===undefined?undefined:{'Content-Type':'application/json'},
    body:body===undefined?undefined:JSON.stringify(body),
  });
  if(!response.ok){
    let detail=response.status===401?'Sign in to manage your real-capital limits.':'Real-capital configuration could not be loaded.';
    try{const data=await response.json();if(typeof data.detail==='string')detail=data.detail}catch{}
    throw Object.assign(new Error(detail),{status:response.status});
  }
  return response.json();
}

function fieldsFrom(profile:RealCapitalProfile):CapitalFields {
  return Object.fromEntries(Object.keys(emptyFields()).map(key=>[key,String(profile[key as keyof CapitalFields])])) as CapitalFields;
}

export default function CapitalSettings({auth,online,onProfile}:{auth:boolean;online:boolean;onProfile?:(value:RealCapitalProfile|null)=>void}) {
  const [profile,setProfile]=useState<RealCapitalProfile|null>(null);
  const [fields,setFields]=useState<CapitalFields>(emptyFields);
  const [connection,setConnection]=useState<CapitalResponse['connection']>();
  const [busy,setBusy]=useState(false),[loading,setLoading]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[retry,setRetry]=useState(0),[now,setNow]=useState(0);
  const edited=useRef(false),saveController=useRef<AbortController|null>(null),mounted=useRef(true);

  useEffect(()=>{mounted.current=true;setNow(Date.now()/1000);const timer=setInterval(()=>setNow(Date.now()/1000),30000);return()=>{mounted.current=false;clearInterval(timer);saveController.current?.abort()}},[]);
  useEffect(()=>{
    if(!auth){setProfile(null);setFields(emptyFields());setConnection(undefined);setError('');setNotice('');edited.current=false;saveController.current?.abort();return}
    const controller=new AbortController();let active=true;
    const timeout=setTimeout(()=>controller.abort(),15000);
    setLoading(true);setError('');
    request<CapitalResponse>(undefined,controller.signal).then(data=>{
      if(!active)return;
      setProfile(data.profile);setConnection(data.connection);
      if(data.profile&&!edited.current)setFields(fieldsFrom(data.profile));
    }).catch(e=>{
      if(!active)return;
      if((e as {status?:number}).status===401){setProfile(null);setFields(emptyFields());setConnection(undefined);edited.current=false}
      setError((e as Error).name==='AbortError'?'The API did not respond. Reconnect and try again.':(e as Error).message);
    }).finally(()=>{clearTimeout(timeout);if(active)setLoading(false)});
    return()=>{active=false;controller.abort();clearTimeout(timeout)};
  },[auth,retry]);

  const stale=!!profile&&(profile.stale||now-profile.confirmed_at>=86400||Math.floor(now/86400)!==Math.floor(profile.confirmed_at/86400));
  useEffect(()=>{onProfile?.(auth?profile:null)},[auth,profile,onProfile]);
  function change(key:keyof CapitalFields,value:string){edited.current=true;setFields(previous=>({...previous,[key]:value}));setNotice('')}
  async function save(){
    if(!auth||!online||busy)return;
    saveController.current?.abort();const controller=new AbortController();saveController.current=controller;
    let timedOut=false;
    const timeout=setTimeout(()=>{timedOut=true;controller.abort()},15000);
    setBusy(true);setError('');setNotice('');
    try{
      const result=await request<RealCapitalProfile|CapitalResponse>(fields,controller.signal);
      if(!mounted.current||(controller.signal.aborted&&!timedOut))return;
      const next='profile' in result?result.profile:result;
      if(!next)throw new Error('No saved risk profile was returned.');
      setProfile(next);setFields(fieldsFrom(next));edited.current=false;
      setNotice('Real-capital limits saved as your declared inputs. No money moved and no exchange order was placed.');
    }catch(e){
      if(!mounted.current||(controller.signal.aborted&&!timedOut))return;
      if((e as {status?:number}).status===401){setProfile(null);setFields(emptyFields());setConnection(undefined);edited.current=false}
      setError(timedOut?'Saving timed out. Reload saved limits to check whether the server received them.':(e as Error).message);
    }finally{clearTimeout(timeout);if(mounted.current)setBusy(false)}
  }

  return <section className="panel" aria-label="Real-capital configuration">
    <div className="panel-head"><div><span className="eyebrow">YOUR REAL BUDGET · MANUAL DECLARATION</span><h2>Real-capital budget &amp; limits</h2></div><span className={'badge '+(stale?'stale':profile?'wait':'unavailable')}>{stale?'Reconfirm balances':profile?'Declared · unverified':'Not configured'}</span></div>
    <div className="wallet-details"><p>Set the USD budget and limits applied to planning and individually approved Kraken orders. These amounts are separate from your simulated paper wallet.</p><p>Use <strong>USD amounts</strong>. The app does not convert CAD, USDC or other currencies into USD or verify these inputs against your exchange account.</p>
      {profile&&<small>Source: your declaration · last confirmed {date(profile.confirmed_at)} · currency USD</small>}
      {connection&&<p>Exchange connection: {connection.provider||'No provider selected'} · {connection.status.replaceAll('_',' ')}.</p>}
      {stale&&<p className="negative">Reconfirm your current cash, exposure and today’s realized P&amp;L before creating another plan.{profile?.stale_reasons.map(reason=><span key={reason} style={{display:'block'}}>{reason}</span>)}</p>}
    </div>
    {!auth?<div className="wallet-details"><p>Sign in to configure your real-capital budget. No real balance is assumed.</p></div>:<>
      <form className="lab-form" onSubmit={event=>{event.preventDefault();save()}} aria-label="Real-capital limits form">
        <label>Total trading capital (USD)<input aria-label="Total real trading capital in USD" inputMode="decimal" type="number" min="0.01" max="10000000" step="any" value={fields.capital_usd} onChange={e=>change('capital_usd',e.target.value)} placeholder="Enter your actual budget" required disabled={busy}/></label>
        <label>Available cash (USD)<input aria-label="Available real cash in USD" inputMode="decimal" type="number" min="0" max="10000000" step="any" value={fields.available_cash_usd} onChange={e=>change('available_cash_usd',e.target.value)} placeholder="Enter available cash" required disabled={busy}/></label>
        <label>Money already in crypto (USD)<input aria-label="Existing real crypto exposure in USD" inputMode="decimal" type="number" min="0" max="10000000" step="any" value={fields.existing_crypto_exposure_usd} onChange={e=>change('existing_crypto_exposure_usd',e.target.value)} placeholder="Enter current exposure, or 0" required disabled={busy}/></label>
        <label>Today’s closed-trade profit / loss (USD · UTC day)<input aria-label="Today's realized real profit or loss in USD" inputMode="decimal" type="number" min="-10000000" max="10000000" step="any" value={fields.daily_realized_pnl_usd} onChange={e=>change('daily_realized_pnl_usd',e.target.value)} placeholder="Use a minus sign for a loss" required disabled={busy}/></label>
        <div className="wide"><small>The percentages below start with editable example limits. They are not a recommendation or proof that a trade is suitable.</small></div>
        <label>Most to risk per trade (% of budget)<input aria-label="Real risk per trade percentage" inputMode="decimal" type="number" min="0.000001" max="2" step="any" value={fields.risk_per_trade_pct} onChange={e=>change('risk_per_trade_pct',e.target.value)} required disabled={busy}/></label>
        <label>Most to spend on one trade (% of budget)<input aria-label="Maximum real position percentage" inputMode="decimal" type="number" min="0.000001" max="25" step="any" value={fields.max_position_pct} onChange={e=>change('max_position_pct',e.target.value)} required disabled={busy}/></label>
        <label>Most of my budget allowed in crypto (%)<input aria-label="Total real crypto exposure percentage" inputMode="decimal" type="number" min="0.000001" max="100" step="any" value={fields.max_crypto_exposure_pct} onChange={e=>change('max_crypto_exposure_pct',e.target.value)} required disabled={busy}/></label>
        <label>Stop new trades after losing today (%)<input aria-label="Real daily loss limit percentage" inputMode="decimal" type="number" min="0.000001" max="10" step="any" value={fields.daily_loss_limit_pct} onChange={e=>change('daily_loss_limit_pct',e.target.value)} required disabled={busy}/></label>
        <button className="primary" disabled={busy||loading||!online}>{busy?'Saving limits…':stale?'Reconfirm real-capital limits':'Save real-capital limits'}</button>
      </form>
      {loading&&<div className="wallet-details"><p role="status">Loading saved limits…</p></div>}
      {notice&&<div className="wallet-details"><p role="status">{notice}</p></div>}
      {error&&<div className="wallet-details"><p className="negative" role="alert">{error}</p><button type="button" className="secondary compact" disabled={busy||!online} onClick={()=>setRetry(value=>value+1)}>Reload saved limits</button></div>}
      {!online&&<div className="wallet-details"><p>API offline. Saved declarations have not been refreshed; saving requires a connection.</p></div>}
    </>}
    <div className="panel-foot" style={{display:'block'}}>These are your declared limits, separate from actual Kraken balances. They apply to planning and manual order checks. Risk checks do not establish a profitable trading edge. Exchange order submission is disabled here; this form never requests exchange credentials.</div>
  </section>;
}

export function RealPlanView({plan}:{plan:RealPlan|null}) {
  const [now,setNow]=useState(0);
  useEffect(()=>{setNow(Date.now()/1000);const timer=setInterval(()=>setNow(Date.now()/1000),1000);return()=>clearInterval(timer)},[]);
  if(!plan)return null;
  const expired=now>0&&(!plan.expires_at||now>=plan.expires_at);
  const passed=plan.risk_decision==='PASS'&&!expired;
  return <section className="panel" aria-label="Real-capital manual trade plan">
    <div className="panel-head"><div><span className="eyebrow">REAL-CAPITAL MANUAL PLAN · NO ORDER PLACED</span><h2>{plan.symbol||'Trade plan'}{plan.provider?' · '+plan.provider:''}</h2></div><span className={'badge '+(expired?'stale':passed?'wait':'no-go')}>{expired?'Quote expired':passed?'Risk checks passed':'Risk checks failed'}</span></div>
    <div className="wallet-details"><p><strong>Trade decision: WAIT.</strong> Passing the risk calculation does not establish a validated trading edge or approve a real-money order.</p><p>This plan uses your declared USD capital and a sampled market book. Stop and target levels are hypotheses; a 2:1 modeled reward/risk ratio is not a win probability.</p></div>
    <div className="evidence-metrics" style={{padding:'0 22px 20px'}}>
      <div><small>Indicative quantity</small><strong>{amount(plan.quantity,8)}</strong></div>
      <div><small>Estimated average buy price · USD</small><strong>{amount(plan.entry_vwap,10)}</strong></div>
      <div><small>Price where idea fails · USD</small><strong>{amount(plan.stop,10)}</strong></div>
      <div><small>Possible exit price · USD</small><strong>{amount(plan.target,10)}</strong></div>
      <div><small>Position notional</small><strong>{usd(plan.notional_usd)}</strong></div>
      <div><small>Entry cost including modeled fees</small><strong>{usd(plan.entry_cost_usd)}</strong></div>
      <div><small>Modeled loss at stop</small><strong>{usd(plan.modeled_loss_usd)}</strong><small>Gaps can produce a greater loss.</small></div>
      <div><small>Net modeled profit at target</small><strong>{usd(plan.net_target_profit_usd)}</strong></div>
      <div><small>Net modeled reward / risk</small><strong>{amount(plan.net_reward_risk,2)}{plan.net_reward_risk!==null?' : 1':''}</strong></div>
      <div><small>Declared per-trade risk budget</small><strong>{usd(plan.risk_budget_usd)}</strong></div>
      <div><small>Remaining declared daily loss budget</small><strong>{usd(plan.remaining_daily_loss_budget_usd)}</strong></div>
      <div><small>Success probability</small><strong>Not validated</strong></div>
    </div>
    <div className="wallet-details">
      <p>{expired?'Prices expired. Refresh the plan with a fresh book before using these numbers.':'Quote validity ends '+date(plan.expires_at)+'. Recheck prices and balances before acting.'}</p>
      <small>Capital source: your unverified declaration · confirmed {date(plan.profile_confirmed_at)}</small>
      {plan.snapshot&&<small style={{display:'block'}}>Market source: {plan.snapshot.provider} · source time {date(plan.snapshot.source_at)} · received {date(plan.snapshot.received_at)}</small>}
      {plan.reasons.map(reason=><p key={reason}>{reason}</p>)}
      <details><summary>Assumptions and limits</summary>{plan.limitations.map(limit=><p key={limit}>{limit}</p>)}</details>
    </div>
    <div className="panel-foot">Manual planning only. No funds were moved, no order was submitted, and no success probability was inferred.</div>
  </section>;
}

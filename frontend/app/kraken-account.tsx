'use client';

import { useEffect, useRef, useState } from 'react';

export type KrakenConnectionStatus = {
  provider:string;
  status:string;
  connected:boolean;
  credential_entry_enabled:boolean;
  order_submission_enabled:boolean;
  live_order_submission_enabled:boolean;
  withdrawals_enabled?:boolean;
  requirements?:string[];
  trading_fees?:string;
  connection?:{id:string;verified_at:number;permissions:string[];can_trade:boolean}|null;
  markets?:{symbol:string;ready:boolean}[];
  active_order?:(KrakenOrderResult&KrakenOrderTerms)|null;
};
export type KrakenAccountSnapshot = {
  verified_at:number;
  balances:{asset:string;balance:string;available:string}[];
  open_orders:{id:string;pair:string;side:string;quantity:string;executed:string;status:string;limit_price:string}[];
  fees_note:string;
};
export type KrakenOrderTerms = {
  id:string;
  expires_at:number;
  symbol:string;
  side:'buy'|'sell';
  quantity:string;
  limit_price:string;
  estimated_notional?:string;
  fee_reserve?:string;
  quote_currency?:'USD';
  risk_disclosure?:string|string[];
  provider_validation?:boolean;
};
export type KrakenOrderPreview = KrakenOrderTerms&{
  status:'validated';
  estimated_notional:string;
  fee_reserve:string;
  quote_currency:'USD';
  risk_disclosure:string|string[];
  provider_validation:true;
};
export type KrakenOrderResult = {
  id?:string;
  status:'submitting'|'submitted'|'unknown'|'rejected'|'resolved';
  order_ids:string[];
  message:string;
};

const BASE=process.env.NEXT_PUBLIC_API_BASE||'';
const CONFIRMATION='PLACE THIS REAL ORDER';
const ACCOUNT_MAX_AGE=60;
const actionButtonStyle={whiteSpace:'normal' as const,minHeight:44,maxWidth:'100%'};
const positiveDecimal=(value:string)=>/^\d+(?:\.\d+)?$/.test(value)&&Number.isFinite(Number(value))&&Number(value)>0;
const date=(at:number)=>Number.isFinite(at)?new Date(at*1000).toLocaleString():'Unavailable';
class KrakenRequestError extends Error {
  constructor(message:string,readonly status:number){super(message)}
}

// Preserve backend decimal amounts when adding the maximum buy cost. Monetary
// arithmetic must not introduce binary floating-point rounding into the review.
function maximumBuyCost(notional:string,reserve:string):string|null {
  if(typeof notional!=='string'||typeof reserve!=='string'||!/^\d+(?:\.\d+)?$/.test(notional)||!/^\d+(?:\.\d+)?$/.test(reserve)||notional.length>120||reserve.length>120)return null;
  const [wholeA,fractionA='']=notional.split('.'),[wholeB,fractionB='']=reserve.split('.');
  const places=Math.max(fractionA.length,fractionB.length);
  const total=BigInt(wholeA+fractionA.padEnd(places,'0'))+BigInt(wholeB+fractionB.padEnd(places,'0'));
  if(!places)return total.toString();
  const digits=total.toString().padStart(places+1,'0');
  return (digits.slice(0,-places)+'.'+digits.slice(-places)).replace(/\.?0+$/,'');
}

function PreviewDetails({preview}:{preview:KrakenOrderTerms}) {
  const maximum=preview.estimated_notional!=null&&preview.fee_reserve!=null?maximumBuyCost(preview.estimated_notional,preview.fee_reserve):null;
  return <>
    <div className="evidence-metrics">
      <div><small>Exact real order</small><strong>{preview.side.toUpperCase()} {preview.symbol}</strong><small>Spot immediate-or-cancel limit order</small></div>
      <div><small>Quantity · base asset units</small><strong>{preview.quantity}</strong></div>
      <div><small>Limit price</small><strong>{preview.limit_price} USD</strong></div>
      <div><small>{preview.side==='buy'?'Maximum buy cost with fee reserve':'Gross proceeds at the limit price'}</small><strong>{preview.side==='buy'?(maximum===null?'Unavailable':maximum+' USD'):preview.estimated_notional==null?'Unavailable':preview.estimated_notional+' USD'}</strong><small>Fee reserve: {preview.fee_reserve==null?'Unavailable':preview.fee_reserve+' USD'}</small></div>
    </div>
    <p>{preview.side==='buy'?'The order cannot buy above this limit price; fee assumptions and available funds are rechecked by the server.':'The order cannot sell below this limit price. Fees reduce proceeds; available base-asset funds are rechecked by the server.'}</p>
    <p>This immediate-or-cancel order can fill partially; Kraken cancels any unfilled remainder. Provider validation does not submit an order or guarantee a fill, profit or maximum trading loss. No protective stop-loss order is included.</p>
    {(Array.isArray(preview.risk_disclosure)?preview.risk_disclosure:preview.risk_disclosure?[preview.risk_disclosure]:[]).map((text,index)=><p key={index}>{text}</p>)}
  </>;
}

export default function KrakenAccount({auth,online}:{auth:boolean;online:boolean}) {
  const [connection,setConnection]=useState<KrakenConnectionStatus|null>(null);
  const [account,setAccount]=useState<KrakenAccountSnapshot|null>(null);
  const [apiKey,setApiKey]=useState(''),[apiSecret,setApiSecret]=useState('');
  const [countryCode,setCountryCode]=useState(''),[region,setRegion]=useState('');
  const [eligibilityConfirmed,setEligibilityConfirmed]=useState(false),[dedicatedKeyConfirmed,setDedicatedKeyConfirmed]=useState(false);
  const [symbol,setSymbol]=useState(''),[side,setSide]=useState<'buy'|'sell'>('buy');
  const [quantity,setQuantity]=useState(''),[limitPrice,setLimitPrice]=useState('');
  const [preview,setPreview]=useState<KrakenOrderPreview|null>(null),[confirmation,setConfirmation]=useState('');
  const [result,setResult]=useState<(KrakenOrderResult&{order:KrakenOrderTerms})|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [now,setNow]=useState(0),[secureContext,setSecureContext]=useState(false);
  const mounted=useRef(false),authorized=useRef(auth),working=useRef(false),pending=useRef<AbortController|null>(null);
  authorized.current=auth;

  async function request<T>(path:string,body?:unknown,secretRequest=false):Promise<T> {
    const controller=new AbortController();pending.current=controller;
    const timeout=setTimeout(()=>controller.abort(),20000);
    try {
      const response=await fetch(BASE+'/api'+path,{method:body===undefined?'GET':'POST',credentials:'include',cache:'no-store',
        headers:body===undefined?undefined:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
      if(!response.ok){
        let message=response.status===401?'Sign in again to access your Kraken connection.':'The Kraken request could not be completed.';
        // Account/risk routes return fixed nonsecret AccountError messages.
        // Never read or render a credential-ingestion failure response body.
        if(!secretRequest){try{const value=await response.json();if(typeof value.detail==='string'&&value.detail.length<=500)message=value.detail}catch{}}
        throw new KrakenRequestError(message,response.status);
      }
      return await response.json();
    } finally {clearTimeout(timeout);if(pending.current===controller)pending.current=null}
  }
  async function action(run:()=>Promise<void>) {
    if(working.current||!authorized.current)return;
    working.current=true;setBusy(true);setError('');setNotice('');
    try {await run()}catch(error) {if(mounted.current&&authorized.current)setError(error instanceof KrakenRequestError?error.message:'The request could not be completed. Refresh connection status and review your Kraken account before continuing.')}
    finally {working.current=false;if(mounted.current)setBusy(false)}
  }
  async function readConnection() {
    const value=await request<KrakenConnectionStatus>('/connections');
    if(value.provider!=='kraken')throw new Error('Unexpected provider');
    if(mounted.current&&authorized.current){
      setConnection(value);setPreview(null);setConfirmation('');setAccount(null);
      const active=value.active_order;
      if(active?.id&&['submitting','submitted','unknown'].includes(active.status))setResult({...active,order:active});
    }
  }
  const refreshConnection=()=>action(readConnection);

  useEffect(()=>{
    mounted.current=true;
    const endpoint=new URL(BASE||window.location.origin,window.location.origin);
    const loopback=['localhost','127.0.0.1','[::1]'].includes(endpoint.hostname);
    setSecureContext(window.isSecureContext&&(endpoint.protocol==='https:'||(endpoint.protocol==='http:'&&loopback)));
    setNow(Date.now()/1000);
    // This clock only expires the displayed review; it makes no network calls.
    const timer=setInterval(()=>setNow(Date.now()/1000),1000);
    return()=>{mounted.current=false;clearInterval(timer);pending.current?.abort()};
  },[]);
  useEffect(()=>{
    setConnection(null);setAccount(null);setPreview(null);setConfirmation('');setApiKey('');setApiSecret('');setCountryCode('');setRegion('');setEligibilityConfirmed(false);setDedicatedKeyConfirmed(false);setError('');setNotice('');
    if(!auth){pending.current?.abort();return}
    refreshConnection();
    // A connection read runs on sign-in only. Balance and order reads are manual.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[auth]);

  const connected=auth&&connection?.connected===true;
  const accountFresh=online&&account!=null&&Number.isFinite(account.verified_at)&&now-account.verified_at>=0&&now-account.verified_at<=ACCOUNT_MAX_AGE;
  const tradingPermission=connected&&connection?.connection?.can_trade===true;
  const submissionEnabled=tradingPermission&&connection?.order_submission_enabled===true&&connection.live_order_submission_enabled===true;
  const unresolved=result!=null&&['submitting','submitted','unknown'].includes(result.status);
  const reviewFresh=preview!=null&&Number.isFinite(preview.expires_at)&&now>0&&now<preview.expires_at;
  const validPreview=preview?.status==='validated'&&preview.provider_validation===true&&preview.quote_currency==='USD'&&
    positiveDecimal(preview.quantity)&&positiveDecimal(preview.limit_price)&&maximumBuyCost(preview.estimated_notional,preview.fee_reserve)!==null;
  const canApprove=auth&&online&&!busy&&!unresolved&&submissionEnabled&&accountFresh&&reviewFresh&&validPreview&&confirmation===CONFIRMATION;
  const markets=connection?.markets?.filter(row=>typeof row.symbol==='string'&&row.symbol.endsWith('-USD'))||[];
  const marketReady=markets.some(row=>row.symbol===symbol&&row.ready);
  const canPreview=auth&&online&&!busy&&!unresolved&&tradingPermission&&accountFresh&&marketReady&&positiveDecimal(quantity)&&positiveDecimal(limitPrice);

  function invalidateReview(){setPreview(null);setConfirmation('')}
  async function connect() {
    // Keep values only for this one request, then immediately clear the inputs.
    // They are never saved to local/session storage or included in log messages.
    const credentials={api_key:apiKey,api_secret:apiSecret,country_code:countryCode,region,
      eligibility_confirmed:eligibilityConfirmed,dedicated_key_confirmed:dedicatedKeyConfirmed};setApiKey('');setApiSecret('');
    if(!secureContext||!connection?.credential_entry_enabled||!online||!eligibilityConfirmed||!dedicatedKeyConfirmed||!/^[A-Z]{2}$/.test(countryCode)||!region.trim())return;
    await action(async()=>{
      await request('/connections/kraken',credentials,true);
      await readConnection();
      if(mounted.current&&authorized.current)setNotice('Kraken connection verified. Refresh account data to review actual balances and open orders.');
    });
  }
  async function refreshAccount() {
    invalidateReview();
    await action(async()=>{
      const value=await request<KrakenAccountSnapshot>('/connections/kraken/account');
      if(!Number.isFinite(value.verified_at)||!Array.isArray(value.balances)||!Array.isArray(value.open_orders))throw new Error('Invalid account response');
      if(mounted.current&&authorized.current)setAccount(value);
    });
  }
  async function disconnect() {
    invalidateReview();
    await action(async()=>{
      await request('/connections/kraken/disconnect',{});
      if(mounted.current&&authorized.current){setConnection(null);setAccount(null);setApiKey('');setApiSecret('');setNotice('App credentials removed. Existing Kraken orders were not cancelled. Manage them directly at Kraken.');}
      await readConnection();
    });
  }
  async function validateOrder() {
    if(!canPreview)return;
    const proposed={symbol,side,quantity,limit_price:limitPrice};invalidateReview();
    await action(async()=>{
      const value=await request<KrakenOrderPreview>('/connections/kraken/preview',proposed);
      if(value.status!=='validated'||value.provider_validation!==true||!value.id||!Number.isFinite(value.expires_at)||value.quote_currency!=='USD'||value.side!==proposed.side||value.symbol!==proposed.symbol)throw new Error('Invalid order review');
      if(mounted.current&&authorized.current){setPreview(value);setResult(null);setNow(Date.now()/1000);setNotice('Kraken validated this exact order without submitting it. Review every amount before individual approval.');}
    });
  }
  async function approveOrder() {
    if(!canApprove||!preview)return;
    const reviewed=preview;setConfirmation('');
    await action(async()=>{
      let outcome:KrakenOrderResult;
      try {
        outcome=await request<KrakenOrderResult>('/connections/kraken/approve',{preview_id:reviewed.id,confirmation:CONFIRMATION});
        if(!['submitting','submitted','unknown','rejected','resolved'].includes(outcome.status)||!Array.isArray(outcome.order_ids))throw new Error('Unknown submission outcome');
      } catch(error) {
        // A timeout after submission may hide a real order. Never automatically
        // retry or permit a new review while the outcome remains ambiguous.
        outcome=error instanceof KrakenRequestError&&error.status>=400&&error.status<500?
          {id:reviewed.id,status:'rejected',order_ids:[],message:error.message}:
          {id:reviewed.id,status:'unknown',order_ids:[],message:'Submission outcome is unknown. Do not place another order. Check Kraken directly and reconcile this request before continuing.'};
      }
      if(mounted.current&&authorized.current){setResult({...outcome,order:reviewed});setPreview(null);setAccount(null);setNotice('');}
    });
  }
  async function reconcileOrder() {
    if(!result||!unresolved)return;
    const previous=result;
    await action(async()=>{
      const value=await request<KrakenOrderResult>('/connections/kraken/reconcile',{order_id:previous.id||previous.order.id});
      if(!['submitting','submitted','unknown','rejected','resolved'].includes(value.status)||!Array.isArray(value.order_ids))throw new Error('Invalid reconciliation response');
      if(mounted.current&&authorized.current){setResult({...value,order:previous.order});setAccount(null);}
    });
  }

  return <>
    <section className="panel" aria-label="Your Kraken account"><div className="panel-head"><div><span className="eyebrow">YOUR EXCHANGE ACCOUNT · RESTRICTED SPOT ACCESS</span><h2>Your Kraken account</h2></div><span className={'badge '+(connected?'live':'unavailable')}>{connected?'Connected':'Not connected'}</span></div>
      <div className="wallet-details">
        <p>This connects your own Kraken exchange account. Watching or connecting a public wallet does not link a Kraken account or authorize an order.</p>
        <p>Every real order needs a fresh, exact review and your individual approval. Autonomous trading, withdrawals and transfers are unavailable.</p>
        {!auth?<p>Sign in to manage your restricted account connection.</p>:<>
          {error&&<p className="negative" role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
          <p><strong>Real order submission: {submissionEnabled?'Enabled for individually approved orders':'Disabled by backend configuration or account permissions'}</strong></p>
          {connection?.requirements?.map(line=><p key={line}>{line}</p>)}
          {connected&&<><p>Connection verified: {date(connection!.connection?.verified_at||0)}</p><p>Verified permissions: {connection!.connection?.permissions?.join(', ')||'Unavailable'}</p><p>Removing this app’s credentials does not cancel existing real orders. They can remain active and fill at Kraken.</p><button type="button" className="danger" style={actionButtonStyle} disabled={busy||!online} onClick={disconnect}>Remove app credentials · keep existing orders</button></>}
          {!connected&&connection?.credential_entry_enabled&&secureContext&&<form autoComplete="off" onSubmit={event=>{event.preventDefault();connect()}}>
            <p>Create a new, dedicated Kraken Spot API key used only by this app. Reusing it in another app can cause conflicting API request nonces.</p>
            <p>Enable Query funds, Query open orders and trades, and Query closed orders and trades. Enable Modify orders and Close orders only if you want individually approved trading. Leave every other permission off, including withdrawals, funding, transfers, exports and WebSocket access. The server rejects excess permissions.</p>
            <p>Enter the dedicated key only in this authenticated form, never in chat.</p>
            <div className="settings-grid"><label>Kraken API key<input aria-label="Kraken API key" type="password" autoComplete="off" spellCheck={false} autoCapitalize="none" required value={apiKey} onChange={event=>setApiKey(event.target.value)} disabled={busy}/></label><label>Kraken API secret<input aria-label="Kraken API secret" type="password" autoComplete="off" spellCheck={false} autoCapitalize="none" required value={apiSecret} onChange={event=>setApiSecret(event.target.value)} disabled={busy}/></label></div>
            <div className="settings-grid"><label>Residence country · two-letter ISO code<input aria-label="Kraken residence country code" placeholder="Two-letter country code" value={countryCode} onChange={event=>setCountryCode(event.target.value.toUpperCase())} pattern="[A-Z]{2}" maxLength={2} required disabled={busy}/></label><label>State or province · country if none<input aria-label="Kraken residence region" value={region} onChange={event=>setRegion(event.target.value)} required maxLength={100} disabled={busy}/></label></div>
            <p><label><input type="checkbox" checked={eligibilityConfirmed} onChange={event=>setEligibilityConfirmed(event.target.checked)} required disabled={busy}/> I confirm that this Kraken account and spot product are permitted for my residence. Kraken remains the final authority on account and regional eligibility.</label></p>
            <p><label><input type="checkbox" checked={dedicatedKeyConfirmed} onChange={event=>setDedicatedKeyConfirmed(event.target.checked)} required disabled={busy}/> This is a newly dedicated API key used only in Market Sentinel AI.</label></p>
            <button className="primary" style={actionButtonStyle} disabled={busy||!online||!apiKey||!apiSecret||!eligibilityConfirmed||!dedicatedKeyConfirmed||!/^[A-Z]{2}$/.test(countryCode)||!region.trim()}>Verify restricted Kraken connection</button>
            <p>The server encrypts accepted credentials. This browser clears the entry fields after each attempt and does not store them. No real order is submitted by connecting.</p>
          </form>}
          {!connected&&(!connection?.credential_entry_enabled||!secureContext)&&<p>Credential entry is disabled until the secure backend connection flow is configured and this page uses a secure connection. No credentials are requested here while that gate is closed.</p>}
          <p><button type="button" className="secondary" style={actionButtonStyle} disabled={busy} onClick={refreshConnection}>Refresh connection status</button></p>
          {connected&&<p><button type="button" className="secondary" style={actionButtonStyle} disabled={busy||!online} onClick={refreshAccount}>Refresh balances and open orders</button></p>}
          {account&&<><h3>Kraken balances</h3><p>Verified {date(account.verified_at)} · {accountFresh?'recent account snapshot':'stale account snapshot; refresh before reviewing an order'}. Balances can change after this read.</p><div className="table-scroll"><table><thead><tr><th>Asset</th><th>Balance</th><th>Available</th></tr></thead><tbody>{account.balances.map(row=><tr key={row.asset}><td>{row.asset}</td><td>{row.balance}</td><td>{row.available}</td></tr>)}</tbody></table></div>{account.balances.length===0&&<p>Kraken returned no balances in this account response.</p>}
            <h3>Current open Kraken orders</h3><div className="table-scroll"><table><thead><tr><th>Order ID / status</th><th>Market / side</th><th>Quantity / executed</th><th>Limit price</th></tr></thead><tbody>{account.open_orders.map(row=><tr key={row.id}><td>{row.id} · {row.status}</td><td>{row.pair} · {row.side}</td><td>{row.quantity} / {row.executed}</td><td>{row.limit_price}</td></tr>)}</tbody></table></div>{account.open_orders.length===0&&<p>No open orders were returned in this snapshot. This does not establish that an earlier request was rejected or that no order has filled.</p>}<p>{account.fees_note}</p></>}
        </>}
      </div><div className="panel-foot">Free Render hosting can sleep or be unavailable. Orders already accepted by Kraken can stay active and fill while this app is offline. This app does not guarantee continuous monitoring, cancellation or protective exits. Kraken trading fees apply.</div>
    </section>

    {auth&&<section className="panel" aria-label="Individually approved Kraken limit order"><div className="panel-head"><div><span className="eyebrow">REAL FUNDS · ONE REVIEW, ONE APPROVAL</span><h2>Review a Kraken spot limit order</h2></div><span className={'badge '+(submissionEnabled?'wait':'unavailable')}>{submissionEnabled?'Individual approval required':'Submission disabled'}</span></div><div className="wallet-details">
      <p>These orders use your actual Kraken assets. A provider validation or risk PASS does not establish profitability or recommend trading.</p>
      <p>Confirm your real-capital profile and limits in Settings before creating a review. The initial hard maximum is 500 USD per order. Only currently verified Kraken USD spot markets can be reviewed.</p>
      <p>To investigate another asset, search Live Markets and select its Kraken USD market for detailed observation. Listings do not establish trading eligibility; the server checks actual pair rules, account permissions and your declared residence for each review. Coverage is limited by available markets and data.</p>
      {!connected&&<p>Verify your restricted Kraken account connection first.</p>}
      {connected&&!accountFresh&&<p>Refresh Kraken balances and open orders before creating a review. Account observations expire after 60 seconds.</p>}
      {connected&&!tradingPermission&&<p>The verified connection does not permit trading.</p>}
      {!submissionEnabled&&<p>Backend live-order submission is disabled. Any available validation creates no real order.</p>}
      {unresolved&&<p role="alert">A previous submission requires reconciliation. New order reviews are blocked. Check Kraken directly and reconcile the original request; refreshing an empty open-order list does not prove that no order filled.</p>}
      <form className="lab-form" autoComplete="off" onSubmit={event=>{event.preventDefault();validateOrder()}}>
        <label>USD spot market<select aria-label="Kraken real order market" value={symbol} onChange={event=>{setSymbol(event.target.value);invalidateReview()}} disabled={busy||unresolved}><option value="">Select an observed Kraken USD market</option>{markets.map(row=><option key={row.symbol} value={row.symbol} disabled={!row.ready}>{row.symbol}{row.ready?'':' · awaiting fresh verified data'}</option>)}</select></label>
        <label>Side<select aria-label="Kraken real order side" value={side} onChange={event=>{setSide(event.target.value as 'buy'|'sell');invalidateReview()}} disabled={busy||unresolved}><option value="buy">Buy with USD</option><option value="sell">Sell owned asset for USD</option></select></label>
        <label>Quantity · base asset units<input aria-label="Kraken real order quantity" inputMode="decimal" value={quantity} onChange={event=>{setQuantity(event.target.value);invalidateReview()}} pattern="[0-9]+(\.[0-9]+)?" required disabled={busy||unresolved}/></label>
        <label>Limit price · USD<input aria-label="Kraken real order limit price" inputMode="decimal" value={limitPrice} onChange={event=>{setLimitPrice(event.target.value);invalidateReview()}} pattern="[0-9]+(\.[0-9]+)?" required disabled={busy||unresolved}/></label>
        <button className="secondary" style={actionButtonStyle} disabled={!canPreview}>Validate and review · no order placed</button>
      </form>
      {preview&&<div aria-label="Exact Kraken order review"><h3>Exact order awaiting your approval</h3><PreviewDetails preview={preview}/><p>Review expires: {date(preview.expires_at)} · {reviewFresh?'review is current':'expired; validate a new review'}</p><form autoComplete="off" onSubmit={event=>{event.preventDefault();approveOrder()}}><label>Type {CONFIRMATION} to approve this exact real order<input aria-label="Real Kraken order approval phrase" autoComplete="off" spellCheck={false} value={confirmation} onChange={event=>setConfirmation(event.target.value)} disabled={busy||!submissionEnabled||!reviewFresh||!accountFresh}/></label><p><button className="danger" style={actionButtonStyle} disabled={!canApprove}>Place this real {preview.side} limit order</button></p></form></div>}
      {result&&<div role="status"><h3>{result.status==='submitted'?'Kraken accepted the order submission':result.status==='rejected'?'Order request rejected':result.status==='resolved'?'Kraken order reconciled to a terminal status':result.status==='submitting'?'Order submission is unresolved':'Order submission outcome unknown'}</h3><PreviewDetails preview={result.order}/><p>{result.message}</p>{result.order_ids.length>0&&<p>Kraken order IDs: {result.order_ids.join(', ')}</p>}<p>Submission is not proof of a fill. Review the actual account and order status at Kraken. No automatic retry is sent.</p>{unresolved&&<button type="button" className="secondary" style={actionButtonStyle} disabled={busy||!online} onClick={reconcileOrder}>Reconcile this order with Kraken · no resend</button>}</div>}
    </div></section>}
  </>;
}

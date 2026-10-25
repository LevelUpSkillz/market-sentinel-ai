'use client';

import {useEffect,useState} from 'react';
import InstrumentPanel from './instrument-panel';
import CapitalSettings,{RealPlanView,type RealCapitalProfile,type RealPlan} from './capital';
import KrakenAccount,{type KrakenSummary} from './kraken-account';
import type {Market} from './types';

export type LiveMoneyView='overview'|'trade'|'risk'|'connection';
type Order={id:string;status:string;symbol?:string;side?:string;quantity?:string;limit_price?:string;recorded_at?:number;submitted_at?:number;order_ids:string[];message:string};
const API=process.env.NEXT_PUBLIC_API_BASE||'';
const format=(value:unknown)=>value==null||value===''||!Number.isFinite(Number(value))?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(Number(value));
const date=(at?:number|null)=>at&&Number.isFinite(at)?new Date(at*1000).toLocaleString():'Unavailable';
const VIEWS:{id:LiveMoneyView;label:string;number:string}[]=[{id:'overview',label:'Overview',number:'01'},{id:'risk',label:'Budget & limits',number:'02'},{id:'trade',label:'Trade ticket',number:'03'},{id:'connection',label:'Connection',number:'04'}];

export default function LiveMoney({auth,online,effectsRunning,now,markets,stopped,busy,onStop,onMarkets,view,onView,plan,onRefreshPlan}:{
 auth:boolean;online:boolean;effectsRunning:boolean;now:number;markets:Market[];stopped:boolean;busy:boolean;onStop:()=>Promise<void>;onMarkets:()=>void;
 view:LiveMoneyView;onView:(value:LiveMoneyView)=>void;plan:RealPlan|null;onRefreshPlan:()=>Promise<void>;
}){
 const [summary,setSummary]=useState<KrakenSummary>({connection:null,account:null,unresolved:false});
 const [profile,setProfile]=useState<RealCapitalProfile|null>(null);
 const [orders,setOrders]=useState<Order[]>([]),[historyAt,setHistoryAt]=useState<number|null>(null),[historyError,setHistoryError]=useState('');
 const [revision,setRevision]=useState(0),[historyLoading,setHistoryLoading]=useState(false),[planBusy,setPlanBusy]=useState(false),[planError,setPlanError]=useState('');
 useEffect(()=>{
   if(!auth){setOrders([]);setHistoryAt(null);setHistoryError('');return}
   const controller=new AbortController();let active=true;const timer=setTimeout(()=>controller.abort(),15000);
   setHistoryLoading(true);
   fetch(API+'/api/connections/kraken/orders',{credentials:'include',cache:'no-store',signal:controller.signal}).then(async response=>{
     if(!response.ok)throw new Error('The saved order journal is unavailable. No exchange order was requested.');
     const value=await response.json();
     if(!Array.isArray(value.orders)||!Number.isFinite(value.as_of))throw new Error('The order journal response is unavailable.');
     if(active){setOrders(value.orders);setHistoryAt(value.as_of);setHistoryError('')}
   }).catch(error=>{if(active)setHistoryError((error as Error).name==='AbortError'?'Order journal request timed out.':(error as Error).message)}).finally(()=>{clearTimeout(timer);if(active)setHistoryLoading(false)});
   return()=>{active=false;controller.abort();clearTimeout(timer)};
 },[auth,revision,summary.unresolved]);
 const connected=auth&&summary.connection?.connected===true;
 const account=auth?summary.account:null;
 const accountFresh=online&&account!=null&&now-account.verified_at>=0&&now-account.verified_at<=60;
 const usdRows=account?.balances.filter(row=>row.asset==='USD'||row.asset==='ZUSD')||[];
 const usd=usdRows.length===1?usdRows[0].available:null;
 const held=account?.balances.filter(row=>Number.isFinite(Number(row.balance))&&Number(row.balance)!==0).length;
 const profileFresh=auth&&profile!=null&&!profile.stale&&now-profile.confirmed_at<86400&&Math.floor(now/86400)===Math.floor(profile.confirmed_at/86400);
 const stages=[{label:'Kraken account',value:connected?'Connected':'Connect account',ready:connected,view:'connection' as const},
  {label:'Budget & limits',value:profileFresh?'Confirmed':'Set or reconfirm',ready:profileFresh,view:'risk' as const},
  {label:'Order review',value:summary.unresolved?'Reconcile prior order':'Review before approval',ready:false,view:'trade' as const}];
 const blocked=!profileFresh||!accountFresh||stopped||summary.unresolved||!connected||!summary.connection?.connection?.can_trade||!summary.connection?.live_order_submission_enabled;
 return <div className="live-money-workspace">
  <InstrumentPanel title="Capital protection array" subtitle="A visual checklist for your Kraken account. Every real order still needs your exact approval." model={{kind:'capital',points:[],steps:[{label:'ACCOUNT',state:connected?'ready':'unknown'},{label:'BUDGET',state:profileFresh?'ready':'unknown'},{label:'SNAPSHOT',state:accountFresh?'ready':'unknown'},{label:'APPROVAL',state:stopped||summary.unresolved?'blocked':'unknown'}]}} running={effectsRunning} facts={[{label:'Account link',value:connected?'Connected':'Not connected'},{label:'Last available USD',value:format(usd),note:account?accountFresh?'Recent Kraken snapshot':'Old snapshot · refresh below':'Read balances explicitly below'},{label:'Risk budget',value:profileFresh?'Confirmed':'Needs confirmation',note:'Declared budget, not an exchange balance'},{label:'Execution control',value:stopped?'Paused':summary.unresolved?'Reconciliation required':'Your approval required'}]} caption="The shield and orbit motion are decorative. Readiness is not an order or a profit forecast. No account balance is requested by this display; refresh balances in the account panel. USD, USDC and CAD are never combined." source={'Source: current account setup / declared budget · Kraken account snapshot '+date(account?.verified_at)}/>

  <section className="capital-hero" aria-label="Live money control center"><div><span className="eyebrow">YOUR CAPITAL. YOUR APPROVAL.</span><h2>A clear view of your<br/><em>real money.</em></h2><p>Read your Kraken account, define your limits, then review one spot order at a time. Every real order needs your approval.</p><div className="capital-hero-status"><span className={'status-dot '+(connected?'is-live':'')}/>{connected?'Kraken connected':'Kraken connection required'}<span className="capital-divider"/>{stopped?'New trades paused':summary.unresolved?'Order needs reconciliation':'Manual approval only'}</div></div>
   <div className="capital-command"><span className="eyebrow">EXECUTION CONTROL</span><strong>{stopped?'Trading paused':summary.unresolved?'Reconciliation required':blocked?'Setup required':'Ready for your review'}</strong><p>{stopped?'New app orders are blocked. Existing Kraken orders are unaffected.':summary.unresolved?'Inspect the original request. The app will not resend it.':'Linking an account never starts trading. No withdrawal or autonomous execution.'}</p><button className={stopped?'secondary':'danger'} disabled={!auth||!online||busy} onClick={onStop}>{stopped?'Resume new trades':'Pause new trades'}</button></div>
  </section>
  <nav className="desk-tabs" aria-label="Live Money sections">{VIEWS.map(item=><button key={item.id} type="button" aria-current={view===item.id?'page':undefined} onClick={()=>onView(item.id)}><span>{item.number}</span>{item.label}</button>)}</nav>
  {view==='overview'&&<>
   <div className="capital-metrics" aria-label="Actual Kraken account summary"><div><small>Available USD cash</small><strong>{format(usd)}</strong><span>{account?'Kraken · '+(accountFresh?'recent snapshot':'refresh needed'):'Read your balances below'}</span></div><div><small>Assets with a balance</small><strong>{held??'—'}</strong><span>Asset counts, no inferred valuation</span></div><div><small>Open Kraken orders</small><strong>{account?.open_orders.length??'—'}</strong><span>{account?'Returned in account snapshot':'Not loaded'}</span></div><div><small>Your declared budget</small><strong>{auth?format(profile?.capital_usd):'—'}</strong><span>{profileFresh?'Confirmed · not an exchange balance':'Budget needs confirmation'}</span></div></div>
   <div className="guided-path" aria-label="Live Money readiness">{stages.map((stage,index)=><button type="button" key={stage.label} onClick={()=>onView(stage.view)}><span className={'path-number '+(stage.ready?'is-complete':'')}>{stage.ready?'✓':String(index+1).padStart(2,'0')}</span><div><small>{stage.label}</small><strong>{stage.value}</strong></div><span aria-hidden="true">↗</span></button>)}</div>
  </>}
  <div hidden={view==='risk'}><KrakenAccount auth={auth} online={online} view={view==='risk'?'overview':view} onSummary={setSummary} liveMarkets={markets} stopped={stopped} riskReady={profileFresh}/></div>
  <div hidden={view!=='risk'}><CapitalSettings auth={auth} online={online} onProfile={setProfile}/></div>
  {view==='trade'&&<>
   {plan&&<section className="research-handoff"><div><span className="eyebrow">RESEARCH → CAPITAL PLANNING</span><h3>Your research sizing</h3><p>This separate plan places no order and attaches no stop to a Kraken order.</p></div><button className="secondary" disabled={!auth||!online||planBusy} onClick={async()=>{setPlanBusy(true);setPlanError('');try{await onRefreshPlan()}catch(error){setPlanError((error as Error).message)}finally{setPlanBusy(false)}}}>Refresh real-capital plan</button>{planError&&<p role="alert">{planError}</p>}<div className="wide"><RealPlanView plan={plan}/></div></section>}
   <div className="desk-note"><div><strong>Need another token?</strong><p>Add its Kraken USD detailed book in Live Markets, then refresh Connection. Listings and indicative prices alone cannot authorize an order.</p></div><button type="button" className="secondary" onClick={onMarkets}>Explore live markets ↗</button></div>
  </>}
  {(view==='overview'||view==='trade')&&<section className="panel" aria-label="Real order journal"><div className="panel-head"><div><span className="eyebrow">YOUR APP REQUESTS · LATEST 50</span><h2>Real order journal</h2></div><button type="button" className="secondary compact" disabled={!auth||!online||historyLoading} onClick={()=>setRevision(value=>value+1)}>Refresh order journal</button></div>
   <div className="wallet-details"><p>Saved app requests, including reviews that never submitted. These are not your complete Kraken trade history or proof of fills.</p></div>
   {historyError&&<p className="error-banner" role="status">{historyError}</p>}
   {orders.length?<div className="table-scroll"><table><thead><tr><th>Market / side</th><th>Quantity</th><th>Limit · USD</th><th>Request status</th><th>Recorded</th></tr></thead><tbody>{orders.map(order=><tr key={order.id}><td><strong>{order.symbol} · {order.side}</strong><small className="source-detail">{order.order_ids?.length?'Kraken ID: '+order.order_ids.join(', '):'No confirmed exchange order ID'}</small></td><td className="mono">{order.quantity}</td><td className="mono">{order.limit_price}</td><td><span className={'badge '+(['unknown','submitting'].includes(order.status)?'no-go':'wait')}>{order.status}</span><small className="source-detail">{order.status==='validated'?'Review only · not sent':order.status==='resolved'?'Terminal exchange record found':'Check fills directly in Kraken'}</small></td><td>{date(order.submitted_at||order.recorded_at)}</td></tr>)}</tbody></table></div>:<div className="empty"><h3>{historyLoading?'Reading saved requests…':'No real order requests loaded'}</h3><p>{auth?'Your app reviews and submitted requests will appear here.':'Sign in to read your own order journal.'}</p></div>}
   <div className="panel-foot"><small>Source: Market Sentinel order journal · {date(historyAt)}. Account data source: Kraken · {date(account?.verified_at)}.</small></div>
  </section>}
  <div className="live-money-footer"><span>SPOT ONLY</span><span>EXPLICIT APPROVAL</span><span>NO WITHDRAWALS</span><p>Free hosting can sleep. Inspect fills and manage existing orders directly in Kraken. Exchange fees apply.</p></div>
 </div>;
}

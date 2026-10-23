'use client';
import { useEffect, useState } from 'react';

type Connection = {provider:string;status:string;connected:boolean;order_submission_enabled:boolean;withdrawals_enabled:boolean;app_hosting_plan:string;trading_fees:string;requirements:string[];documentation:string;fees_url:string};
const BASE=process.env.NEXT_PUBLIC_API_BASE||'';
export default function ExchangeConnection({auth}:{auth:boolean}){
  const [data,setData]=useState<Connection|null>(null),[error,setError]=useState(''),[revision,setRevision]=useState(0);
  useEffect(()=>{
    if(!auth){setData(null);setError('');return}
    const controller=new AbortController();let active=true;const timer=setTimeout(()=>controller.abort(),15000);
    fetch(BASE+'/api/connections',{credentials:'include',signal:controller.signal}).then(async r=>{if(!r.ok)throw new Error('Connection status is unavailable.');const value:Connection=await r.json();if(value.provider!=='kraken'||!Array.isArray(value.requirements))throw new Error('Connection status is unavailable.');if(active){setData(value);setError('')}}).catch(e=>{if(active){setData(null);setError((e as Error).message)}}).finally(()=>clearTimeout(timer));
    return()=>{active=false;controller.abort();clearTimeout(timer)};
  },[auth,revision]);
  return <section className="panel" aria-label="Kraken account connection"><div className="panel-head"><div><span className="eyebrow">PREFERRED EXCHANGE · YOUR APPROVAL FOR EACH FUTURE ORDER</span><h2>Kraken account connection</h2></div><span className="badge unavailable">{data?'Awaiting provider setup':'Not connected'}</span></div><div className="wallet-details"><p>Kraken is selected for future account linking. Your real-capital planning profile works independently; it does not verify an exchange balance or connect your account.</p>{!auth?<p>Sign in to see connection requirements.</p>:error?<p role="status">{error}</p>:data?<><p><strong>Account connected: {data.connected?'Yes':'No'} · Order submission: {data.order_submission_enabled?'Enabled':'Disabled'}</strong></p><p>Secure OAuth linking requires a Kraken-approved app. This workspace has no approved OAuth client configured, so no sign-in connection or order submission is currently available.</p>{data.requirements.map(line=><p key={line}>{line}</p>)}<p>{data.trading_fees} App hosting remains on the free configuration.</p><p><a className="text-button" href={data.documentation} target="_blank" rel="noreferrer">Kraken developer setup ↗</a></p><p><a className="text-button" href={data.fees_url} target="_blank" rel="noreferrer">Review Kraken fees ↗</a></p></>:<p>Loading verified connection status…</p>}{auth&&<button className="secondary compact" onClick={()=>setRevision(v=>v+1)}>Refresh connection status</button>}</div><div className="panel-foot">No exchange secrets or recovery phrases are requested here. A future order must have an explicit review and confirmation in this app. Withdrawal and transfer operations are unavailable.</div></section>;
}

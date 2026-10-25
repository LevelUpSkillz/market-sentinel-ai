'use client';
import type {Dashboard} from './types';
import {freshBook,timestamp} from './instrument-model';
export default function ProviderDiagnostics({data,online,now}:{data:Dashboard|null;online:boolean;now:number}) {
  const clock=Math.max(now,Date.now()/1000);
  return <details className="provider-diagnostics" aria-label="Provider diagnostics"><summary>Technical data diagnostics</summary><section className="panel provider-health" aria-label="Data connection status"><div className="panel-head"><div><span className="eyebrow">OPTIONAL TECHNICAL VIEW</span><h2>Provider diagnostics</h2></div></div><div className="health-list">{['kraken','hyperliquid','coinbase'].map(name=>{
    const provider=data?.providers[name],books=(data?.markets||[]).filter(book=>book.provider===name),fresh=books.filter(book=>freshBook(book,online,clock)).length;
    const events=books.map(book=>book.source_at).filter((at):at is number=>at!=null&&Number.isFinite(at)&&at>0);const latest=events.length?Math.max(...events):null;
    const state=provider?.state==='connected'?online?'Connected':'Last reported connected':provider?.state||'Unavailable';
    return <div key={name}><span className="provider-monogram">{name[0].toUpperCase()}</span><strong>{name}</strong><div className="diagnostic-status"><span>{state}</span><small>{fresh} / {books.length} books within 5s</small><small>{latest!=null?'Latest book event '+(clock-latest>=0?Math.floor(clock-latest)+'s ago':'has clock difference'):'No book event loaded'}</small><small>Last message {timestamp(provider?.last_message_at)}</small></div></div>;
  })}</div><div className="wallet-details"><p>Connection state and book age are separate. A market can be quiet while the stream stays connected. Prices older than the freshness limit still fail the trade checks.</p><small>Source: provider status and individual source timestamps · API received {timestamp(data?.as_of)}. Retained status is historical when the API is offline.</small></div></section></details>;
}

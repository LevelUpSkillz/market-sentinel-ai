'use client';
import {useEffect,useState} from 'react';
import type {Dashboard} from './types';
import {freshBook,shown} from './instrument-model';
type ObservedQuote={id:string;symbol:string;provider:string;quote:string;price:string;source_at:number;received_at:number;changed:boolean};
export default function OrbitalQuotes({data,online}:{data:Dashboard|null;online:boolean}) {
  const [observed,setObserved]=useState<Record<string,ObservedQuote>>({});
  useEffect(()=>{
    if(!data){setObserved({});return}
    const now=Date.now()/1000;
    setObserved(previous=>{let changed=false;const next={...previous};for(const base of ['BTC','ETH','SOL']){
      const row=data.markets.find(m=>m.provider==='kraken'&&m.symbol===base+'-USD'&&m.received_at>0)||data.markets.find(m=>m.symbol.startsWith(base+'-')&&m.received_at>0);
      if(!row||!freshBook(row,online,now)||row.mid==null||!Number.isFinite(Number(row.mid))||Number(row.mid)<=0)continue;
      const id=row.provider+'|'+row.symbol,prior=previous[base];if(prior?.id===id&&prior.source_at>=row.source_at!)continue;
      next[base]={id,symbol:row.symbol,provider:row.provider,quote:row.quote,price:row.mid,source_at:row.source_at!,received_at:row.received_at,changed:prior?.id===id&&prior.price!==row.mid};changed=true;
    }return changed?next:previous});
  },[data,online]);
  const now=Date.now()/1000,quotes=data?Object.values(observed).filter(q=>data.markets.some(m=>m.provider+'|'+m.symbol===q.id)):[];
  return <div className="orbital-quote-beacons" aria-label="Observed market quotes">{quotes.map(q=>{const current=data?.markets.find(m=>m.provider+'|'+m.symbol===q.id),fresh=!!current&&freshBook(current,online,now)&&now-q.source_at>=-1&&now-q.source_at<=5&&now-q.received_at>=0&&now-q.received_at<=5;return <div key={q.id+q.source_at} className={'quote-beacon '+(fresh?'is-live':'is-retained')+(fresh&&q.changed&&now-q.source_at<2.5?' is-new':'')}><div><strong>{q.symbol.split('-')[0]}</strong><span>{fresh?'Live':'Last observed'}</span></div><p>{shown(q.price,9)} <small>{q.quote}</small></p><small>{q.provider} · {q.symbol.endsWith('-PERP')?'perp':'spot'} · {new Date(q.source_at*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</small><small>Age {Math.max(0,Math.floor(now-q.source_at))}s · book midpoint</small></div>})}{!quotes.length&&<span className="orbital-quotes-empty">Verified quote markers appear when source data arrives.</span>}</div>;
}

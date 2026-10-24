'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { Dashboard, Market, Paper, Signal } from './types';
import ProviderMonitor from './provider-monitor';
import {tokenName,tokenSymbol} from './token-labels';
import PriceHistory, {type ChartMarker} from './price-history';

type Props = {advanced?:boolean;canAct?:boolean;markets:Market[];online:boolean;now:number;auth:boolean;trades?:Dashboard['trades'];paper?:Paper[];signals?:Signal[];requested?:{provider:string;symbol:string}|null;onResearch?:(market:Market)=>void;onPractice?:(market:Market)=>void;onSelectMarket?:(market:Market)=>void;onTraders?:(market:Market)=>void};
type Sample = {at:number;received_at:number;value:number;bid:string|null;ask:string|null;spread_bps:string|null;break_before:boolean;change:'up'|'down'|null};
const MAX_POINTS = 180;
const MAX_WINDOW_SECONDS = 600;
const MAX_CONNECTED_GAP = 5;
const WIDTH = 980, HEIGHT = 288, LEFT = 72, RIGHT = 20, TOP = 24, BOTTOM = 42;

const keyOf = (market:Market) => market.provider+'|'+market.symbol;
const n = (value:unknown,digits=2) => value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumFractionDigits:digits});
const price = (value:unknown) => value==null||!Number.isFinite(Number(value))?'—':Number(value).toLocaleString('en-US',{maximumSignificantDigits:9});
const date = (value:number|null|undefined) => value!=null&&Number.isFinite(value)?new Date(value*1000).toLocaleString():'Unavailable';
const time = (value:number) => new Date(value*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
const age = (value:number|null|undefined,now:number) => value!=null&&value>0?Math.max(0,Math.floor(now-value))+'s':'Unavailable';

function fresh(market:Market|undefined,online:boolean,auth:boolean,now:number){
  return !!market&&auth&&online&&market.status==='live'&&market.source_at!=null&&
    Number.isFinite(market.source_at)&&Number.isFinite(market.received_at)&&
    now-market.source_at>=-1&&now-market.source_at<=5&&now-market.received_at>=0&&now-market.received_at<=5&&
    ['crc32_verified','ordered_stream'].includes(market.integrity)&&market.mid!=null&&Number.isFinite(Number(market.mid))&&Number(market.mid)>0;
}

export default function LiveMarketChart({markets,online,now,auth,trades=[],paper=[],signals=[],requested,onResearch,onPractice,onTraders,onSelectMarket,canAct=true,advanced=false}:Props){
  const [selected,setSelected]=useState('');
  const [view,setView]=useState('history');
  const [histories,setHistories]=useState<Record<string,Sample[]>>({});
  const [hover,setHover]=useState<number|null>(null);
  const [flash,setFlash]=useState<{id:number;direction:'up'|'down'}|null>(null);
  const historyCache=useRef<Record<string,Sample[]>>({});
  const manuallySelected=useRef(false);
  const broken=useRef(new Set<string>());
  const lastPulsed=useRef(new Map<string,number>());
  const previousSelection=useRef('');
  const appliedRequest=useRef<Props['requested']>(null);
  useEffect(()=>{if(auth&&requested&&appliedRequest.current!==requested&&markets.some(m=>m.provider===requested.provider&&m.symbol===requested.symbol)){appliedRequest.current=requested;manuallySelected.current=true;setSelected(requested.provider+'|'+requested.symbol);setHover(null)}},[requested,auth,markets]);
  const clock=Math.max(now,Date.now()/1000);
  const available=auth?markets.filter(m=>advanced||m.instrument==='spot'&&m.quote==='USD'):[];
  const options=useMemo(()=>{if(advanced)return [...markets].sort((a,b)=>a.symbol.localeCompare(b.symbol)||a.provider.localeCompare(b.provider));const unique=new Map<string,Market>();for(const m of [...markets].filter(m=>m.instrument==='spot'&&m.quote==='USD').sort((a,b)=>(a.provider==='kraken'?0:1)-(b.provider==='kraken'?0:1))){if(!unique.has(m.symbol))unique.set(m.symbol,m)}return [...unique.values()].sort((a,b)=>tokenName(a.symbol).localeCompare(tokenName(b.symbol)))},[markets,advanced]);

  useEffect(()=>{
    if(!auth){setSelected('');setHistories({});historyCache.current={};manuallySelected.current=false;setHover(null);setFlash(null);broken.current.clear();lastPulsed.current.clear();previousSelection.current='';return}
    const currentNow=Math.max(now,Date.now()/1000);
    const validKeys=new Set(markets.map(keyOf));
    const currentSelection=options.find(market=>keyOf(market)===selected);
    const freshSelection=options.find(market=>fresh(market,online,auth,currentNow));
    const fallback=freshSelection||options.find(market=>market.received_at>0)||options[0];
    const keepSelection=!!currentSelection&&(manuallySelected.current||!!historyCache.current[selected]?.length||fresh(currentSelection,online,auth,currentNow)||!freshSelection);
    const nextSelection=keepSelection?selected:fallback?keyOf(fallback):'';
    if(nextSelection!==selected)setSelected(nextSelection);
    // Compute observations outside a state updater so StrictMode replays cannot
    // erase a disconnect boundary or consume the same source point twice.
    {
      const previous=historyCache.current;
      let changed=false;
      const next:Record<string,Sample[]>={};
      for(const market of markets){
        const key=keyOf(market),existing=previous[key]||[];
        if(!fresh(market,online,auth,currentNow)){
          broken.current.add(key);
          if(existing.length)next[key]=existing;
          continue;
        }
        const at=market.source_at!,last=existing.at(-1);
        if(last&&at<=last.at){
          // API responses and heartbeats cannot manufacture a provider event.
          next[key]=existing;
          continue;
        }
        const value=Number(market.mid);
        const point:Sample={at,received_at:market.received_at,value,bid:market.bid,ask:market.ask,spread_bps:market.spread_bps,
          break_before:!last||broken.current.has(key)||at-last.at>MAX_CONNECTED_GAP,
          change:last&&last.value!==value?(value>last.value?'up':'down'):null};
        next[key]=[...existing.filter(sample=>sample.at>=at-MAX_WINDOW_SECONDS),point].slice(-MAX_POINTS);
        broken.current.delete(key);changed=true;
      }
      if(Object.keys(previous).some(key=>!validKeys.has(key)))changed=true;
      for(const key of broken.current){if(!validKeys.has(key))broken.current.delete(key)}
      if(changed){historyCache.current=next;setHistories(next)}
    }
  },[markets,online,auth,now]);

  const missingRequest=!!(auth&&requested&&!available.some(m=>m.provider===requested.provider&&m.symbol===requested.symbol));
  const market=missingRequest?undefined:available.find(item=>keyOf(item)===selected);
  const samples=auth&&!missingRequest?(histories[selected]||[]):[];
  const latest=samples.at(-1);
  const markers:ChartMarker[]=useMemo(()=>{if(!auth||!market)return [];return [
    ...trades.filter(t=>t.provider===market.provider&&t.symbol===market.symbol&&Number.isFinite(t.source_at)&&t.source_at<=clock+1&&Number(t.price)>0&&Number(t.quantity)>0).map(t=>({at:t.source_at,price:Number(t.price),kind:'trade' as const,label:'Recorded '+t.side+' trade · '+t.provider})),
    ...paper.filter(p=>p.provider===market.provider&&p.symbol===market.symbol&&Number.isFinite(p.opened_at)&&p.opened_at<=clock+1&&Number(p.entry_price)>0).map(p=>({at:p.opened_at,price:Number(p.entry_price),kind:'practice' as const,label:'Practice entry · virtual money'})),
    ...signals.flatMap(s=>s.snapshots.filter(m=>m.provider===market.provider&&m.symbol===market.symbol&&m.source_at!=null&&m.source_at<=clock+1&&['crc32_verified','ordered_stream'].includes(m.integrity)&&Number(m.mid)>0).map(m=>({at:m.source_at!,price:Number(m.mid),kind:'signal' as const,label:'Recorded '+s.decision+' research signal · '+s.strategy_version})))
  ]},[auth,market,trades,paper,signals,clock]);
  const isFresh=fresh(market,online,auth,clock);
  const status=isFresh?'live':market?.received_at?'stale':'unavailable';

  useEffect(()=>{
    if(previousSelection.current!==selected){
      previousSelection.current=selected;
      if(latest)lastPulsed.current.set(selected,latest.at);
      setFlash(null);setHover(null);return;
    }
    if(!isFresh||!latest){setFlash(null);return}
    if((lastPulsed.current.get(selected)??-Infinity)>=latest.at)return;
    lastPulsed.current.set(selected,latest.at);
    if(!latest.change){setFlash(null);return}
    setFlash({id:latest.at,direction:latest.change});
    const timer=setTimeout(()=>setFlash(null),700);
    return()=>clearTimeout(timer);
  },[selected,latest,isFresh]);

  const plot=useMemo(()=>{
    if(samples.length<2)return null;
    const first=samples[0],last=samples[samples.length-1];
    const minimum=Math.min(...samples.map(sample=>sample.value)),maximum=Math.max(...samples.map(sample=>sample.value));
    const padding=(maximum-minimum)*.12||Math.max(Math.abs(minimum)*.0005,Number.MIN_VALUE);
    const low=minimum-padding,high=maximum+padding;
    const x=(at:number)=>LEFT+(at-first.at)/Math.max(last.at-first.at,.001)*(WIDTH-LEFT-RIGHT);
    const y=(value:number)=>TOP+(high-value)/(high-low)*(HEIGHT-TOP-BOTTOM);
    const points=samples.map(sample=>({...sample,x:x(sample.at),y:y(sample.value)}));
    const path=points.map((point,index)=>(index===0||point.break_before?'M':'L')+point.x.toFixed(2)+','+point.y.toFixed(2)).join(' ');
    const ticks=Array.from({length:5},(_,index)=>({value:high-(high-low)*index/4,y:TOP+(HEIGHT-TOP-BOTTOM)*index/4}));
    return {path,points,ticks,minimum,maximum,first,last,x,y,change:(last.value/first.value-1)*100};
  },[samples]);

  const cursor=plot&&hover!=null?plot.points[Math.min(Math.max(0,hover),plot.points.length-1)]:null;
  const windowLabel=plot?time(plot.first.at)+' → '+time(plot.last.at):latest?time(latest.at):'Awaiting provider observations';

  return <section id="market-price-chart" className="panel live-market-panel" aria-label="Live market chart">
    <div className="panel-head"><div><span className="eyebrow">LIVE PRICES + EXCHANGE HISTORY</span><h2>{market?tokenName(market.symbol):'Market chart'}</h2></div><div className="live-market-controls"><span className={'badge '+status}>{status}</span><select aria-label="Live chart market" value={market?selected:''} onChange={event=>{manuallySelected.current=true;setSelected(event.target.value);setHover(null);const choice=markets.find(m=>keyOf(m)===event.target.value);if(choice)onSelectMarket?.(choice)}} disabled={!auth||!available.length}>
      {(!available.length||missingRequest)&&<option value="">{missingRequest?requested?.symbol+' · detailed book needed':'No detailed markets loaded'}</option>}{auth&&options.map(item=><option key={keyOf(item)} value={keyOf(item)}>{tokenName(item.symbol)}{advanced?' · '+item.provider+' · '+item.instrument:''}</option>)}
    </select></div></div>
    <div className="live-market-summary"><div><span className="live-market-source">{market?tokenName(market.symbol)+(market.quote==='USD'?' · price in US dollars':' · research quote in '+market.quote):missingRequest?requested?.symbol+' · add its detailed book below':'Sign in to connect to market data'}</span><div className="live-market-price-line"><strong data-testid="live-chart-price" key={flash?.id??'stable'} className={'live-market-price '+(isFresh&&flash?'is-'+flash.direction:'')}>{price(latest?.value)}<small>{market?.quote||''}</small></strong>{plot&&<span className={'live-market-window-change '+(plot.change<0?'is-down':'is-up')}>{plot.change>0?'+':''}{n(plot.change,3)}%<small>observed window</small></span>}</div></div>
      <div className="live-market-top-book"><div><small>Buyers offer (bid)</small><strong>{price(latest?.bid)} <small>{market?.quote}</small></strong></div><div><small>Sellers ask (ask)</small><strong>{price(latest?.ask)} <small>{market?.quote}</small></strong></div><div><small>Spread</small><strong>{n(latest?.spread_bps,3)} <small>bps</small></strong></div></div>
    </div>
    <div className="live-market-chart-meta"><span><strong data-testid="live-chart-sample-count">{samples.length}</strong> distinct provider observations</span><span>{windowLabel}</span><span>{isFresh?'Receiving verified book observations':market?.received_at?'Retained observations · feed stale or paused':'Waiting for verified book data'}</span></div>
    <div className="chart-view-switch"><label>Chart view<select aria-label="Chart view" value={view} onChange={e=>setView(e.target.value)}><option value="history">Price history</option><option value="ticks">Live ticks</option></select></label><span>{view==='history'?'A ready-to-read exchange history, refreshed every 30 seconds.':'Fresh observations collected while this page is open.'}</span></div>
    {view==='history'?<PriceHistory provider={market?.provider||''} symbol={market?.symbol||''} auth={auth} online={online} now={now} markers={markers}/>:plot?<div className="live-market-plot">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={'Observed midpoint prices for '+(market?.symbol||'selected market')+'. Source timestamps on the horizontal axis; gaps break the line.'} tabIndex={0}
        onPointerMove={event=>{
          const bounds=event.currentTarget.getBoundingClientRect();
          const at=plot.first.at+((event.clientX-bounds.left)/bounds.width*WIDTH-LEFT)/(WIDTH-LEFT-RIGHT)*(plot.last.at-plot.first.at);
          let closest=0;
          for(let index=1;index<plot.points.length;index++)if(Math.abs(plot.points[index].at-at)<Math.abs(plot.points[closest].at-at))closest=index;
          setHover(closest);
        }} onPointerLeave={()=>setHover(null)} onBlur={()=>setHover(null)} onKeyDown={event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();setHover(previous=>Math.min(plot.points.length-1,Math.max(0,(previous??plot.points.length-1)+(event.key==='ArrowLeft'?-1:1))))}else if(event.key==='Escape')setHover(null)}}>
        {plot.ticks.map((tick,index)=><g key={index}><line className="live-market-grid" x1={LEFT} x2={WIDTH-RIGHT} y1={tick.y} y2={tick.y}/><text className="live-market-axis" x={LEFT-10} y={tick.y+4} textAnchor="end">{price(tick.value)}</text></g>)}
        <path data-testid="live-chart-line" d={plot.path} className={'live-market-line '+(!isFresh?'is-stale':'')} fill="none"/>
        {plot.points.filter((point,index)=>point.break_before||index===plot.points.length-1).map(point=><circle key={point.at} className={'live-market-point '+(isFresh&&point.at===plot.last.at?'is-current':'')} cx={point.x} cy={point.y} r={point.at===plot.last.at?4:2}/>) }
        {cursor&&<g><line className="live-market-crosshair" x1={cursor.x} x2={cursor.x} y1={TOP} y2={HEIGHT-BOTTOM}/><circle className="live-market-cursor" cx={cursor.x} cy={cursor.y} r="4"/></g>}
        <text className="live-market-axis" x={LEFT} y={HEIGHT-14}>{time(plot.first.at)}</text><text className="live-market-axis" x={(LEFT+WIDTH-RIGHT)/2} y={HEIGHT-14} textAnchor="middle">{time((plot.first.at+plot.last.at)/2)}</text><text className="live-market-axis" x={WIDTH-RIGHT} y={HEIGHT-14} textAnchor="end">{time(plot.last.at)}</text>
      </svg>
      {cursor&&<div className="live-market-tooltip" style={{left:Math.max(25,Math.min(78,cursor.x/WIDTH*100))+'%'}}><strong>{price(cursor.value)} {market?.quote}</strong><small>Source {date(cursor.at)}</small></div>}
      <div className="live-market-plot-foot"><span>Live book midpoints · missing observations leave gaps</span><span>Keyboard: ← / → inspect observed points</span></div>
    </div>:<div className="empty live-market-empty"><h3>{!auth?'Sign in to view the live chart':samples.length?'Waiting for the next provider observation':'Waiting for verified market evidence'}</h3><p>The chart appears after two distinct, fresh provider timestamps. A successful API response or heartbeat does not add a price point.</p></div>}
    {market&&<ProviderMonitor markets={markets} symbol={market.symbol} online={online} now={now} trades={trades}/>}
    {market&&<div className="chart-next-steps" aria-label="Research this market"><div><strong>{tokenName(market.symbol)} · choose your next step</strong><p>Choose a next step. These buttons open research or a plan; they place no trade.</p></div><div><button className="secondary" onClick={()=>onResearch?.(market)}>Research this token →</button><button className="secondary" onClick={()=>onTraders?.(market)}>Public trader actions →</button>{canAct&&<button className="primary" disabled={market.instrument!=='spot'||market.quote!=='USD'} onClick={()=>onPractice?.(market)}>Plan with practice money →</button>}</div></div>}
    <details className="chart-source-details"><summary>Data source and update times</summary><p className="source-market-reference">Market reference: {market?.symbol||'unavailable'} · {market?.provider||'unavailable'}</p><div className="live-market-provenance"><div><small>Source event</small><strong>{date(latest?.at)}</strong><small>Age {age(latest?.at,clock)}</small></div><div><small>Received by backend</small><strong>{date(latest?.received_at)}</strong><small>Age {age(latest?.received_at,clock)}</small></div><div><small>Integrity / cadence</small><strong>{market?.integrity||'Unavailable'}</strong><small>Visible dashboard refresh: 2 seconds · source events vary</small></div></div>
    <div className="panel-foot live-market-foot"><span>Source: {market?.provider||'unavailable'} · {market?.quote||'quote currency unavailable'} · up to {MAX_POINTS} actual observations over ten minutes. Prices stop updating when evidence becomes stale. This chart shows sampled market observations, not a forecast or a guaranteed execution price.</span></div>
    </details>
  </section>;
}

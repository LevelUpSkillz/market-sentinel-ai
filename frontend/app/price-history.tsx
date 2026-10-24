'use client';

import {useEffect,useMemo,useRef,useState} from 'react';
export type ChartMarker={at:number;price:number;kind:'trade'|'signal'|'practice';label:string};
type Candle={at:number;open:string;high:string;low:string;close:string;volume?:string;closed:boolean};
type History={provider:string;symbol:string;interval_minutes:number;received_at:number;source_at:number;candles:Candle[];executable:false};
const px=(n:number)=>n.toLocaleString('en-US',{maximumSignificantDigits:8});
const axisPrice=(n:number)=>n!==0&&(Math.abs(n)<.001||Math.abs(n)>=10000000)?n.toExponential(2):n.toLocaleString('en-US',{maximumSignificantDigits:6});
const time=(n:number,dated=false)=>new Date(n*1000).toLocaleString([],dated?{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}:{hour:'2-digit',minute:'2-digit'});
const LEFT=74,RIGHT=18,TOP=22,PRICE_BOTTOM=240,VOLUME_TOP=270,VOLUME_HEIGHT=46,HEIGHT=352;

function verified(value:History,provider:string,symbol:string,interval:number,now:number) {
 if(value.provider!==provider||value.symbol!==symbol||value.interval_minutes!==interval||value.executable!==false||
   !Number.isFinite(value.received_at)||value.received_at>now+1||!Number.isFinite(value.source_at)||
   !Array.isArray(value.candles)||value.candles.length<2||value.candles.length>180)return false;
 return value.candles.every((c,i)=>{
  const o=Number(c.open),h=Number(c.high),l=Number(c.low),close=Number(c.close);
  return Number.isFinite(c.at)&&c.at>0&&c.at<=now+1&&c.at%(interval*60)===0&&(!i||c.at>value.candles[i-1].at)&&
   [c.open,c.high,c.low,c.close].every(v=>v!==null&&v!==''&&Number.isFinite(Number(v))&&Number(v)>0)&&
   l<=Math.min(o,close)&&h>=Math.max(o,close)&&typeof c.closed==='boolean'&&
   (!c.closed||c.at+interval*60<=now+1)&&
   (c.volume==null||c.volume!==''&&Number.isFinite(Number(c.volume))&&Number(c.volume)>=0);
 })&&value.source_at===value.candles.at(-1)!.at;
}

export default function PriceHistory({provider,symbol,auth,online,now,markers=[]}:{provider:string;symbol:string;auth:boolean;online:boolean;now:number;markers?:ChartMarker[]}) {
 const frame=useRef<HTMLDivElement>(null),[width,setWidth]=useState(980);
 const [interval,setIntervalMinutes]=useState(1),[data,setData]=useState<History|null>(null),[error,setError]=useState('');
 const [style,setStyle]=useState('line'),[cursor,setCursor]=useState<number|null>(null),[count,setCount]=useState(180),[offset,setOffset]=useState(0);
 useEffect(()=>{const element=frame.current;if(!element)return;const observer=new ResizeObserver(entries=>{const measured=entries[0]?.contentRect.width;if(measured)setWidth(Math.max(250,Math.round(measured)))});observer.observe(element);return()=>observer.disconnect()},[]);
 useEffect(()=>{
  setData(null);setError('');setCursor(null);setCount(180);setOffset(0);
  if(!auth||!['kraken','hyperliquid'].includes(provider)||!symbol)return;
  let active=true,running=false;let controller:AbortController|null=null;
  const load=async()=>{
   if(running||document.visibilityState!=='visible')return;
   running=true;const request=new AbortController();controller=request;const timeout=setTimeout(()=>request.abort(),12000);
   try {
    const response=await fetch('/api/price-history?'+new URLSearchParams({symbol,provider,interval:String(interval)}),{credentials:'include',cache:'no-store',signal:request.signal});
    if(!response.ok)throw Error('Exchange history is temporarily unavailable.');
    const value:History=await response.json();
    if(!verified(value,provider,symbol,interval,Date.now()/1000))throw Error('Exchange history could not be verified.');
    if(active){setData(value);setError('')}
   } catch(e) {if(active)setError((e as Error).name==='AbortError'?'Exchange history request timed out.':(e as Error).message)}
   finally {clearTimeout(timeout);running=false}
  };
  load();const timer=setInterval(load,30000);const visible=()=>{if(document.visibilityState==='visible')load()};
  document.addEventListener('visibilitychange',visible);
  return()=>{active=false;controller?.abort();clearInterval(timer);document.removeEventListener('visibilitychange',visible)};
 },[auth,provider,symbol,interval]);
 const plot=useMemo(()=>{
  if(!data||data.symbol!==symbol||data.provider!==provider||data.interval_minutes!==interval)return null;
  const length=Math.min(count,data.candles.length),end=data.candles.length-Math.min(offset,data.candles.length-length);
  const rows=data.candles.slice(end-length,end),first=rows[0].at,last=rows.at(-1)!.at;
  const low=Math.min(...rows.map(c=>Number(c.low))),high=Math.max(...rows.map(c=>Number(c.high))),pad=(high-low)*.12||low*.001;
  const y=(value:number)=>TOP+(high+pad-value)/(high-low+2*pad)*(PRICE_BOTTOM-TOP);
  const space=interval*60,x=(at:number)=>LEFT+(at-first+space/2)/Math.max(space,last-first+space)*(width-LEFT-RIGHT);
  const points=rows.map(c=>({...c,x:x(c.at),y:y(Number(c.close))}));
  const path=points.map((c,i)=>(i===0||c.at-points[i-1].at>space?'M':'L')+c.x.toFixed(2)+','+c.y.toFixed(2)).join(' ');
  const volumes=points.filter(c=>c.volume!=null),maxVolume=Math.max(0,...volumes.map(c=>Number(c.volume)));
  const barWidth=Math.max(1,Math.min(12,(width-LEFT-RIGHT)/(Math.max(length,2)*1.6)));
  const recorded=markers.filter(m=>Number.isFinite(m.at)&&m.at>=first&&m.at<=last+space&&Number.isFinite(m.price)&&m.price>=low-pad&&m.price<=high+pad).slice(-60);
  return {points,path,first,last,x,y,low,high,pad,maxVolume,volumes,barWidth,recorded};
 },[data,symbol,provider,interval,width,count,offset,markers]);
 const clock=Math.max(now,Date.now()/1000);
 const current=!!data&&online&&!error&&clock-data.received_at>=-1&&clock-data.received_at<=65&&clock-data.source_at>=-1&&clock-data.source_at<=interval*60+65;
 const status=!online&&data?'Disconnected':current?'History updated':data?'Old history':error?'History unavailable':'Loading history';
 const point=plot?.points[Math.min(Math.max(0,cursor??plot.points.length-1),plot.points.length-1)];
 const zoom=(inside:boolean)=>{setCount(old=>Math.min(data?.candles.length||180,Math.max(12,inside?Math.floor(Math.min(old,data?.candles.length||180)/2):old*2)));setCursor(null)};
 const inspect=(event:React.PointerEvent<SVGSVGElement>)=>{
  if(!plot)return;
  const bounds=event.currentTarget.getBoundingClientRect(),x=(event.clientX-bounds.left)/bounds.width*width;
  let closest=0;for(let i=1;i<plot.points.length;i++)if(Math.abs(plot.points[i].x-x)<Math.abs(plot.points[closest].x-x))closest=i;
  setCursor(closest);
 };
 return <div ref={frame} className={"history-chart "+style+(cursor!=null?" is-inspecting":"")} aria-label="Exchange price history">
  <div className="history-toolbar"><label>Time range<select aria-label="Price history time range" value={interval} onChange={e=>setIntervalMinutes(Number(e.target.value))}><option value="1">3 hours · 1 minute</option><option value="5">15 hours · 5 minutes</option><option value="15">45 hours · 15 minutes</option></select></label><label>Chart style<select aria-label="Price history chart style" value={style} onChange={e=>setStyle(e.target.value)}><option value="line">Price line</option><option value="candles">Candlesticks</option></select></label><span className={'badge '+(current?'live':!online?'disconnected':'stale')}>{status}</span></div>
  {plot?<>
   <svg viewBox={`0 0 ${width} ${HEIGHT}`} role="img" aria-label={'Exchange price history for '+symbol+' from '+provider} tabIndex={0} onPointerMove={inspect} onPointerDown={inspect} onPointerLeave={()=>setCursor(null)} onBlur={()=>setCursor(null)} onKeyDown={e=>{
    if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setCursor(old=>Math.max(0,Math.min(plot.points.length-1,(old??plot.points.length-1)+(e.key==='ArrowLeft'?-1:1))))}
    if(e.key==='+'||e.key==='='){e.preventDefault();zoom(true)}if(e.key==='-'){e.preventDefault();zoom(false)}if(e.key==='Escape')setCursor(null);
   }}>
    <defs><clipPath id={'history-clip-'+provider}><rect x={LEFT-8} y={TOP} width={width-LEFT-RIGHT+16} height={PRICE_BOTTOM-TOP}/></clipPath></defs>
    {[0,1,2,3,4].map(i=>{const value=plot.high+plot.pad-(plot.high-plot.low+2*plot.pad)*i/4;return <g key={i}><line className="live-market-grid" x1={LEFT} x2={width-RIGHT} y1={plot.y(value)} y2={plot.y(value)}/><text className="live-market-axis" x={LEFT-9} y={plot.y(value)+4} textAnchor="end">{axisPrice(value)}</text></g>})}
    <g clipPath={'url(#history-clip-'+provider+')'}>{style==='line'?<><path data-testid="history-price-line" d={plot.path} className={'live-market-line '+(!current?'is-stale':'')} fill="none"/>{plot.points.filter(c=>!c.closed).map(c=><circle key={c.at} className="unfinished-point" cx={c.x} cy={c.y} r="4"/>)}</>:plot.points.map(c=><g key={c.at} data-closed={c.closed} className={(Number(c.close)>=Number(c.open)?'candle-up':'candle-down')+(!c.closed?' unfinished-candle':'')}><line x1={c.x} x2={c.x} y1={plot.y(Number(c.high))} y2={plot.y(Number(c.low))}/><rect x={c.x-plot.barWidth/2} y={Math.min(plot.y(Number(c.open)),c.y)} width={plot.barWidth} height={Math.max(1,Math.abs(plot.y(Number(c.open))-c.y))}/></g>)}
    {plot.recorded.map((marker,i)=><g key={marker.kind+marker.at+i} className={'recorded-marker '+marker.kind} data-testid="recorded-chart-marker"><title>{marker.label+' · '+new Date(marker.at*1000).toLocaleString()+' · '+px(marker.price)}</title><circle cx={plot.x(marker.at)} cy={plot.y(marker.price)} r={marker.kind==='trade'?3:5}/></g>)}
    {cursor!=null&&point&&<g><line className="live-market-crosshair" x1={point.x} x2={point.x} y1={TOP} y2={VOLUME_TOP+VOLUME_HEIGHT}/><line className="live-market-crosshair" x1={LEFT} x2={width-RIGHT} y1={point.y} y2={point.y}/><circle className="live-market-cursor" cx={point.x} cy={point.y} r="4"/></g>}</g>
    <text className="volume-label" x={LEFT} y={VOLUME_TOP-10}>{plot.volumes.length?'TRADED VOLUME · BASE UNITS':'VOLUME UNAVAILABLE'}</text>
    {plot.volumes.map(c=><rect key={c.at} data-testid="history-volume-bar" className={'volume-bar '+(!c.closed?'unfinished-candle':'')} x={c.x-plot.barWidth/2} width={plot.barWidth} y={VOLUME_TOP+VOLUME_HEIGHT-(plot.maxVolume?Number(c.volume)/plot.maxVolume*VOLUME_HEIGHT:0)} height={plot.maxVolume?Number(c.volume)/plot.maxVolume*VOLUME_HEIGHT:0}><title>{c.volume+' base units · '+time(c.at)}</title></rect>)}
    <text className="live-market-axis" x={LEFT} y={HEIGHT-12}>{time(plot.first,interval===15)}</text><text className="live-market-axis" x={width-RIGHT} y={HEIGHT-12} textAnchor="end">{time(plot.last,interval===15)}</text>
   </svg>
   <div className="history-point"><strong>{point?px(Number(point.close)):''}</strong><span>{point?new Date(point.at*1000).toLocaleString():''} · {point?.closed?'Completed candle':'Current candle · still changing'}</span></div>
   <dl className="candle-inspection" aria-label="Inspected candle prices">{point&&[['Open',point.open],['High',point.high],['Low',point.low],['Close',point.close],['Volume',point.volume]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value!=null?px(Number(value)):'Unavailable'}</dd></div>)}</dl>
   <div className="history-zoom"><div><button type="button" className="secondary compact" aria-label="Zoom in on price history" disabled={plot.points.length<=12} onClick={()=>zoom(true)}>+</button><button type="button" className="secondary compact" aria-label="Zoom out of price history" disabled={!data||count>=data.candles.length} onClick={()=>zoom(false)}>−</button><button type="button" className="text-button" onClick={()=>{setOffset(0);setCount(180);setCursor(null)}}>Reset chart</button></div><span>{plot.points.length} of {data?.candles.length} candles shown</span></div>
   {data&&data.candles.length>count&&<label className="history-pan">Earlier / later candles<input aria-label="Browse earlier price history" type="range" min="0" max={data.candles.length-count} value={Math.max(0,data.candles.length-count-offset)} onChange={e=>{setOffset(data.candles.length-count-Number(e.target.value));setCursor(null)}}/></label>}
   <p className="history-caption">{data?.candles.length} actual exchange candles · gaps stay open · latest candle can change. Use ← / → to inspect prices. + / − zoom. Times use your device timezone.</p>
   <div className="chart-marker-legend"><span><i className="trade"/>Recorded trade</span><span><i className="signal"/>Recorded signal</span><span><i className="practice"/>Practice entry</span><small>{plot.recorded.length?plot.recorded.length+' verified records in view':'No verified markers in this window'}</small></div>
  </>:<div className="empty history-empty"><span className="eyebrow">ACTUAL EXCHANGE HISTORY</span><h3>{!auth?'Sign in to view market history':error||'Loading actual exchange price history…'}</h3><p>Price history loads as soon as a detailed market is selected. If the exchange is unavailable, the chart stays empty. Live ticks show fresh book observations.</p></div>}
  {plot&&error&&<p className="history-error" role="status">{error} Retained history is old.</p>}
  <small className="history-source">Source: {provider||'unavailable'} public {provider==='kraken'?'OHLC':'candleSnapshot'} · received {data?new Date(data.received_at*1000).toLocaleString():'waiting'} · historical trade prices, not executable quotes.</small>
 </div>;
}

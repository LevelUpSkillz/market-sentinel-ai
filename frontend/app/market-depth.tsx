'use client';
import type {Market} from './types';
type Level={price:number;quantity:number;notional:number};
function levels(rows:[string,string][]|undefined):Level[]{return (rows??[]).slice(0,8).map(([price,quantity])=>({price:Number(price),quantity:Number(quantity),notional:Number(price)*Number(quantity)})).filter(row=>Number.isFinite(row.price)&&row.price>0&&Number.isFinite(row.quantity)&&row.quantity>0&&Number.isFinite(row.notional))}
const fmt=(value:number)=>value.toLocaleString('en-US',{maximumSignificantDigits:7});
export default function MarketDepth({market,fresh}:{market:Market|undefined;fresh:boolean}) {
  const bids=levels(market?.bids),asks=levels(market?.asks);
  const totalBid=bids.reduce((sum,row)=>sum+row.notional,0),totalAsk=asks.reduce((sum,row)=>sum+row.notional,0);
  const total=totalBid+totalAsk;
  const max=Math.max(1,...bids.map(row=>row.notional),...asks.map(row=>row.notional));
  return <details className="depth-drawer"><summary><span>Explore the order book <small>Buyers vs sellers</small></span><span className={'badge '+(fresh?'live':market?.received_at?'stale':'unavailable')}>{fresh?'Fresh snapshot':market?.received_at?'Old snapshot':'Unavailable'}</span></summary><div className="depth-content" aria-label="Visible order book depth">
    <p>Orders visible at this exchange. They can change or disappear before a trade fills.</p>
    {bids.length>0&&asks.length>0?<><div className="depth-pressure"><span>Buy side {Math.round(totalBid/total*100)}%</span><span>Sell side {Math.round(totalAsk/total*100)}%</span></div><div className="depth-balance" role="img" aria-label={`Visible buy notional ${fmt(totalBid)} and sell notional ${fmt(totalAsk)} ${market?.quote}`}><span style={{width:(totalBid/total*100)+'%'}}/></div><div className="depth-ladder">{[{name:'Buy orders',rows:bids,side:'buy'},{name:'Sell orders',rows:asks,side:'sell'}].map(({name,rows,side})=><div key={side}><div className="depth-label"><strong>{name}</strong><small>Size · token units</small></div>{rows.map((row,index)=><div key={index} className={'depth-level is-'+side}><span className="depth-bar" style={{width:(row.notional/max*100)+'%'}}/><span>{fmt(row.price)}</span><span>{fmt(row.quantity)}</span></div>)}</div>)}</div></>:<p className="depth-unavailable">No verified two-sided depth is available for this market.</p>}
    <small className="depth-source">Source: {market?.provider||'unavailable'} · {market?.symbol||'no market selected'} · price and notional in {market?.quote||'quote currency unavailable'} · up to eight levels per side · source event {market?.source_at?new Date(market.source_at*1000).toLocaleString():'unavailable'} · received {market?.received_at?new Date(market.received_at*1000).toLocaleString():'unavailable'}. This is displayed liquidity, not a trading signal.</small>
  </div></details>;
}

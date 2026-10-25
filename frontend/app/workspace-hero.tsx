'use client';
import type {Dashboard} from './types';

export default function WorkspaceHero({data,online,onMoney,onRadar,onTraders,onPrices,onHelp}:{data:Dashboard|null;online:boolean;onMoney:()=>void;onRadar:()=>void;onTraders:()=>void;onPrices:()=>void;onHelp:()=>void}) {
  const now=Date.now()/1000;
  const total=data?.markets.length??0;
  const fresh=data?.markets.filter(row=>online&&row.status==='live'&&row.source_at!=null&&now-row.source_at>=-1&&now-row.source_at<=5&&now-row.received_at>=0&&now-row.received_at<=5&&['crc32_verified','ordered_stream'].includes(row.integrity)).length??0;
  const connected=data?Object.values(data.providers).filter(provider=>provider.state==='connected').length:0;
  return <section className="workspace-hero" aria-label="Workspace overview">
    <div className="hero-copy">
      <span className="eyebrow"><span className="terminal-square"/> YOUR PRIVATE MARKET DESK</span>
      <h2>A clearer view.<br/><em>A smarter next move.</em></h2>
      <p>Follow the market. Understand the idea. Stay in control.</p>
      <div className="hero-actions">
        <button className="primary" onClick={onRadar}>Explore trade ideas <span aria-hidden="true">↗</span></button>
        <button className="secondary" onClick={onPrices}>See live prices <span aria-hidden="true">↗</span></button>
      </div>
      <button className="text-button hero-help" onClick={onHelp}>New here? Take the quick tour <span aria-hidden="true">→</span></button>
    </div>
    <div className="hero-observatory">
      <div className="orbital-readout" role="img" aria-label={data?`${fresh} of ${total} detailed market books are fresh`:'Market coverage unavailable until connected'}>
        <svg viewBox="0 0 180 180" aria-hidden="true"><circle className="orbit-outer" cx="90" cy="90" r="82"/><path className="orbit-cross" d="M90 2v13m0 150v13M2 90h13m150 0h13"/><circle className="orbit-track" cx="90" cy="90" r="65"/><circle className="orbit-value" cx="90" cy="90" r="65" pathLength="100" strokeDasharray={`${total?fresh/total*100:0} 100`} transform="rotate(-90 90 90)"/><circle className="orbit-inner" cx="90" cy="90" r="48"/></svg>
        <div><strong>{data?fresh:'—'}</strong><span>FRESH BOOKS</span></div>
      </div>
      <div className="observatory-copy"><span className="eyebrow">LIVE COVERAGE</span><strong>{data?`${fresh} / ${total}`:'Not connected'}</strong><span>Detailed market books · 5s freshness</span><small>{data?`${connected} provider connection${connected===1?'':'s'} reported`:'Waiting for verified sources'}</small><small>Source: exchange books · received {data?new Date(data.as_of*1000).toLocaleTimeString():'unavailable'}</small></div>
    </div>
    <div className="hero-destinations"><button onClick={onTraders}><span>PUBLIC TRADER RESEARCH</span><strong>See what big traders are doing <span aria-hidden="true">↗</span></strong></button><button onClick={onMoney}><span className="capital-label">YOUR KRAKEN ACCOUNT</span><strong>Open Live Money <span aria-hidden="true">↗</span></strong></button></div>
  </section>;
}

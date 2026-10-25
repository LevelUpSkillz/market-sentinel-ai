'use client';
import type {Dashboard} from './types';
import OrbitalScene from './orbital-scene';

type Props={data:Dashboard|null;online:boolean;effectsRunning:boolean;onMoney:()=>void;onRadar:()=>void;onTraders:()=>void;onPrices:()=>void;onHelp:()=>void};
export default function WorkspaceHero({data,online,effectsRunning,onMoney,onRadar,onTraders,onPrices,onHelp}:Props) {
  const now=Date.now()/1000;
  const freshBook=(row:Dashboard['markets'][number])=>online&&row.status==='live'&&row.source_at!=null&&now-row.source_at>=-1&&now-row.source_at<=5&&now-row.received_at>=0&&now-row.received_at<=5&&['crc32_verified','ordered_stream'].includes(row.integrity);
  const total=data?.markets.length??0;
  const fresh=data?.markets.filter(freshBook).length??0;
  const connected=data?Object.values(data.providers).filter(provider=>provider.state==='connected').length:0;
  return <section className="workspace-hero mission-hero" aria-label="Workspace overview">
    <div className="hero-copy">
      <span className="eyebrow"><span className="terminal-square"/> MARKET SENTINEL // MISSION CONTROL</span>
      <h2>See the signal.<br/><em>Own your next move.</em></h2>
      <p>Your personal market observatory. Live prices, public trader intelligence, and every decision under your control.</p>
      <div className="mission-metrics">
        <div role="img" aria-label={data?`${fresh} of ${total} detailed market books are fresh`:'Market coverage unavailable until connected'}><span className="metric-coordinate">01 / COVERAGE</span><strong>{data?fresh:'—'}<small> / {data?total:'—'}</small></strong><span>Fresh detailed books</span></div>
        <div><span className="metric-coordinate">02 / SOURCES</span><strong>{data?connected:'—'}</strong><span>Provider connections reported</span></div>
      </div>
      <div className="hero-actions"><button className="primary" onClick={onRadar}>Explore trade ideas <span aria-hidden="true">↗</span></button><button className="secondary" onClick={onPrices}>See live prices <span aria-hidden="true">↗</span></button><button className="text-button hero-help" onClick={onHelp}>Quick tour →</button></div>
      <small className="mission-source">Exchange books · 5s freshness check · API received {data?new Date(data.as_of*1000).toLocaleTimeString():'unavailable'}</small>
    </div>
    <div className="mission-visual">
      <div className="visual-coordinate"><span>ORBITAL OBSERVATORY</span><span>MS / 01</span></div>
      <OrbitalScene running={effectsRunning}/>
      <div className="orbital-hud-rim" aria-hidden="true"><span/><i/><b/></div>
      <div className="source-nodes" aria-label="Provider source status">{['kraken','hyperliquid','coinbase'].map((name,index)=>{
        const current=data?.markets.some(row=>row.provider===name&&freshBook(row));const reported=data?.providers[name]?.state;
        return <div key={name} className={'source-node source-node-'+index+(current?' is-fresh':'')}><span className="source-node-light"/><div><strong>{name}</strong><small>{current?'Verified fresh books':reported==='connected'?'Awaiting fresh books':reported||'Unavailable'}</small></div></div>;
      })}</div>
      <div className="visual-caption"><span className="status-dot"/> Decorative orbital animation · source diagram, not a geographic map</div>
    </div>
    <div className="hero-destinations"><button onClick={onTraders}><span>PUBLIC TRADER RESEARCH</span><strong>See what big traders are doing <span aria-hidden="true">↗</span></strong></button><button onClick={onMoney}><span className="capital-label">YOUR KRAKEN ACCOUNT</span><strong>Open Live Money <span aria-hidden="true">↗</span></strong></button></div>
  </section>;
}

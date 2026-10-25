'use client';
import {useState} from 'react';
import InstrumentPanel,{type InstrumentFact} from './instrument-panel';
import {depthModel,freshBook,journalModel,labModel,numeric,practiceModel,shown,timestamp,walletModel,type InstrumentModel} from './instrument-model';
import type {Dashboard,JournalRecord,LabResult,Trader} from './types';
type Props={tab:number;data:Dashboard|null;traders:Trader[];records:JournalRecord[];lab:LabResult|null;online:boolean;now:number;running:boolean;onWallet:(address:string)=>void};
export default function SectionObservatory({tab,data,traders,records,lab,online,now,running,onWallet}:Props) {
  const [marketKey,setMarketKey]=useState('');
  if(tab===0||tab===10)return null;
  const clock=Math.max(now,Date.now()/1000),loaded=data!==null;
  let model:InstrumentModel={kind:'systems',points:[]},title='',subtitle='',caption='',source='',facts:InstrumentFact[]=[],controls:React.ReactNode;
  if(tab===1){
    const markets=data?.markets||[];const market=markets.find(row=>row.provider+'|'+row.symbol===marketKey)||markets.find(row=>row.provider==='kraken'&&freshBook(row,online,clock))||markets[0];
    model=depthModel(market,online,clock);title='Order book landscape';subtitle='Explore the visible buy and sell orders for one market in three dimensions.';
    const bid=model.points.filter(p=>p.group==='bid').reduce((sum,p)=>sum+(p.value??0),0),ask=model.points.filter(p=>p.group==='ask').reduce((sum,p)=>sum+(p.value??0),0);
    facts=[{label:'Market',value:market?.symbol||'Unavailable',note:market?.provider||'No provider'},{label:'Displayed buy orders',value:market&&model.points.length?shown(bid)+' '+market.quote:'—'},{label:'Displayed sell orders',value:market&&model.points.length?shown(ask)+' '+market.quote:'—'},{label:'Book freshness',value:market?freshBook(market,online,clock)?'Fresh · under 5s':'Old or unavailable':'Unavailable',note:'A connection alone is not a fresh quote'}];
    controls=<label className="instrument-market">Depth market<select aria-label="Depth visualization market" value={market?market.provider+'|'+market.symbol:''} disabled={!markets.length} onChange={event=>setMarketKey(event.target.value)}>{!markets.length&&<option value="">No detailed markets</option>}{markets.map(row=><option key={row.provider+row.symbol} value={row.provider+'|'+row.symbol}>{row.symbol} · {row.provider}</option>)}</select></label>;
    caption='Bars use displayed price × token size, up to eight levels per side. Quote currencies stay separate. Displayed orders can disappear; this is not a fill guarantee.';
    source=`Source: ${market?.provider||'unavailable'} ${market?.symbol||''} · event ${timestamp(market?.source_at)} · received ${timestamp(market?.received_at)}`;
  }else if(tab===2){
    model=walletModel(traders,online,clock);title='Public wallet constellation';subtitle='Wallet-to-token links show the public positions in your loaded watchlist. Select a wallet to inspect it.';
    const wallets=model.points.filter(p=>p.group==='wallet'),tokens=model.points.filter(p=>p.group==='token');
    facts=[{label:'Loaded wallet snapshots',value:loaded?String(wallets.length):'—'},{label:'Recent snapshots',value:loaded?String(wallets.filter(p=>p.state==='ready').length):'—',note:'Within 90 seconds; others are old'},{label:'Tokens shown',value:loaded?String(tokens.length):'—',note:'Up to 12 token nodes'},{label:'Position links shown',value:loaded?String(model.links?.length||0):'—'}];
    caption='A link means a wallet holds a reported perpetual position in that token. It is not a transfer, trade counterpart, verified person, ranking or recommendation. Layout motion is decorative.';
    source='Source: loaded Hyperliquid clearinghouseState snapshots · each wallet receipt time is in the item inspector.';
  }else if(tab===4){
    title='Signal investigation engine';subtitle='Follow the four evaluation stages. A missing input or failed risk check can reject an idea.';
    const signals=data?.signals||[];const decisions=signals.map(s=>online&&s.snapshots.length>0&&s.snapshots.every(row=>freshBook(row,online,clock))?s.decision:'NO-GO');
    model={kind:'pipeline',points:signals.slice(0,20).map((s,i)=>({id:s.id||'signal'+i,label:s.symbol,group:decisions[i],hint:`${s.symbol} · ${decisions[i]} · ${s.buy_provider} → ${s.sell_provider} · detected ${timestamp(s.detected_at)}`})),steps:[{label:'FIND',state:'unknown'},{label:'CHALLENGE',state:'unknown'},{label:'RISK',state:'unknown'},{label:'DECIDE',state:'unknown'}]};
    facts=[{label:'Detailed-book analyses',value:loaded?String(signals.length):'—',note:'This is separate from broad-market radar coverage'},{label:'WAIT',value:loaded?String(decisions.filter(d=>d==='WAIT').length):'—'},{label:'NO-GO',value:loaded?String(decisions.filter(d=>d==='NO-GO').length):'—'},{label:'GO · practice only',value:loaded?String(decisions.filter(d=>d==='GO').length):'—'}];
    caption='The animated pipeline explains the workflow. It does not create signals or estimate success odds. A real order requires your separate review and approval.';source='Source: dashboard detailed-book signal snapshots · API received '+timestamp(data?.as_of);
  }else if(tab===3||tab===5||tab===8){
    model=journalModel(records,tab===5?'forensic':tab===8?'relay':'timeline');
    title=tab===3?'Opportunity flight recorder':tab===5?'Market investigation spectrum':'Alert transmission console';
    subtitle=tab===3?'Inspect the timeline of loaded, recorded opportunity detections.':tab===5?'Compare the spreads actually saved with loaded market investigations.':'Inspect loaded alert records and their reported delivery states.';
    const at=model.points.map(p=>p.at).filter((value):value is number=>value!=null&&Number.isFinite(value));
    facts=[{label:'Loaded records in this view',value:loaded?String(records.length):'—',note:'Filtered records, not the entire database'},{label:tab===5?'Saved spreads shown':'Events with timestamps',value:loaded?String(model.points.filter(p=>tab===5||p.at!=null).length):'—'},{label:tab===8?'Delivered in loaded records':'Earliest shown',value:tab===8?loaded?String(records.filter(r=>r.status==='delivered').length):'—':at.length?timestamp(Math.min(...at)):'—'},{label:tab===8?'Mobile setup':'Latest shown',value:tab===8?data?.alerts_configured?'Configured':'Not configured':at.length?timestamp(Math.max(...at)):'—',note:tab===8?'Configured does not prove delivery':undefined}];
    caption=tab===5?'Bar heights use saved spread basis points. These historical observations do not prove manipulation, intent or a future price move.':tab===8?'Only saved delivery records establish delivery. Decorative relay lights do not represent messages being sent.':'Points use recorded detection times and decision categories. This is an event timeline, not a price, return or profitability chart.';
    source='Source: loaded '+(tab===3?'opportunity':tab===5?'forensic':'alert')+' journal records · original timestamps retained.';
  }else if(tab===6){
    model=labModel(lab);title='Walk-forward validation map';subtitle='Training and later test windows stay separate. Each row represents a recorded validation fold.';
    const percentage=(value:number|undefined)=>value!=null&&Number.isFinite(value)?(value*100).toFixed(2)+'%':'—';
    facts=[{label:'Loaded validation folds',value:lab?String(lab.folds.length):'—'},{label:'Out-of-sample return',value:percentage(lab?.out_of_sample_return),note:'Hypothetical; after configured costs'},{label:'Buy-and-hold benchmark',value:percentage(lab?.buy_and_hold_return)},{label:'No-trade benchmark',value:percentage(lab?.no_trade_return)}];
    caption='Dim segments are training windows; bright segments are held-out tests; gaps are the embargo. No return curve or validation result is invented before a study runs.';source=lab?'Source: uploaded study · '+lab.source+' · '+lab.data_label:'Source: no completed study loaded. Orbital guides are decorative.';
  }else if(tab===7){
    model=practiceModel(data);title='Practice capital orbit';subtitle='See virtual cash and the original entry cost of open practice positions.';
    const open=data?.paper.filter(p=>p.status==='open')||[];
    facts=[{label:'Virtual cash',value:data?shown(data.account.cash)+' USD':'—'},{label:'Open practice positions',value:loaded?String(open.length):'—'},{label:'Realized practice P&L',value:data?shown(data.account.realized_pnl)+' USD':'—',note:'Simulated results, not real money'},{label:'Open entry cost',value:data?shown(open.reduce((sum,p)=>sum+(numeric(p.entry_notional)??0),0))+' USD':'—'}];
    caption='The ring shows cash and original entry costs, not current portfolio equity. Unrealized gains or losses are not inferred. These are simulated trades only.';source='Source: practice account and trade ledger · API received '+timestamp(data?.as_of);
  }else if(tab===9){
    model={kind:'systems',points:[],steps:[{label:'OWNER',state:data?'ready':'unknown'},{label:'SOURCES',state:'unknown'},{label:'STRATEGY',state:data?'ready':'unknown'},{label:'APPROVAL',state:'unknown'}]};
    title='Workspace systems core';subtitle='Your application environment, strategy version and execution mode at a glance.';
    facts=[{label:'Environment',value:data?.environment||'Unavailable'},{label:'Strategy version',value:data?.strategy_version||'Unavailable'},{label:'Order mode',value:data?.live_trading?'Individual approval':'Submission disabled'},{label:'API connection',value:online?'Connected':'Unavailable',note:'Source freshness is checked separately'}];
    caption='This systems schematic does not test vault health, credentials or exchange account permissions. Decorative nodes never alter configuration.';source='Source: authenticated dashboard configuration · API received '+timestamp(data?.as_of);
  }else return null;
  return <InstrumentPanel model={model} title={title} subtitle={subtitle} facts={facts} source={source} caption={caption} running={running} controls={controls} onPoint={point=>{if(point.group==='wallet')onWallet(point.id.replace(/^wallet:/,''))}}/>;
}

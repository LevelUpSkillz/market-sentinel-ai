'use client';
import {useState} from 'react';
import InstrumentCanvas from './instrument-canvas';
import type {InstrumentModel,InstrumentPoint} from './instrument-model';
export type InstrumentFact={label:string;value:string;note?:string};
export default function InstrumentPanel({model,title,subtitle,facts,source,caption,running,controls,onPoint}:{model:InstrumentModel;title:string;subtitle:string;facts:InstrumentFact[];source:string;caption:string;running:boolean;controls?:React.ReactNode;onPoint?:(point:InstrumentPoint)=>void}) {
  const [flat,setFlat]=useState(false),[guides,setGuides]=useState(true),[selected,setSelected]=useState(''),[expanded,setExpanded]=useState(false);
  const current=model.points.find(p=>p.id===selected)||model.points[0];
  const select=(point:InstrumentPoint)=>setSelected(point.id);
  return <section className={'panel instrument-panel instrument-'+model.kind+(expanded?' is-expanded':'')} aria-label={title}>
    <div className="panel-head"><div><span className="eyebrow">SPATIAL INTELLIGENCE / {model.kind.toUpperCase()}</span><h2>{title}</h2></div><div className="instrument-layers" aria-label="Visual display controls"><button aria-pressed={!flat} onClick={()=>setFlat(false)}>3D</button><button aria-pressed={flat} onClick={()=>setFlat(true)}>Flat</button><button aria-pressed={guides} onClick={()=>setGuides(value=>!value)}>Grid</button><button aria-label={expanded?'Use compact visual':'Expand visual'} aria-pressed={expanded} onClick={()=>setExpanded(value=>!value)}>{expanded?'↙':'↗'}</button></div></div>
    <div className="instrument-description"><p>{subtitle}</p>{controls}</div>
    <div className="instrument-workspace"><div className="instrument-stage"><InstrumentCanvas model={model} running={running} flat={flat} guides={guides} selected={current?.id||''} onSelect={select}/><div className="instrument-readout"><span>{model.old?'RETAINED SNAPSHOT':model.points.length||model.bands?.length?'RECORDED EVIDENCE':'SCHEMATIC / AWAITING EVIDENCE'}</span><span>Layout motion is decorative</span></div></div><dl className="instrument-facts">{facts.map(fact=><div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd>{fact.note&&<small>{fact.note}</small>}</div>)}</dl></div>
    {model.points.length>0&&<div className="instrument-inspector"><label>Inspect recorded item<select aria-label={'Inspect '+title} value={current?.id||''} onChange={event=>setSelected(event.target.value)}>{model.points.map(point=><option key={point.id} value={point.id}>{point.label} · {point.group||'record'}</option>)}</select></label><p>{current?.hint}</p>{current&&onPoint&&current.group==='wallet'&&<button className="secondary compact" onClick={()=>onPoint(current)}>Open wallet details ↗</button>}</div>}
    <div className="instrument-caption"><p>{caption}</p><small>{source}</small></div>
  </section>;
}

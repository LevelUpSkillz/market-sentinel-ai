'use client';
import InstrumentCanvas from './instrument-canvas';
import {depthModel,freshBook,shown,type InstrumentModel} from './instrument-model';
import type {Market} from './types';
export default function OrbitalScene({running,markets=[],online=false,selected='',view='radar',onSelect=()=>{}}:{running:boolean;markets?:Market[];online?:boolean;selected?:string;view?:'radar'|'depth';onSelect?:(id:string)=>void}) {
 const now=Date.now()/1000,observed=markets.filter(m=>m.received_at>0&&m.mid!=null&&Number.isFinite(Number(m.mid))&&Number(m.mid)>0),market=observed.find(m=>m.provider+'|'+m.symbol===selected)||observed[0];
 const model:InstrumentModel=view==='depth'?depthModel(market,online,now):{kind:'network',points:observed.slice(0,8).map(m=>({id:m.provider+'|'+m.symbol,label:m.symbol,hint:shown(m.mid)+' '+m.quote+' · '+m.provider,state:freshBook(m,online,now)?'ready':'unknown'}))};
 return <InstrumentCanvas model={model} running={running} flat={false} guides={true} selected={selected} onSelect={p=>{if(view==='radar')onSelect(p.id)}} market={view==='radar'} testId="orbital-visual" className="orbital-canvas"/>;
}

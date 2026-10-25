'use client';
import {useEffect,useRef} from 'react';
import type {InstrumentModel,InstrumentPoint} from './instrument-model';
import {paintSpatial,type SceneHit} from './spatial-renderer';
export default function InstrumentCanvas({model,running,flat,guides,selected,onSelect,market=false,testId='section-instrument',className='section-instrument-canvas'}:{model:InstrumentModel;running:boolean;flat:boolean;guides:boolean;selected:string;onSelect:(point:InstrumentPoint)=>void;market?:boolean;testId?:string;className?:string}) {
 const canvas=useRef<HTMLCanvasElement>(null),latest=useRef({model,flat,guides,selected,market}),phase=useRef(0),yaw=useRef(0),redraw=useRef<(()=>void)|null>(null),hits=useRef<SceneHit[]>([]),select=useRef(onSelect),dimensions=useRef({w:900,h:520}),drag=useRef<{x:number;start:number;distance:number}|null>(null);select.current=onSelect;
 useEffect(()=>{latest.current={model,flat,guides,selected,market};redraw.current?.()},[model,flat,guides,selected,market]);
 useEffect(()=>{
  const element=canvas.current,ctx=element?.getContext('2d');if(!element||!ctx)return;
  let frame=0,disposed=false,visible=true,last=-Infinity;
  const draw=()=>{const {w,h}=dimensions.current;hits.current=paintSpatial(ctx,w,h,latest.current.model,phase.current,{...latest.current,yaw:yaw.current})};redraw.current=draw;
  const resize=()=>{const dpr=Math.min(window.devicePixelRatio||1,1.5),w=900,h=innerWidth<700?750:520;dimensions.current={w,h};element.width=w*dpr;element.height=h*dpr;element.style.aspectRatio=`${w}/${h}`;ctx.setTransform(dpr,0,0,dpr,0,0);draw()};resize();
  const stop=()=>{cancelAnimationFrame(frame);frame=0;element.dataset.animating='false'};
  const tick=(time:number)=>{if(disposed||!running||!visible||document.visibilityState!=='visible'){stop();return}if(time-last>=1000/(innerWidth<700?24:30)){phase.current+=last===-Infinity?0:Math.min((time-last)/1000,.1);last=time;draw()}frame=requestAnimationFrame(tick)};
  const start=()=>{if(disposed||frame||!running||!visible||document.visibilityState!=='visible')return;last=-Infinity;element.dataset.animating='true';frame=requestAnimationFrame(tick)};
  element.dataset.animating='false';start();const observer=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting??false;if(visible)start();else stop()});observer.observe(element);
  const visibility=()=>{if(document.visibilityState==='visible')start();else stop()};document.addEventListener('visibilitychange',visibility);window.addEventListener('resize',resize);
  return()=>{disposed=true;stop();observer.disconnect();document.removeEventListener('visibilitychange',visibility);window.removeEventListener('resize',resize);redraw.current=null};
 },[running]);
 const pointAt=(e:React.PointerEvent<HTMLCanvasElement>|React.MouseEvent<HTMLCanvasElement>)=>{const r=e.currentTarget.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*dimensions.current.w,y=(e.clientY-r.top)/r.height*dimensions.current.h;return hits.current.find(p=>Math.hypot(p.x-x,p.y-y)<38)};
 return <canvas ref={canvas} data-testid={testId} className={className} aria-hidden="true" onPointerDown={e=>{drag.current={x:e.clientX,start:yaw.current,distance:0};e.currentTarget.setPointerCapture(e.pointerId)}} onPointerMove={e=>{if(drag.current&&e.buttons){drag.current.distance=Math.abs(e.clientX-drag.current.x);yaw.current=drag.current.start+(e.clientX-drag.current.x)/250;redraw.current?.()}e.currentTarget.style.cursor=drag.current&&e.buttons?'grabbing':pointAt(e)?'pointer':'grab'}} onPointerUp={e=>{if(drag.current&&drag.current.distance<7){const p=pointAt(e);if(p)select.current(p.point)}drag.current=null;if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId)}} onPointerCancel={()=>{drag.current=null}}/>;
}

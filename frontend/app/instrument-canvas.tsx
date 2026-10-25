'use client';
import {useEffect,useRef} from 'react';
import type {InstrumentModel,InstrumentPoint} from './instrument-model';
export default function InstrumentCanvas({model,running,flat,guides,selected,onSelect}:{model:InstrumentModel;running:boolean;flat:boolean;guides:boolean;selected:string;onSelect:(point:InstrumentPoint)=>void}) {
  const canvas=useRef<HTMLCanvasElement>(null),latest=useRef({model,flat,guides,selected}),phase=useRef(0),redraw=useRef<(()=>void)|null>(null),hits=useRef<{x:number;y:number;point:InstrumentPoint}[]>([]),select=useRef(onSelect);select.current=onSelect;
  useEffect(()=>{latest.current={model,flat,guides,selected};redraw.current?.()},[model,flat,guides,selected]);
  useEffect(()=>{
    const element=canvas.current,ctx=element?.getContext('2d');if(!element||!ctx)return;
    const W=720,H=330,cx=360,cy=171,dpr=Math.min(window.devicePixelRatio||1,1.5);element.width=W*dpr;element.height=H*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);element.dataset.animating='false';
    let frame=0,disposed=false,visible=true,last=-Infinity;
    const palette={depth:'#60e9e7',network:'#b6a0ff',pipeline:'#5ee8e2',timeline:'#79baff',forensic:'#ff9e9b',lab:'#91deb3',practice:'#a7e0b4',relay:'#aaa6ff',systems:'#84c9f1',capital:'#ebc58c'};
    const rgba=(hex:string,alpha:number)=>`rgba(${parseInt(hex.slice(1,3),16)},${parseInt(hex.slice(3,5),16)},${parseInt(hex.slice(5,7),16)},${alpha})`;
    const draw=()=>{
      const {model:m,flat:top,guides:grid,selected:chosen}=latest.current,color=palette[m.kind],t=phase.current;hits.current=[];ctx.clearRect(0,0,W,H);
      const glow=ctx.createRadialGradient(cx,cy,15,cx,cy,270);glow.addColorStop(0,rgba(color,.09));glow.addColorStop(1,rgba(color,0));ctx.fillStyle=glow;ctx.fillRect(0,0,W,H);
      const line=(a:number,b:number,c:number,d:number,alpha=.25)=>{ctx.beginPath();ctx.moveTo(a,b);ctx.lineTo(c,d);ctx.strokeStyle=rgba(color,alpha);ctx.lineWidth=.8;ctx.stroke()};
      const label=(text:string,x:number,y:number,size=9,alpha=.7,align:CanvasTextAlign='center')=>{ctx.font=`${size}px ui-monospace,monospace`;ctx.textAlign=align;ctx.fillStyle=rgba(color,alpha);ctx.fillText(text,x,y)};
      const dot=(x:number,y:number,r=3,alpha=.9)=>{ctx.fillStyle=rgba(color,alpha);ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill()};
      const ring=(radius:number,squash:number,rotation:number,alpha=.2)=>{ctx.save();ctx.translate(cx,cy);ctx.rotate(rotation);ctx.strokeStyle=rgba(color,alpha);ctx.lineWidth=.7;ctx.beginPath();ctx.ellipse(0,0,radius,radius*squash,0,0,Math.PI*2);ctx.stroke();ctx.restore()};
      if(grid){for(let i=0;i<9;i++){line(45+i*78,28,45+i*78,H-24,.07);line(40,30+i*35,W-40,30+i*35,.07)}line(cx,18,cx,H-18,.18);line(22,cy,W-22,cy,.12)}
      ring(253,top?.9:.34,-.18,.13);ring(219,top?.9:.45,.25,.18);
      // Layered holographic engineering geometry. All of this cage/trail motion
      // is ornamental; it never supplies measurements or activity counts.
      const projectCage=(x:number,y:number,z:number)=>{const a=t*.19,xx=x*Math.cos(a)-z*Math.sin(a),zz=x*Math.sin(a)+z*Math.cos(a);return {x:cx+xx,y:cy+y*.67+zz*.32}};
      const cage=Array.from({length:12},(_,i)=>{const a=i/12*Math.PI*2;return projectCage(Math.cos(a)*194,Math.sin(a)*100,Math.sin(a*2)*63)});
      for(let i=0;i<cage.length;i++){const a=cage[i],b=cage[(i+1)%cage.length],c=cage[(i+4)%cage.length];line(a.x,a.y,b.x,b.y,.25);line(a.x,a.y,c.x,c.y,.09)}
      for(let layer=0;layer<3;layer++){
        const radius=150+layer*29,rotation=t*(layer%2?-.13:.17)+layer*.72;
        for(let tick=0;tick<42;tick++){const a=tick/42*Math.PI*2+rotation,b=a+.07;ctx.save();ctx.translate(cx,cy);ctx.rotate(layer*.65-.3);ctx.beginPath();ctx.ellipse(0,0,radius,radius*(top?.84:.42+layer*.09),0,a,b);ctx.strokeStyle=rgba(color,tick%7===0?.6:.18);ctx.lineWidth=tick%7===0?2:.7;ctx.stroke();ctx.restore()}
      }
      for(let ribbon=0;ribbon<2;ribbon++){
        ctx.beginPath();for(let step=0;step<=65;step++){const a=step/65*Math.PI*3+t*(ribbon?-.6:.6),r=58+step*.7,x=cx+Math.cos(a)*r,y=cy-105+step*3.2;step?ctx.lineTo(x,y):ctx.moveTo(x,y)}ctx.strokeStyle=rgba(color,.1);ctx.lineWidth=.6;ctx.stroke();
      }
      for(let orbit=0;orbit<2;orbit++)for(let trail=18;trail>=0;trail--){const a=t*(orbit?-.8:1.2)+orbit*Math.PI-trail*.022,x=cx+Math.cos(a)*(267-orbit*38),y=cy+Math.sin(a)*(top?130:69+orbit*17);dot(x,y,trail===0?3:1.2,(1-trail/19)*(trail===0?.9:.35))}

      // These moving lights are ornamental. They never represent trade arrivals.
      for(let i=0;i<3;i++){const a=t*(i===1?-.7:1)+i*2.1;dot(cx+Math.cos(a)*253,cy+Math.sin(a)*(top?226:79),2,.55)}
      if(m.kind==='depth'||m.kind==='forensic'){
        const points=m.points.filter(p=>p.value!=null&&Number.isFinite(p.value)&&p.value>=0),max=Math.max(1,...points.map(p=>p.value!));
        const project=(x:number,z:number,h:number)=>top?{x:80+x*1.65+z*.23,y:260-h}:{x:cx+(x-120)*1.45+z*.8,y:241+(x-120)*.16-z*.35-h};
        const groups=m.kind==='depth'?['bid','ask']:['spread'];
        groups.forEach((group,side)=>{const rows=m.kind==='depth'?points.filter(p=>p.group===group):points;rows.forEach((p,i)=>{const x=rows.length>1?i/(rows.length-1)*245:122,z=m.kind==='depth'?(side===0?-55:55):0,h=p.value!/max*136,base=project(x,z,0),tip=project(x,z,h),width=top?Math.min(18,400/Math.max(1,rows.length)) :12;const c=m.kind==='depth'&&side===1?'#ed9db4':color;ctx.fillStyle=rgba(c,m.old?.18:.4);ctx.fillRect(tip.x-width/2,tip.y,width,Math.max(2,h));ctx.fillStyle=rgba(c,m.old?.3:.85);ctx.beginPath();ctx.moveTo(tip.x-width/2,tip.y);ctx.lineTo(tip.x-width/2+8,tip.y-5);ctx.lineTo(tip.x+width/2+8,tip.y-5);ctx.lineTo(tip.x+width/2,tip.y);ctx.closePath();ctx.fill();line(base.x,base.y,tip.x,tip.y,.5);if(p.id===chosen){ctx.strokeStyle='#e6fcff';ctx.lineWidth=1.5;ctx.strokeRect(tip.x-width/2-3,tip.y-5,width+13,h+7)}hits.current.push({x:tip.x,y:tip.y,point:p});if(rows.length<=8)label(p.label,base.x,base.y+17,8,.7);})});
        if(!points.length)label('AWAITING RECORDED MEASUREMENTS',cx,cy,11,.7);
      }else if(m.kind==='network'){
        const wallets=m.points.filter(p=>p.group==='wallet'),tokens=m.points.filter(p=>p.group==='token'),positions=new Map<string,{x:number;y:number}>();
        wallets.forEach((p,i)=>{const a=i/Math.max(1,wallets.length)*Math.PI*2+t*.06;positions.set(p.id,{x:cx+Math.cos(a)*233,y:cy+Math.sin(a)*(top?119:98)})});
        tokens.forEach((p,i)=>{const a=i/Math.max(1,tokens.length)*Math.PI*2-t*.03;positions.set(p.id,{x:cx+Math.cos(a)*101,y:cy+Math.sin(a)*(top?80:63)})});
        for(const [from,to] of m.links||[]){const a=positions.get(from),b=positions.get(to);if(a&&b)line(a.x,a.y,b.x,b.y,.35)}
        for(const p of m.points){const at=positions.get(p.id);if(!at)continue;dot(at.x,at.y,p.group==='wallet'?5:8,p.state==='unknown'?.35:.9);ctx.strokeStyle=rgba(color,.35);ctx.beginPath();ctx.arc(at.x,at.y,p.id===chosen?16:12,0,Math.PI*2);ctx.stroke();label(p.label,at.x,at.y+25,p.group==='wallet'?8:11,.8);hits.current.push({...at,point:p})}
        if(!m.points.length)label('NO LOADED WALLET SNAPSHOTS',cx,cy,11,.7);
      }else if(m.kind==='timeline'||m.kind==='relay'){
        const rows=m.points.filter(p=>p.at!=null&&Number.isFinite(p.at)).sort((a,b)=>a.at!-b.at!),first=rows[0]?.at??0,lastAt=rows.at(-1)?.at??first;
        for(let track=0;track<3;track++)line(75,96+track*65,W-75,96+track*65,.2);
        rows.forEach((p,i)=>{const x=lastAt>first?80+(p.at!-first)/(lastAt-first)*560:cx,y=p.group==='GO'||p.group==='delivered'?96:p.group==='NO-GO'||p.group==='failed'?226:161;dot(x,y,p.id===chosen?7:4,.85);line(x,y-16,x,y+16,.5);hits.current.push({x,y,point:p});if(rows.length<8)label(p.label.slice(0,18),x,y+32,8,.75)});
        if(!rows.length)label('NO LOADED EVENTS',cx,cy,11,.7);
      }else if(m.kind==='lab'){
        const rows=m.bands||[],max=Math.max(1,...rows.map(r=>r.testEnd));
        rows.forEach((r,i)=>{const y=60+i*(205/Math.max(1,rows.length));ctx.fillStyle=rgba(color,.22);ctx.fillRect(90,y,r.trainEnd/max*530,12);ctx.fillStyle=rgba(color,.85);ctx.fillRect(90+r.testStart/max*530,y,(r.testEnd-r.testStart)/max*530,12);label('F'+(i+1),75,y+10,8,.8,'right')});
        if(!rows.length){for(let i=0;i<4;i++)ring(53+i*31,top?.9:.65,t*.12+i*.63,.23);label('RUN A STUDY TO LOAD VALIDATION FOLDS',cx,cy+8,10,.8)}
      }else if(m.kind==='practice'){
        const rows=m.points.filter(p=>p.value!=null&&p.value>0),total=rows.reduce((sum,p)=>sum+p.value!,0);let start=-Math.PI/2;
        if(total>0&&Number.isFinite(total))for(const [i,p] of rows.entries()){const end=start+p.value!/total*Math.PI*2,gap=Math.min(.015,(end-start)/4);ctx.beginPath();ctx.arc(cx,cy,101,start+gap,end-gap);ctx.lineWidth=18;ctx.strokeStyle=i===0?rgba(color,.9):'#6a9fdc';ctx.stroke();label(p.label,cx+Math.cos((start+end)/2)*169,cy+Math.sin((start+end)/2)*137,9,.85);start=end;}
        label(total>0?'VIRTUAL CAPITAL':'NO LOADED PRACTICE ACCOUNT',cx,cy+4,11,.8);
      }else{
        // Complex geometric instruments are schematics; only their labeled states are data.
        for(let i=0;i<5;i++)ring(48+i*24,top?.9:.34+(i%3)*.22,t*(i%2?-.17:.14)+i*.7,.32);
        if(m.kind==='capital'){
          ctx.beginPath();ctx.moveTo(cx,cy-84);ctx.lineTo(cx+66,cy-54);ctx.lineTo(cx+58,cy+29);ctx.quadraticCurveTo(cx+36,cy+70,cx,cy+93);ctx.quadraticCurveTo(cx-36,cy+70,cx-58,cy+29);ctx.lineTo(cx-66,cy-54);ctx.closePath();ctx.strokeStyle=rgba(color,.8);ctx.lineWidth=1.5;ctx.stroke();line(cx,cy-62,cx,cy+63,.32);
        }else if(m.kind==='systems'){
          const a=t*.12,vertices=Array.from({length:8},(_,i)=>{const x=(i&1?1:-1)*54,z=(i&2?1:-1)*54,y=(i&4?1:-1)*54;return {x:cx+x*Math.cos(a)-z*Math.sin(a),y:cy+y*.8+(x*Math.sin(a)+z*Math.cos(a))*.35}});vertices.forEach((v,i)=>{for(let bit=0;bit<3;bit++){const j=i^(1<<bit);if(j>i)line(v.x,v.y,vertices[j].x,vertices[j].y,.7)}});
        }
        const steps=m.steps||[{label:'FIND',state:'unknown'},{label:'CHALLENGE',state:'unknown'},{label:'RISK',state:'unknown'},{label:'DECIDE',state:'unknown'}];
        steps.forEach((step,i)=>{const x=105+i*(510/Math.max(1,steps.length-1)),y=269;line(x,cy+56,x,y-17,.24);ctx.strokeStyle=rgba(color,step.state==='ready'?.8:.3);ctx.strokeRect(x-48,y-15,96,30);label(step.label.slice(0,14),x,y+3,9,step.state==='blocked'?.5:.85)});
      }
      if(grid){for(const [x,y,sx,sy] of [[23,19,1,1],[W-23,19,-1,1],[23,H-18,1,-1],[W-23,H-18,-1,-1]]){line(x,y,x+19*sx,y,.6);line(x,y,x,y+12*sy,.6)}}
    };
    redraw.current=draw;
    const stop=()=>{cancelAnimationFrame(frame);frame=0;element.dataset.animating='false'};
    const tick=(time:number)=>{if(disposed||!running||!visible||document.visibilityState!=='visible'){stop();return}if(time-last>=1000/(innerWidth<700?24:30)){phase.current+=last===-Infinity?0:Math.min((time-last)/1000,.1)*.22;last=time;draw()}frame=requestAnimationFrame(tick)};
    const start=()=>{if(disposed||frame||!running||!visible||document.visibilityState!=='visible')return;last=-Infinity;element.dataset.animating='true';frame=requestAnimationFrame(tick)};
    draw();start();const observer=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting??false;if(visible)start();else stop()});observer.observe(element);
    const visibility=()=>{if(document.visibilityState==='visible')start();else stop()};document.addEventListener('visibilitychange',visibility);
    return()=>{disposed=true;stop();observer.disconnect();document.removeEventListener('visibilitychange',visibility);redraw.current=null};
  },[running]);
  return <canvas ref={canvas} data-testid="section-instrument" className="section-instrument-canvas" aria-hidden="true" onPointerMove={e=>{const rect=e.currentTarget.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*720,y=(e.clientY-rect.top)/rect.height*330;const point=hits.current.find(p=>Math.hypot(p.x-x,p.y-y)<23);e.currentTarget.style.cursor=point?'pointer':'default'}} onClick={e=>{const rect=e.currentTarget.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*720,y=(e.clientY-rect.top)/rect.height*330;const point=hits.current.find(p=>Math.hypot(p.x-x,p.y-y)<23);if(point)select.current(point.point)}}/>;
}

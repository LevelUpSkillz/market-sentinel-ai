'use client';
import {useEffect,useRef} from 'react';

// An ornamental wireframe, not a geographical map, data feed or prediction.
export default function OrbitalScene({running}:{running:boolean}) {
  const canvas=useRef<HTMLCanvasElement>(null);
  const phase=useRef(0);
  useEffect(()=>{
    const element=canvas.current;if(!element)return;
    const ctx=element.getContext('2d');if(!ctx)return;
    let disposed=false,intersecting=true,frame=0,last=-Infinity;
    let angle=phase.current;
    const width=700,height=430,cx=350,cy=219,radius=119;
    const pixelRatio=Math.min(window.devicePixelRatio||1,1.5);
    element.width=Math.round(width*pixelRatio);element.height=Math.round(height*pixelRatio);
    ctx.setTransform(pixelRatio,0,0,pixelRatio,0,0);
    element.dataset.animating='false';
    const project=(latitude:number,longitude:number)=>{
      const x=Math.cos(latitude)*Math.cos(longitude),z=Math.cos(latitude)*Math.sin(longitude),y=Math.sin(latitude);
      const tilt=.32,yy=y*Math.cos(tilt)-z*Math.sin(tilt),zz=y*Math.sin(tilt)+z*Math.cos(tilt);
      const perspective=3.8/(3.8-zz);
      return {x:cx+x*radius*perspective,y:cy+yy*radius*perspective,z:zz};
    };
    const drawLine=(points:ReturnType<typeof project>[])=>{
      for(const front of [false,true]){
        ctx.beginPath();let connected=false;
        for(const point of points){if((point.z>=0)!==front){connected=false;continue}if(connected)ctx.lineTo(point.x,point.y);else ctx.moveTo(point.x,point.y);connected=true}
        ctx.strokeStyle=front?'rgba(81,218,255,.42)':'rgba(58,139,186,.12)';ctx.lineWidth=front?.7:.5;ctx.stroke();
      }
    };
    const draw=()=>{
      phase.current=angle;
      ctx.clearRect(0,0,width,height);
      const halo=ctx.createRadialGradient(cx,cy,50,cx,cy,204);
      halo.addColorStop(0,'rgba(18,127,183,.14)');halo.addColorStop(.7,'rgba(20,131,183,.08)');halo.addColorStop(1,'rgba(6,16,30,0)');
      ctx.fillStyle=halo;ctx.fillRect(0,0,width,height);
      for(let i=0;i<64;i++){
        const x=(Math.sin(i*127.1)*.5+.5)*width,y=(Math.cos(i*71.7)*.5+.5)*height;
        ctx.fillStyle=i%7===0?'rgba(118,207,255,.6)':'rgba(122,169,214,.2)';ctx.fillRect(x,y,i%7===0?1.6:1,i%7===0?1.6:1);
      }
      ctx.save();ctx.translate(cx,cy);ctx.rotate(-.32);
      ctx.setLineDash([2,9]);ctx.strokeStyle='rgba(83,179,232,.25)';ctx.lineWidth=.8;ctx.beginPath();ctx.ellipse(0,0,231,77,0,0,Math.PI*2);ctx.stroke();
      ctx.setLineDash([]);ctx.strokeStyle='rgba(68,208,255,.36)';ctx.beginPath();ctx.ellipse(0,0,204,65,0,0,Math.PI*2);ctx.stroke();ctx.restore();
      // Rotating latitude/longitude meridians. No random financial events.
      for(let lat=-60;lat<=60;lat+=20){const points=[];for(let step=0;step<=72;step++)points.push(project(lat*Math.PI/180,step/72*Math.PI*2+angle));drawLine(points)}
      for(let lon=0;lon<180;lon+=15){const points=[];for(let step=0;step<=72;step++)points.push(project(-Math.PI+step/72*Math.PI*2,lon*Math.PI/180+angle));drawLine(points)}
      ctx.strokeStyle='rgba(115,237,255,.36)';ctx.lineWidth=.8;ctx.beginPath();ctx.arc(cx,cy,radius+.5,0,Math.PI*2);ctx.stroke();
      // HUD reticle and orbital lights are decorative, not trade markers.
      ctx.strokeStyle='rgba(109,211,249,.24)';ctx.setLineDash([2,5]);ctx.beginPath();ctx.moveTo(cx-172,cy);ctx.lineTo(cx+172,cy);ctx.moveTo(cx,cy-165);ctx.lineTo(cx,cy+165);ctx.stroke();ctx.setLineDash([]);
      ctx.save();ctx.translate(cx,cy);ctx.rotate(-.32);
      for(let index=0;index<3;index++){
        const phase=angle*(index===1?-1.1:1.7)+index*2.1,rx=index===1?231:204,ry=index===1?77:65;
        const x=Math.cos(phase)*rx,y=Math.sin(phase)*ry;
        const glow=ctx.createRadialGradient(x,y,0,x,y,13);glow.addColorStop(0,index===1?'rgba(164,162,255,.95)':'rgba(100,245,255,.95)');glow.addColorStop(1,'rgba(68,205,255,0)');
        ctx.fillStyle=glow;ctx.beginPath();ctx.arc(x,y,13,0,Math.PI*2);ctx.fill();ctx.fillStyle='#d7fbff';ctx.beginPath();ctx.arc(x,y,2.1,0,Math.PI*2);ctx.fill();
      }
      ctx.restore();
      ctx.strokeStyle='rgba(128,216,252,.45)';ctx.lineWidth=1;
      for(const [x,y,sx,sy] of [[28,34,1,1],[672,34,-1,1],[28,398,1,-1],[672,398,-1,-1]]){ctx.beginPath();ctx.moveTo(x,y+15*sy);ctx.lineTo(x,y);ctx.lineTo(x+20*sx,y);ctx.stroke()}
    };
    const stop=()=>{cancelAnimationFrame(frame);frame=0;element.dataset.animating='false'};
    const tick=(timestamp:number)=>{
      if(disposed||!running||!intersecting||document.visibilityState!=='visible'){stop();return}
      if(timestamp-last>=1000/(window.innerWidth<700?24:30)){angle+=last===-Infinity?0:Math.min((timestamp-last)/1000,.1)*.14;last=timestamp;draw()}
      frame=requestAnimationFrame(tick);
    };
    const start=()=>{if(disposed||frame||!running||!intersecting||document.visibilityState!=='visible')return;last=-Infinity;element.dataset.animating='true';frame=requestAnimationFrame(tick)};
    draw();start();
    const observer=new IntersectionObserver(entries=>{intersecting=entries[0]?.isIntersecting??false;if(intersecting)start();else stop()},{threshold:0});observer.observe(element);
    const visibility=()=>{if(document.visibilityState==='visible')start();else stop()};document.addEventListener('visibilitychange',visibility);
    return()=>{disposed=true;stop();observer.disconnect();document.removeEventListener('visibilitychange',visibility)};
  },[running]);
  return <canvas ref={canvas} className="orbital-canvas" aria-hidden="true" data-testid="orbital-visual"/>;
}

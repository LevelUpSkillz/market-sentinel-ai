'use client';
import {useEffect,useRef,useState} from 'react';
const STEPS=[
 {title:'Start with the prices',screen:1,button:'Open Markets',text:'Markets shows what each exchange is reporting. “Live” means the source is fresh. “Old” means wait for an update.',tip:'The line chart shows actual exchange prices. It does not predict the next move.'},
 {title:'Find an idea, not a command',screen:4,button:'Open Trade Ideas',text:'Trade Ideas combines market activity with public trader research. Each card explains what to watch and why an entry passes or fails.',tip:'GO = ready for a practice review. WAIT = a condition is missing. NO-GO = skip this entry. None promises a profit.'},
 {title:'Understand the big traders',screen:2,button:'Open Big Traders',text:'See public wallets, their reported positions and available past trades. Open a wallet’s profile to see its actual actions.',tip:'A wallet is an anonymous public account. Its past win rate is not your chance of winning, and its trade may already be too late to follow.'},
 {title:'Practice before risking money',screen:7,button:'Open Practice',text:'A practice trade uses virtual money. The app models fees and records what happened without sending an exchange order.',tip:'Practice results help test an idea. They are not real profits or proof that it will work with real money.'},
 {title:'Use your real account deliberately',screen:10,button:'Open Live Money',text:'Live Money is for your connected Kraken account. Refresh your balances, set your budget and risk limits, then prepare a trade.',tip:'A suggested stop or target is a planning price. It is not an automatic stop-loss or take-profit order.'},
 {title:'Preview is not buying',screen:10,button:'Open Live Money',text:'“Validate and review” checks an order without placing it. Only your final, exact approval can send the reviewed order to Kraken.',tip:'Real trades can lose money. If a submission has an unknown result, check its status before trying anything else. You can pause new trades at any time.'}
];
export default function QuickTour({open,onClose,onNavigate,readOnly=false}:{open:boolean;onClose:()=>void;onNavigate:(screen:number)=>void;readOnly?:boolean}){
 const [step,setStep]=useState(0);const panel=useRef<HTMLDivElement>(null);
 const steps=readOnly?STEPS.slice(0,3):STEPS;
 useEffect(()=>{if(!open)return;setStep(0);const previous=document.activeElement as HTMLElement|null;const overflow=document.body.style.overflow;document.body.style.overflow='hidden';panel.current?.focus();return()=>{document.body.style.overflow=overflow;previous?.focus()}},[open]);
 if(!open)return null;const current=steps[Math.min(step,steps.length-1)];
 return <div className="tour-backdrop"><div ref={panel} tabIndex={-1} className="quick-tour" role="dialog" aria-modal="true" aria-labelledby="tour-title" onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();onClose()}if(e.key==='Tab'){const buttons=Array.from(panel.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')||[]);const first=buttons[0],last=buttons.at(-1);if(e.shiftKey&&(document.activeElement===first||document.activeElement===panel.current)){e.preventDefault();last?.focus()}else if(!e.shiftKey&&(document.activeElement===last||document.activeElement===panel.current)){e.preventDefault();first?.focus()}}}}>
 <div className="tour-top"><span className="eyebrow">YOUR QUICK GUIDE · {step+1} OF {steps.length}</span><button className="secondary compact" aria-label="Close tutorial" onClick={onClose}>Close ×</button></div>
 <div className="tour-progress" aria-hidden="true">{steps.map((_,i)=><span key={i} className={i<=step?'done':''}/>)}</div>
 <h2 id="tour-title">{current.title}</h2><p>{current.text}</p><div className="tour-tip">{current.tip}</div>
 <button className="text-button" onClick={()=>{onNavigate(current.screen);onClose()}}>{current.button} ↗</button>
 <div className="tour-bottom"><button className="secondary" disabled={step===0} onClick={()=>setStep(s=>s-1)}>Back</button><button className="primary" onClick={()=>step===steps.length-1?onClose():setStep(s=>s+1)}>{step===steps.length-1?'Got it':'Next'}</button></div>
 <small>This guide only explains or opens a screen. It never creates a trade.</small></div></div>;
}

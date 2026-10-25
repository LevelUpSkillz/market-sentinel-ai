'use client';
import {useEffect,useState} from 'react';
const KEY='market-sentinel-visual-effects';
export default function useVisualEffects() {
  const [paused,setPaused]=useState(true),[reduced,setReduced]=useState(false),[visible,setVisible]=useState(true);
  useEffect(()=>{
    const media=window.matchMedia('(prefers-reduced-motion: reduce)');
    const update=()=>setReduced(media.matches);
    const visibility=()=>setVisible(document.visibilityState==='visible');
    let saved=false;try{saved=localStorage.getItem(KEY)==='paused'}catch{}
    setPaused(saved);update();visibility();media.addEventListener('change',update);document.addEventListener('visibilitychange',visibility);
    return()=>{media.removeEventListener('change',update);document.removeEventListener('visibilitychange',visibility)};
  },[]);
  const toggle=()=>{if(reduced)return;setPaused(previous=>{const next=!previous;try{localStorage.setItem(KEY,next?'paused':'enabled')}catch{}return next})};
  return {enabled:!paused&&!reduced,running:!paused&&!reduced&&visible,reduced,toggle};
}

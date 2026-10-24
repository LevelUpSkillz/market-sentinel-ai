'use client';
import {useRef,useState} from 'react';

export default function BackupDownload({auth,online}:{auth:boolean;online:boolean}){
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  const working=useRef(false);
  async function download(){
    if(!auth||!online||working.current)return;
    working.current=true;setBusy(true);setMessage('');
    try{
      const response=await fetch('/api/backup/export',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:'{}',cache:'no-store',signal:AbortSignal.timeout(20000)});
      if(!response.ok){const value=await response.json().catch(()=>({}));throw new Error(typeof value.detail==='string'?value.detail:'The archive could not be created. No partial export was downloaded.')}
      const blob=await response.blob();
      if(blob.size>16*1024*1024)throw new Error('The archive exceeded its supported size. No partial export was downloaded.');
      const url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download='market-sentinel-history-'+new Date().toISOString().slice(0,10)+'.json';link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      setMessage('Archive download started. Keep this private; it includes account and order history. Exchange credentials and server secrets are excluded.');
    }catch(error){setMessage((error as Error).message)}finally{working.current=false;setBusy(false)}
  }
  return <section className="panel" aria-label="Private history backup"><div className="panel-head"><h2>Keep a private history backup</h2></div><div className="wallet-details"><p>The current free database expires November 22, 2026. Save your paper, research and real-order evidence before expiry. A backup contains private financial information.</p><p>Exports include a checksum and record counts. Credentials, sessions and signing nonces are excluded. Restore is an offline operation into a separate empty database; restored orders can never submit.</p><button className="secondary" disabled={!auth||!online||busy} onClick={download}>{busy?'Creating private archive…':'Download private history archive'}</button><small style={{display:'block',marginTop:12}}>Maximum archive 16 MiB · two requests per hour · oversized exports fail without silently dropping records.</small>{message&&<p role="status">{message}</p>}</div></section>;
}

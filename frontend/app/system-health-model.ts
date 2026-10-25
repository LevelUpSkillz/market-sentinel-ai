import type {Dashboard} from './types';
export type SystemHealth={label:string;tone:'good'|'warning'|'critical'|'neutral';issues:string[]};
export function systemHealth(data:Dashboard|null,online:boolean,auth:boolean,checking:boolean):SystemHealth {
  if(checking&&!data)return {label:'Checking',tone:'neutral',issues:['Checking the secure app session and data connection.']};
  if(!auth||!data)return {label:'Sign in required',tone:'neutral',issues:['Sign in to read the data system status.']};
  if(!online)return {label:'Connection issue',tone:'critical',issues:['The app API could not be reached. Retained observations are old; new entries require fresh data.']};
  const issues:string[]=[];
  if(data.journal_error)issues.push('Saving market history reported an error. Review technical diagnostics.');
  const collector=(data as Dashboard&{collector?:{state?:string}}).collector?.state;
  if(collector&&['failed','stalled','stopped','unavailable'].includes(collector))issues.push('The market collector reports '+collector+'.');
  const enabled=Object.entries(data.providers).filter(([,status])=>status.state!=='disabled');
  for(const [name,status] of enabled){
    if(status.state!=='connected')issues.push(name+' is '+(status.state||'unavailable')+'.');
    else if(status.last_message_at!=null&&Number.isFinite(status.last_message_at)&&data.as_of-status.last_message_at>60)issues.push(name+' has not reported a message for over a minute.');
  }
  // A quiet book crossing the 5s execution limit is not itself a transport outage.
  // Warn globally only if ALL loaded books have been without receipts for >30s.
  const enabledNames=new Set(enabled.map(([name])=>name));
  const observed=data.markets.filter(book=>enabledNames.has(book.provider)&&Number.isFinite(book.received_at)&&book.received_at>0);
  if(!issues.length&&observed.length>0&&observed.every(book=>data.as_of-book.received_at>30))issues.push('All loaded detailed price books have been without updates for over 30 seconds.');
  if(issues.length)return {label:data.journal_error||collector==='failed'?'Data system issue':'Feed needs attention',tone:data.journal_error||collector==='failed'?'critical':'warning',issues};
  if(!enabled.length)return {label:'Data setup needed',tone:'neutral',issues:['No market provider is enabled. Open Settings to review data sources.']};
  if(data.control.stopped)return {label:'New trades paused',tone:'warning',issues:['New app entries are paused by the emergency control. Existing exchange orders are unaffected.']};
  return {label:'Data connected',tone:'good',issues:[]};
}

import type {Dashboard,JournalRecord,LabResult,Market,Trader} from './types';
export type InstrumentKind='depth'|'network'|'pipeline'|'timeline'|'forensic'|'lab'|'practice'|'relay'|'systems'|'capital';
export type InstrumentPoint={id:string;label:string;hint:string;value?:number;at?:number;group?:string;state?:'ready'|'blocked'|'unknown'};
export type InstrumentModel={kind:InstrumentKind;points:InstrumentPoint[];links?:[string,string][];bands?:{trainEnd:number;testStart:number;testEnd:number}[];steps?:{label:string;state:'ready'|'blocked'|'unknown'}[];old?:boolean};
export const numeric=(value:unknown):number|null=>value==null||value===''||!Number.isFinite(Number(value))?null:Number(value);
export const shown=(value:unknown,digits=7)=>numeric(value)==null?'—':Number(value).toLocaleString('en-US',{maximumSignificantDigits:digits});
export const timestamp=(at:number|undefined|null)=>at!=null&&Number.isFinite(at)&&at>0?new Date(at*1000).toLocaleString():'Unavailable';
export function freshBook(row:Market,online:boolean,now:number){return online&&row.status==='live'&&row.source_at!=null&&now-row.source_at>=-1&&now-row.source_at<=5&&now-row.received_at>=0&&now-row.received_at<=5&&['crc32_verified','ordered_stream'].includes(row.integrity)}
export function depthModel(market:Market|undefined,online:boolean,now:number):InstrumentModel {
  if(!market||!['crc32_verified','ordered_stream'].includes(market.integrity))return {kind:'depth',points:[]};
  const points:InstrumentPoint[]=[];
  for(const [side,rows] of [['bid',market.bids],['ask',market.asks]] as const){
    rows.slice(0,8).forEach(([rawPrice,rawSize],index)=>{const price=numeric(rawPrice),size=numeric(rawSize);if(price==null||size==null||price<=0||size<=0||!Number.isFinite(price*size))return;points.push({id:side+index,label:(side==='bid'?'Buy':'Sell')+' '+(index+1),value:price*size,group:side,hint:`${shown(price)} ${market.quote} · ${shown(size)} ${market.symbol.split('-')[0]} · displayed value ${shown(price*size)} ${market.quote}`})});
  }
  return {kind:'depth',points,old:!freshBook(market,online,now)};
}
export function walletModel(traders:Trader[],online:boolean,now:number):InstrumentModel {
  const points:InstrumentPoint[]=[],links:[string,string][]=[],tokens=new Set<string>();
  for(const trader of traders.slice(0,10)){
    const snap=trader.snapshot;if(!snap)continue;
    const recent=online&&now-snap.received_at>=0&&now-snap.received_at<=90;
    const id='wallet:'+trader.address;
    points.push({id,label:trader.address.slice(0,6)+'…'+trader.address.slice(-4),group:'wallet',state:recent?'ready':'unknown',hint:`Public wallet ${trader.address} · ${recent?'recent':'old'} snapshot · received ${timestamp(snap.received_at)}`});
    for(const position of snap.positions){if(numeric(position.szi)==null||Number(position.szi)===0)continue;const coin=position.coin;if(!tokens.has(coin)&&tokens.size>=12)continue;if(!tokens.has(coin)){tokens.add(coin);points.push({id:'token:'+coin,label:coin,group:'token',hint:coin+' perpetual position · no price or verified person inferred'})}links.push([id,'token:'+coin]);}
  }
  return {kind:'network',points,links};
}
export function journalModel(records:JournalRecord[],kind:'timeline'|'forensic'|'relay'):InstrumentModel {
  const points:InstrumentPoint[]=[];
  records.slice(0,48).forEach((record,index)=>{
    const signal=record as JournalRecord&{detected_at?:number;decision?:string;symbol?:string};
    const at=numeric(signal.detected_at??record.recorded_at),spread=numeric(record.snapshot?.spread_bps);
    if(kind==='forensic'&&(spread==null||spread<0))return;
    points.push({id:record.id||'record'+index,label:signal.symbol||record.snapshot?.symbol||record.coin||record.title||record.action||'Recorded event',at:at??undefined,value:kind==='forensic'?spread??undefined:undefined,group:signal.decision||record.status||record.analysis?.decision||'observed',hint:`${timestamp(at)} · ${signal.decision||record.status||record.action||'saved observation'}${kind==='forensic'?' · saved spread '+shown(spread)+' bps':''}`});
  });return {kind,points};
}
export function labModel(lab:LabResult|null):InstrumentModel {return {kind:'lab',points:[],bands:lab?.folds.slice(0,12).map(f=>({trainEnd:f.training_end_exclusive,testStart:f.test_start,testEnd:f.test_end_exclusive}))||[]}}
export function practiceModel(data:Dashboard|null):InstrumentModel {
  if(!data)return {kind:'practice',points:[]};
  const cash=numeric(data.account.cash),cost=data.paper.filter(p=>p.status==='open').reduce((sum,p)=>sum+(numeric(p.entry_notional)??0),0);
  return {kind:'practice',points:[...(cash!=null&&cash>=0?[{id:'cash',label:'Virtual cash',value:cash,hint:shown(cash)+' USD simulated cash'}]:[]),...(cost>0&&Number.isFinite(cost)?[{id:'cost',label:'Open entry cost',value:cost,hint:shown(cost)+' USD original entry cost · not current market value'}]:[])]};
}

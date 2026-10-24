import {expect,test} from '@playwright/test';
// SYNTHETIC browser contract. No actual inference, credentials or real trades.
test('AI explanations and semantic search remain read-only and show their source evidence',async({page})=>{
 const writes:string[]=[];const now=Date.now()/1000;
 await page.route('**/api/**',async route=>{const r=route.request(),path=new URL(r.url()).pathname;if(r.method()==='POST')writes.push(path);let body:unknown={records:[]};
 if(path==='/api/dashboard')body={as_of:now,environment:'SYNTHETIC',auth_method:'owner_password',live_trading:false,markets:[],providers:{},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:now,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
 if(path==='/api/intelligence')body={as_of:now,actions:[]};
 if(path==='/api/radar')body={as_of:now,mode:'paper_only',strategy_version:'SYNTHETIC',status:'warming_up',coverage:{universe:0,observed:0,warming_up:0,ready:0,candidates:0},setups:[],limitations:[]};
 if(path==='/api/ai')body=r.method()==='GET'?{enabled:true}:{kind:'explanation',summary:'The idea needs stronger evidence.',caution:'Fees and incomplete history matter.',evidence_ids:['E1'],model:'SYNTHETIC_MODEL',as_of:now,evidence:[{id:'E1',symbol:'SYNTHETIC-BTC-USD',decision:'WAIT',text:'SYNTHETIC PUBLIC EVIDENCE ONLY',source:'SYNTHETIC_PROVIDER',received_at:now}],financial_action:false};
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})});
 await page.setViewportSize({width:390,height:844});await page.goto('/#radar');const ai=page.getByRole('region',{name:'AI research assistant'});
 await ai.getByRole('button',{name:'Explain the current idea',exact:true}).click();await expect(ai).toContainText('The idea needs stronger evidence.');await expect(ai).toContainText('SYNTHETIC PUBLIC EVIDENCE ONLY');await expect(ai).toContainText('WAIT');
 await ai.getByLabel('AI explanation language').selectOption('fr');await ai.getByRole('button',{name:'What could go wrong?',exact:true}).click();
 expect(writes).toEqual(['/api/ai','/api/ai']);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

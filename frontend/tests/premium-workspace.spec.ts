import {expect,test,type Page} from '@playwright/test';

// SYNTHETIC browser fixtures only. No actual account, quote, credential or order.
const NOW=new Date('2026-10-24T12:00:00Z').getTime()/1000;
const PROFILE={capital_usd:'2000',available_cash_usd:'100.12',existing_crypto_exposure_usd:'0',daily_realized_pnl_usd:'0',risk_per_trade_pct:'0.5',max_position_pct:'5',max_crypto_exposure_pct:'25',daily_loss_limit_pct:'2',currency:'USD',source:'USER_DECLARED_UNVERIFIED',confirmed_at:NOW,stale:false,stale_reasons:[],execution_enabled:false};
async function fixture(page:Page){
 let stopped=false;const writes:string[]=[];let accountReads=0;
 await page.clock.install({time:new Date(NOW*1000)});
 await page.route('**/api/**',async route=>{
  const request=route.request(),path=new URL(request.url()).pathname;
  if(request.method()==='POST')writes.push(path);
  let value:unknown={records:[]};
  if(path==='/api/dashboard')value={as_of:NOW,environment:'SYNTHETIC_TEST_ONLY',auth_method:'owner_password',live_trading:true,markets:[{provider:'kraken',symbol:'BTC-USD',instrument:'spot',quote:'USD',bid:'60000',ask:'60001',mid:'60000.5',source_at:NOW,received_at:NOW,spread_bps:'0.16',imbalance:'0',visible_depth_usd:'10000',status:'live',integrity:'crc32_verified',bids:[['60000','1']],asks:[['60001','1']]}],providers:{kraken:{state:'connected'}},signals:[],control:{stopped},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC_FIXTURE',last_persist:NOW,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
  if(path==='/api/intelligence')value={as_of:NOW,actions:[]};
  if(path==='/api/capital')value={profile:PROFILE,execution_enabled:false};
  if(path==='/api/connections')value={provider:'kraken',connected:true,credential_entry_enabled:true,order_submission_enabled:!stopped,live_order_submission_enabled:true,status:'connected',connection:{id:'SYNTHETIC-CONNECTION',verified_at:NOW,permissions:[],can_trade:true},markets:[{symbol:'BTC-USD',ready:true}],active_order:null};
  if(path==='/api/connections/kraken/account'){accountReads++;value={verified_at:NOW,balances:[{asset:'ZUSD',balance:'100.12',available:'100.12'},{asset:'USDC',balance:'500',available:'500'}],open_orders:[],fees_note:'SYNTHETIC ACCOUNT FIXTURE'}}
  if(path==='/api/connections/kraken/orders')value={as_of:NOW,orders:[{id:'SYNTHETIC-JOURNAL',status:'validated',symbol:'BTC-USD',side:'buy',quantity:'0.0001',limit_price:'60001',recorded_at:NOW,order_ids:[],message:'SYNTHETIC: review only'}]};
  if(path==='/api/control'){stopped=request.postDataJSON().stopped;value={stopped}}
  if(path==='/api/radar')value={as_of:NOW,last_scan_at:NOW,mode:'paper_only',status:'warming_up',strategy_version:'SYNTHETIC',coverage:{universe:600,observed:40,warming_up:40,ready:0,candidates:0},setups:[],limitations:[],feed:{state:'connected',received_at:NOW,event_trigger:'bbo'},watchlist:[{market_id:'kraken:BTC/USD',symbol:'BTC-USD',provider:'kraken',price:'60000.5',source_at:NOW,received_at:NOW,completed_bins:3,required_bins:10,baseline_ready:false,change_5m_bps:null,range_5m_bps:null,price_kind:'observed midpoint',executable:false}]};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(value)});
 });
 return {writes,accountReads:()=>accountReads};
}
async function reviewImage(page:Page,name:string){
 await page.evaluate(()=>{const label=document.createElement('div');label.textContent='SYNTHETIC DESIGN REVIEW — NO REAL BALANCES OR TRADES';label.style.cssText='position:fixed;top:0;left:0;right:0;padding:5px;background:#4a2756;color:white;text-align:center;font:9px sans-serif;z-index:9999';document.body.append(label)});
 const encoded=(await page.screenshot({type:'jpeg',quality:55,fullPage:false})).toString('base64');
 const total=Math.ceil(encoded.length/6000);
 for(let index=0;index<total;index++)console.log('DESIGN_REVIEW '+name+' '+index+' '+total+' '+encoded.slice(index*6000,(index+1)*6000));
}

test('Live Money deep link reads real-account fixtures only on request and never mixes paper cash or USDC into USD',async({page})=>{
 await page.setViewportSize({width:390,height:844});const state=await fixture(page);
 await page.goto('/#live-money');
 await expect(page.getByRole('heading',{name:'Live Money.'})).toBeVisible();
 const metrics=page.getByLabel('Actual Kraken account summary');
 await expect(metrics.getByText('$10,000.00',{exact:true})).toHaveCount(0);
 await expect(metrics.getByText('$100.12',{exact:true})).toHaveCount(0);
 expect(state.accountReads()).toBe(0);
 await page.getByRole('button',{name:'Refresh balances and open orders',exact:true}).click();
 await expect(metrics.getByText('$100.12',{exact:true})).toBeVisible();
 await expect(metrics.getByText('$600.12',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Review only · not sent',{exact:true})).toBeVisible();
 expect(state.writes).toEqual([]);
 expect(state.accountReads()).toBe(1);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await reviewImage(page,'live-money-mobile');
});

test('pausing new app trades immediately blocks the real ticket and does not submit or cancel an exchange order',async({page})=>{
 const state=await fixture(page);await page.goto('/#live-money');
 await page.getByRole('button',{name:'Refresh balances and open orders',exact:true}).click();
 await page.getByRole('button',{name:'Pause new trades',exact:true}).click();
 await expect(page.getByRole('button',{name:'Resume new trades',exact:true})).toBeVisible();
 await page.getByRole('navigation',{name:'Live Money sections'}).getByRole('button',{name:'Trade ticket',exact:false}).click();
 await page.getByLabel('Kraken real order market',{exact:true}).selectOption('BTC-USD');
 await page.getByLabel('Kraken real order quantity',{exact:true}).fill('0.0001');
 await page.getByLabel('Kraken real order limit price',{exact:true}).fill('60001');
 await expect(page.getByRole('button',{name:'Validate and review · no order placed',exact:true})).toBeDisabled();
 expect(state.writes).toEqual(['/api/control']);
});

test('public radar explains partial baselines without invented five-minute returns and marks old observations stale',async({page})=>{
 await page.setViewportSize({width:1440,height:1000});const state=await fixture(page);await page.goto('/#radar');
 await expect(page.getByRole('heading',{name:'Trade Ideas.'})).toBeVisible();
 const pulse=page.getByRole('region',{name:'Opportunity radar'}).getByLabel('Public market observations');
 await expect(pulse.getByText('3 / 10',{exact:false})).toBeVisible();
 await expect(pulse.getByText('No complete five-minute estimate',{exact:true})).toBeVisible();
 await expect(pulse.getByText('Fresh observation',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Watching',exact:true}).click();
 expect(state.writes).toEqual([]);
 await page.clock.fastForward(6000);
 await expect(pulse.getByText('Stale',{exact:true})).toBeVisible();
 await expect(pulse.getByText('Fresh observation',{exact:true})).toHaveCount(0);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('premium desktop mission control provides direct radar and capital navigation without invented balances',async({page})=>{
 await page.setViewportSize({width:1440,height:1000});await fixture(page);await page.goto('/');
 await expect(page.getByRole('region',{name:'Workspace overview'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Open Live Money',exact:false})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 await reviewImage(page,'mission-control-desktop');
 await page.getByRole('button',{name:'Open Live Money',exact:false}).click();
 await expect(page.getByRole('heading',{name:'Live Money.'})).toBeVisible();
 await expect(page).toHaveURL(/#live-money$/);
});

import {expect,test,type Page} from '@playwright/test';

// SYNTHETIC acceptance fixtures. Never production prices, balances or orders.
const NOW=Date.parse('2026-10-24T12:00:00Z')/1000;
const MARKET={provider:'kraken',symbol:'BTC-USD',instrument:'spot',quote:'USD',bid:'105.8',ask:'106',mid:'105.9',spread_bps:'18',imbalance:'0',visible_depth_usd:'10000',source_at:NOW,received_at:NOW,status:'live',integrity:'crc32_verified',bids:[['105.8','10']],asks:[['106','10']]};
async function fixture(page:Page,options:{gap?:boolean;invalid?:boolean;outage?:boolean}={}) {
 const writes:string[]=[];const reads:string[]=[];
 await page.clock.install({time:new Date(NOW*1000)});
 await page.route('**/api/**',async route=>{
  const request=route.request(),url=new URL(request.url()),path=url.pathname;
  if(request.method()!=='GET')writes.push(path);else reads.push(path);
  let body:unknown={records:[]};
  if(path==='/api/dashboard') {
   if(options.outage){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'SYNTHETIC disconnected feed'})});return}
   body={as_of:NOW,environment:'SYNTHETIC_TEST_ONLY',auth_method:'owner_password',live_trading:true,markets:[MARKET,{...MARKET,provider:'hyperliquid',symbol:'ETH-USDC-PERP',quote:'USDC',instrument:'perpetual',integrity:'ordered_stream',source_at:NOW-90,received_at:NOW-90}],providers:{kraken:{state:'connected'},hyperliquid:{state:'connected'},coinbase:{state:'disabled',reason:'SYNTHETIC provider permission disabled'}},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[{id:'SYNTHETIC-PAPER',symbol:'BTC-USD',provider:'kraken',status:'open',quantity:'1',entry_price:'103',entry_notional:'103',entry_fee:'1',opened_at:NOW-1200}],funding:[],trades:[{provider:'kraken',symbol:'BTC-USD',price:'105.8',quantity:'2',source_at:NOW-30,side:'buy'},{provider:'other',symbol:'BTC-USD',price:'105',quantity:'1',source_at:NOW-30,side:'buy'},{provider:'kraken',symbol:'BTC-USD',price:'105',quantity:'1',source_at:NOW+300,side:'buy'}],strategy_version:'SYNTHETIC',last_persist:NOW,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
  }
  if(path==='/api/price-history') {
   const interval=Number(url.searchParams.get('interval')||1);
   const candles=Array.from({length:60},(_,i)=>({at:NOW-(59-i)*interval*60,open:String(100+i/10),high:String(100.5+i/10),low:String(99.5+i/10),close:String(100+i/10),volume:String(i+1),closed:i<59})).filter((_,i)=>!options.gap||i!==25);
   if(options.invalid)candles[candles.length-1].at=NOW+3600;
   body={provider:url.searchParams.get('provider'),symbol:url.searchParams.get('symbol'),interval_minutes:interval,received_at:NOW,source_at:candles.at(-1)!.at,executable:false,candles};
  }
  if(path==='/api/intelligence')body={as_of:NOW,actions:[]};
  if(path==='/api/suggestions')body={as_of:NOW,cards:[],limitations:[],strategy_version:'SYNTHETIC'};
  if(path==='/api/traders')body={traders:[],events:[],intelligence:{as_of:NOW,actions:[]}};
  if(path==='/api/radar')body={as_of:NOW,last_scan_at:NOW,mode:'paper_only',status:'warming_up',strategy_version:'SYNTHETIC',coverage:{universe:600,observed:2,warming_up:2,ready:0,candidates:0},setups:[],limitations:[]};
  if(path==='/api/assets')body={items:[],page:1,limit:25,total:0,counts:{catalogue:0,global_prices:0,venue_markets:2,streaming_quotes:1},as_of:NOW,watched_markets:[],extra_book_limit:6,sessions:{kraken:{state:'connected'}},errors:{},catalogue_received_at:null,global_quotes_received_at:null,coverage:'SYNTHETIC',attribution:{label:'SYNTHETIC',url:'https://coinpaprika.com',license:'SYNTHETIC'}};
  if(path==='/api/capital')body={profile:null,execution_enabled:false};
  if(path==='/api/connections')body={provider:'kraken',connected:false,credential_entry_enabled:true,order_submission_enabled:false,live_order_submission_enabled:true,status:'not_connected',connection:null,markets:[],active_order:null};
  if(path==='/api/connections/kraken/orders')body={as_of:NOW,orders:[]};
  if(path==='/api/plans')body={id:'SYNTHETIC-PLAN',decision:'WAIT',provider:'kraken',symbol:'BTC-USD',mode:'paper',detected_at:NOW,maximum_modeled_loss:'11',target_net_profit:'9',risk_reward:'0.8',snapshot:MARKET,stages:{finder:{facts:[]},skeptic:{objections:['SYNTHETIC modeled costs exceed the intended reward.'],unknowns:['Profit probability is not validated.']},risk:{rules:[]},decision:{meaning:'Checking a plan placed no trade.'}}};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
 return {writes,reads};
}
async function review(page:Page,name:string) {
 await page.evaluate(()=>{const tag=document.createElement('div');tag.textContent='SYNTHETIC VISUAL REVIEW · NO REAL PRICES OR MONEY';tag.style.cssText='position:fixed;top:0;left:0;right:0;z-index:9999;background:#3c294a;color:#fff;font:8px monospace;text-align:center;padding:3px';document.body.append(tag)});
 const data=(await page.screenshot({type:'jpeg',quality:65,fullPage:false})).toString('base64');
 const count=Math.ceil(data.length/200);for(let i=0;i<count;i++)console.log('MISSION_REVIEW '+name+' '+i+' '+count+' '+data.slice(i*200,(i+1)*200));
}

for(const width of [320,390])test('complete beginner mobile journey at '+width+'px preserves the money boundary',async({page})=>{
 await page.setViewportSize({width,height:844});const state=await fixture(page);await page.goto('/');
 const dock=page.getByRole('navigation',{name:'Quick navigation'});
 await expect(dock.getByRole('button')).toHaveCount(5);
 for(const name of ['Home','Markets','Trade Ideas','Big Traders','Live Money'])await expect(dock.getByRole('button',{name:'Quick '+name,exact:true})).toBeVisible();
 const chart=page.getByRole('region',{name:'Live market chart'});await expect(chart.getByTestId('history-price-line')).toBeAttached();
 await chart.getByRole('button',{name:'Plan with practice money',exact:false}).click();
 await expect(page.getByRole('heading',{name:'Trade Ideas.'})).toBeVisible();await expect(page.getByLabel('Practice plan market')).toHaveValue('kraken:BTC-USD');
 const plan=page.locator('#practice-planning');await expect(plan).toBeFocused();await expect(plan).toContainText('It records no trade');
 await plan.getByLabel('Stop price (USD)',{exact:true}).fill('95');await plan.getByLabel('Target price (USD)',{exact:true}).fill('120');
 await plan.getByRole('button',{name:'Check practice plan',exact:false}).click();await expect(plan).toContainText('Checking a plan placed no trade.');expect(state.writes).toEqual(['/api/plans']);
 await dock.getByRole('button',{name:'Quick Live Money',exact:true}).click();await expect(page.getByText('REAL MONEY · YOUR KRAKEN ACCOUNT',{exact:true})).toBeVisible();
 await expect(page.getByText('Each exact order requires a separate review and your individual approval.',{exact:true})).toBeVisible();
 await dock.getByRole('button',{name:'Quick Markets',exact:true}).click();await expect(page.getByRole('heading',{name:'Markets.'})).toBeVisible();
 await page.getByRole('button',{name:'Open navigation',exact:true}).click();await expect(page.getByRole('button',{name:'Settings',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'More Tools',exact:true}).click();await page.getByRole('button',{name:'Practice',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Practice.'})).toBeVisible();expect(state.writes).toEqual(['/api/plans']);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('mobile chart supports real candle inspection, zoom, volume and recorded markers without filling gaps',async({page})=>{
 await page.setViewportSize({width:390,height:844});const state=await fixture(page,{gap:true});await page.goto('/');const chart=page.getByLabel('Exchange price history',{exact:true});
 const path=chart.getByTestId('history-price-line');await expect(path).toBeAttached();expect(((await path.getAttribute('d'))?.match(/M/g)||[]).length).toBe(2);
 await expect(chart.getByTestId('history-volume-bar')).toHaveCount(59);await expect(chart.getByTestId('recorded-chart-marker')).toHaveCount(2);
 await chart.getByRole('button',{name:'Zoom in on price history',exact:true}).click();await expect(chart).toContainText('29 of 59 candles shown');await expect(chart.getByLabel('Browse earlier price history')).toBeVisible();
 const svg=chart.getByRole('img');await svg.focus();await page.keyboard.press('ArrowLeft');await expect(chart.getByLabel('Inspected candle prices')).toContainText('Volume');await expect(chart.locator('.live-market-crosshair')).toHaveCount(2);
 await chart.getByLabel('Price history chart style').selectOption('candles');await expect(chart.locator('[data-closed=false]')).toHaveCount(1);
 await chart.getByLabel('Price history time range').selectOption('5');await expect(chart).toContainText('59 actual exchange candles');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect(state.writes).toEqual([]);
});

test('connection instruments separate fresh, old, unavailable and disconnected evidence',async({page})=>{
 await page.setViewportSize({width:390,height:844});const options={outage:false};await fixture(page,options);await page.goto('/');
 const feeds=page.getByRole('region',{name:'Provider connections'});await expect(feeds.locator('.feed-chip.fresh')).toContainText('Kraken');await expect(feeds.locator('.feed-chip.old')).toContainText('Hyperliquid');await expect(feeds.locator('.feed-chip.unavailable')).toContainText('Coinbase');
 const path=page.getByTestId('history-price-line');const before=await path.getAttribute('d');options.outage=true;await page.clock.runFor(2200);await expect(feeds.locator('.feed-chip.disconnected')).toHaveCount(3);expect(await path.getAttribute('d')).toBe(before);
});

test('invalid or future candles never render a historical price',async({page})=>{
 const state=await fixture(page,{invalid:true});await page.goto('/');const chart=page.getByLabel('Exchange price history',{exact:true});await expect(chart).toContainText('Exchange history could not be verified.');await expect(chart.getByTestId('history-price-line')).toHaveCount(0);await expect(chart.getByTestId('history-volume-bar')).toHaveCount(0);expect(state.writes).toEqual([]);
});

test('orbital mobile and desktop visual review uses labeled synthetic evidence',async({page})=>{
 await fixture(page);await page.setViewportSize({width:390,height:844});await page.goto('/');await expect(page.getByTestId('history-price-line')).toBeAttached();await review(page,'home-mobile');
 const history=page.getByLabel('Exchange price history',{exact:true});await history.scrollIntoViewIfNeeded();await review(page,'chart-mobile');
 await page.setViewportSize({width:1440,height:1100});await page.evaluate(()=>scrollTo(0,0));await review(page,'home-desktop');
});

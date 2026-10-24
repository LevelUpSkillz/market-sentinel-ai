import {expect,test,type Page} from '@playwright/test';
// SYNTHETIC public data and authority fixtures only. No Google account or real order.
const NOW=Date.parse('2026-10-24T12:00:00Z')/1000;
const BOOK={provider:'kraken',symbol:'BTC-USD',instrument:'spot',quote:'USD',bid:'100',ask:'101',mid:'100.5',spread_bps:'10',imbalance:'0',visible_depth_usd:'10000',source_at:NOW,received_at:NOW,status:'live',integrity:'crc32_verified',bids:[['100','10']],asks:[['101','10']]};
async function fixture(page:Page,options:{viewer?:boolean;anonymous?:boolean;phase?:string}={}) {
 const requests:{path:string;method:string}[]=[];await page.clock.install({time:new Date(NOW*1000)});
 await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname;requests.push({path,method:req.method()});let body:unknown={records:[]};let status=200;
  const clock=Date.now()/1000;
  if(path==='/api/auth/options')body={google_ready:true,owner_google_enabled:true,research_url:'https://market-research.getlevelupskillz.com',owner_url:'https://market.getlevelupskillz.com',invite_only:true};
  if(path==='/api/dashboard'){
   if(options.anonymous){status=401;body={detail:'SYNTHETIC sign-in required'}}
   else body={role:options.viewer?'viewer':'owner',read_only:!!options.viewer,as_of:NOW,environment:'SYNTHETIC_TEST_ONLY',auth_method:options.viewer?'supabase_google':'owner_password',live_trading:!options.viewer,markets:[BOOK,{...BOOK,provider:'coinbase'},{...BOOK,provider:'hyperliquid',symbol:'BTC-USDC-PERP',quote:'USDC',instrument:'perpetual',integrity:'ordered_stream'}],providers:{kraken:{state:'connected'},coinbase:{state:'connected'},hyperliquid:{state:'connected'}},signals:[],control:{stopped:!!options.viewer},account:options.viewer?null:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:NOW,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
  }
  if(path==='/api/intelligence')body={as_of:NOW,actions:[]};
  if(path==='/api/traders')body={traders:[],events:[],intelligence:{as_of:NOW,actions:[]}};
  if(path==='/api/trader-directory'){status=503;body={detail:'SYNTHETIC unavailable directory'}}
  if(path==='/api/radar')body={as_of:NOW,last_scan_at:NOW,mode:'paper_only',status:'warming_up',strategy_version:'SYNTHETIC',coverage:{universe:600,observed:3,warming_up:3,ready:0,candidates:0},setups:[],limitations:[]};
  if(path==='/api/price-history')body={provider:url.searchParams.get('provider'),symbol:url.searchParams.get('symbol'),interval_minutes:Number(url.searchParams.get('interval')),received_at:NOW,source_at:NOW,executable:false,candles:[{at:NOW-120,open:'99',high:'102',low:'98',close:'100',volume:'2',closed:true},{at:NOW-60,open:'100',high:'104',low:'99',close:'103',volume:'3',closed:true},{at:NOW,open:'103',high:'105',low:'101',close:'104',volume:'1',closed:false}]};
  if(path==='/api/suggestions') {
   const old=options.phase==='old';
   body={as_of:NOW,cards:options.phase==='missing'?[]:[{id:'SYNTHETIC_IDEA',symbol:'BTC-USD',provider:'kraken',state:old?'skip':'watch',decision:old?'NO-GO':'WAIT',title:'SYNTHETIC Bitcoin watch',reason:old?'The source needs an update.':'SYNTHETIC observed condition; wait for a trigger',levels:old?{entry_trigger:null,entry_limit:null,stop:null,target:null}:{entry_trigger:'101',entry_limit:'102',stop:'95',target:'110'},cost_bps:old?null:'80',facts:['SYNTHETIC market observation'],checks:[],source_at:old?NOW-10:NOW,received_at:old?NOW-10:NOW,data_status:old?'old':'fresh',expires_at:null,profiles:[],success_probability_pct:null,odds_note:'No validated prediction.',execution:'Practice review only'}],strategy_version:'SYNTHETIC',limitations:[]};
  }
  if(path==='/api/tokens'){
   const section=url.searchParams.get('section');const predicted=section?.startsWith('predicted-');body={section,as_of:NOW,page:1,limit:25,total:predicted?0:2,status:predicted?'unavailable':'available',source:'kraken',basis:predicted?'No validated forecast available.':'Reported 24-hour change only.',items:predicted?[]:[{id:'kraken:BTC/USD',name:'Bitcoin',symbol:'BTC',provider:'kraken',currency:'USD',chart_symbol:'BTC-USD',detailed:true,quote:{price:'100.5',status:'live',source_at:NOW,received_at:NOW,change_24h_pct:'2.5'}},{id:'kraken:ETH/USD',name:'Ethereum',symbol:'ETH',provider:'kraken',currency:'USD',chart_symbol:'ETH-USD',detailed:false,quote:{price:'50',status:'live',source_at:NOW,received_at:NOW,change_24h_pct:'-1'}}]};
  }
  await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });return requests;
}

test('Google login opens the fixed identity flow and keeps the existing owner login available',async({page})=>{
 await page.setViewportSize({width:390,height:844});const requests=await fixture(page,{anonymous:true});await page.goto('/');
 const login=page.getByRole('region',{name:'Google sign-in',exact:true});await expect(login).toBeVisible();await expect(login.getByRole('link',{name:'Continue with Google',exact:false})).toHaveAttribute('href','https://market-research.getlevelupskillz.com/api/auth/google/start');await expect(login).toContainText('full workspace');await expect(page.getByLabel('Owner password')).toBeVisible();expect(requests.filter(r=>r.method!=='GET')).toEqual([]);
});

test('Google research viewer deep links cannot expose owner controls or trigger private reads',async({page})=>{
 await page.setViewportSize({width:390,height:844});const requests=await fixture(page,{viewer:true});await page.goto('/#live-money');await expect(page.getByRole('heading',{name:'Home.'})).toBeVisible();
 const dock=page.getByRole('navigation',{name:'Quick navigation'});await expect(dock.getByRole('button')).toHaveCount(4);await expect(dock.getByRole('button',{name:'Quick Live Money',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Plan with practice money',exact:false})).toHaveCount(0);
 await dock.getByRole('button',{name:'Quick Markets',exact:true}).click();await expect(page.getByRole('region',{name:'Token markets'})).toContainText('Bitcoin');await dock.getByRole('button',{name:'Quick Trade Ideas',exact:true}).click();await expect(page.locator('#practice-planning')).toHaveCount(0);await dock.getByRole('button',{name:'Quick Big Traders',exact:true}).click();await expect(page.getByRole('heading',{name:'Big Traders.'})).toBeVisible();
 expect(requests.filter(r=>r.method!=='GET')).toEqual([]);expect(requests.filter(r=>/^\/api\/(connections|capital|members|suggestions)/.test(r.path))).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('token sections use plain names and actual moves while forecasts remain unavailable',async({page})=>{
 await page.setViewportSize({width:390,height:844});await fixture(page);await page.goto('/#live-markets');const tokens=page.getByRole('region',{name:'Token markets'});await expect(tokens.getByRole('heading',{name:'Bitcoin',exact:true})).toBeVisible();await expect(tokens.getByRole('heading',{name:'Ethereum',exact:true})).toBeVisible();await expect(tokens.getByText('perpetual',{exact:false})).toHaveCount(0);await expect(tokens.getByText('EUR',{exact:true})).toHaveCount(0);
 const sections=tokens.getByRole('navigation',{name:'Market sections'});for(const label of ['New listings','Gainers','Decliners','Top performers','Underperformers','Predicted leaders','Predicted laggards'])await expect(sections.getByRole('button',{name:label,exact:true})).toBeVisible();
 await sections.getByRole('button',{name:'Predicted leaders',exact:true}).click();await expect(tokens.getByRole('heading',{name:'No validated forecast available',exact:true})).toBeVisible();await expect(tokens.locator('.token-row')).toHaveCount(0);
 const selector=page.getByLabel('Live chart market',{exact:true});await expect(selector.locator('option')).toHaveText(['Bitcoin']);await expect(page.getByRole('region',{name:'Simultaneous provider monitor'}).locator('.monitor-card')).toHaveCount(3);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('brief feed gaps retain idea details and do not flash a trading rejection',async({page})=>{
 await page.setViewportSize({width:390,height:844});const options={phase:'fresh'};const requests=await fixture(page,options);await page.goto('/');const ideas=page.getByRole('region',{name:'Trade suggestions'});await expect(ideas.getByText('Watch',{exact:true})).toBeVisible();await expect(ideas.getByText('Watch for this price',{exact:true})).toBeVisible();
 options.phase='missing';await page.clock.runFor(2200);await expect(ideas.getByText('Watch for this price',{exact:true})).toBeVisible();await expect(ideas.getByText('Updating data',{exact:true})).toBeVisible();await expect(ideas.getByText('Skip for now',{exact:true})).toHaveCount(0);
 options.phase='old';await page.clock.runFor(2200);await expect(ideas).toContainText('Previous levels · do not use for entry');await expect(ideas.getByText('101 USD',{exact:true})).toBeVisible();await expect(ideas.getByText('Practice ready',{exact:true})).toHaveCount(0);expect(requests.filter(r=>r.method!=='GET')).toEqual([]);
});

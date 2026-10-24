import {expect,test,type Page} from '@playwright/test';
// All numbers, identities and prices here are synthetic test evidence only.
const NOW=1800000000;const ADDRESS='0x'+'a'.repeat(40);
async function mock(page:Page){
 const writes:string[]=[];await page.clock.install({time:new Date(NOW*1000)});
 await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),path=url.pathname;if(req.method()!=='GET')writes.push(path);let body:unknown={records:[]};
 if(path==='/api/dashboard')body={as_of:NOW,environment:'SYNTHETIC_TEST',auth_method:'owner_password',live_trading:false,markets:[{provider:'kraken',symbol:'BTC-USD',instrument:'spot',quote:'USD',bid:'100',ask:'101',mid:'100.5',spread_bps:'100',imbalance:'0',visible_depth_usd:'10000',source_at:NOW,received_at:NOW,status:'live',integrity:'crc32_verified',bids:[['100','10']],asks:[['101','10']]}],providers:{kraken:{state:'connected'}},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:NOW,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
 if(path==='/api/intelligence')body={as_of:NOW,actions:[]};
 if(path==='/api/radar')body={as_of:NOW,mode:'paper_only',strategy_version:'SYNTHETIC',status:'warming_up',coverage:{universe:0,observed:0,warming_up:0,ready:0,candidates:0},setups:[],limitations:[]};
 if(path==='/api/price-history')body={provider:url.searchParams.get('provider'),symbol:url.searchParams.get('symbol'),interval_minutes:Number(url.searchParams.get('interval')),received_at:NOW,source_at:NOW,executable:false,candles:[{at:NOW-120,open:'99',high:'102',low:'98',close:'100',closed:true},{at:NOW-60,open:'100',high:'104',low:'99',close:'103',closed:true},{at:NOW,open:'103',high:'105',low:'101',close:'104',closed:false}]};
 if(path==='/api/suggestions')body={as_of:NOW,strategy_version:'SYNTHETIC',limitations:[],cards:[{id:'SYNTHETIC',symbol:'BTC-USD',provider:'kraken',state:'watch',decision:'WAIT',title:'Watch BTC for a possible entry',reason:'SYNTHETIC observed condition; wait for the price trigger',levels:{entry_trigger:'101',entry_limit:'102',stop:'99',target:'110'},cost_bps:'85',facts:['SYNTHETIC observed price activity'],checks:[],source_at:NOW,received_at:NOW,expires_at:NOW+30,profiles:[{address:ADDRESS,direction:'long',symbol:'BTC-USDC-PERP',position_received_at:NOW,position_recent:true,history_received_at:NOW,completed_positions:12,historical_win_rate_pct:75,net_before_funding_usdc:'10',truncated:true,source:'SYNTHETIC history',reason:'Plan independently',note:'Perpetual position'}],success_probability_pct:null,odds_note:'Trader win rates are not your odds.',execution:'Practice review only'}]};
 if(path==='/api/traders')body={traders:[],events:[],intelligence:{as_of:NOW,actions:[]}};
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)})});return writes;
}

test('simple navigation and six-step guide explain decisions without creating a trade',async({page})=>{
 await page.setViewportSize({width:390,height:844});const writes=await mock(page);await page.goto('/');
 await page.getByRole('button',{name:'Show me how',exact:true}).click();const guide=page.getByRole('dialog',{name:'Start with the prices'});
 await expect(guide).toBeVisible();await expect(guide).toContainText('never creates a trade');
 for(let i=0;i<5;i++)await page.getByRole('dialog').getByRole('button',{name:'Next',exact:true}).click();
 await expect(page.getByRole('dialog')).toContainText('Preview is not buying');await expect(page.getByRole('dialog')).toContainText('exact approval');
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
 await page.getByRole('button',{name:'Show me how',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Open Prices',exact:false}).click();
 await expect(page.getByRole('heading',{name:'Prices.'})).toBeVisible();expect(writes).toEqual([]);
 await page.getByLabel('Open navigation').click();await expect(page.getByRole('button',{name:'Strategy Lab',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'More tools',exact:true}).click();await expect(page.getByRole('button',{name:'Practice',exact:true})).toBeVisible();
});

test('exchange history draws a real series immediately with line and candlestick modes',async({page})=>{
 const writes=await mock(page);await page.goto('/');const chart=page.getByLabel('Exchange price history',{exact:true});
 await expect(chart.getByTestId('history-price-line')).toHaveAttribute('d',/L/);await expect(chart).toContainText('3 actual exchange candles');await expect(chart).toContainText('still changing');
 await chart.getByLabel('Price history chart style').selectOption('candles');await expect(chart.locator('.candle-up')).toHaveCount(3);expect(writes).toEqual([]);
});

test('suggestions show actual profile evidence separately from unvalidated odds and disable stale entry levels',async({page})=>{
 await page.setViewportSize({width:390,height:844});const writes=await mock(page);await page.goto('/');const ideas=page.getByRole('region',{name:'Trade suggestions'});
 await expect(ideas).toContainText('12 completed positions');await expect(ideas).toContainText('75.0% historical wins');await expect(ideas.getByText('Not validated',{exact:true})).toBeVisible();
 await expect(ideas).toContainText('different market');await expect(ideas.getByText('Watch for this price',{exact:true})).toBeVisible();
 await page.clock.runFor(6500);await expect(ideas.getByText('Watch for this price',{exact:true})).toHaveCount(0);await expect(ideas).toContainText('Wait for a fresh check');
 await ideas.getByRole('button',{name:'View trader’s profile and actions',exact:false}).click();await expect(page.getByRole('heading',{name:'Big Traders.'})).toBeVisible();expect(writes).toEqual([]);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});


test('missing historical candles leave a visible gap rather than an invented price line',async({page})=>{
 await mock(page);
 await page.route('**/api/price-history?*',async route=>{const url=new URL(route.request().url());await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({provider:'kraken',symbol:'BTC-USD',interval_minutes:1,received_at:NOW,source_at:NOW,executable:false,candles:[{at:NOW-180,open:'99',high:'102',low:'98',close:'100',closed:true},{at:NOW-120,open:'100',high:'104',low:'99',close:'103',closed:true},{at:NOW,open:'103',high:'105',low:'101',close:'104',closed:false}]})})});
 await page.goto('/');const path=page.getByTestId('history-price-line');await expect(path).toBeAttached();expect(((await path.getAttribute('d'))?.match(/M/g)||[]).length).toBe(2);
});

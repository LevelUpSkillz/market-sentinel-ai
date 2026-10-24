import { expect, test } from '@playwright/test';

test('unauthenticated workspace shows no invented financial data',async({page})=>{
  await page.route('**/api/**',route=>route.fulfill({status:401,body:'Authentication required'}));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Home.'})).toBeVisible();
  await expect(page.getByLabel('Owner password')).toBeVisible();
  await expect(page.getByText('Sign in to see your trade ideas',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Show me how',exact:true})).toBeVisible();
  await expect(page.getByText('$10,000')).toHaveCount(0);
});
test('mobile navigation reaches the research and live capital workspaces',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.route('**/api/**',route=>route.fulfill({status:401,body:'Authentication required'}));
  await page.goto('/');
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Markets',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Markets.'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Indicative swap estimates'})).toBeVisible();
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'More Tools',exact:true}).click();
  await page.getByRole('button',{name:'Strategy Lab',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Walk-forward strategy lab'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('synthetic history is visibly separate from unvalidated follower odds',async({page})=>{
  const now=Date.now()/1000;
  const address='0x'+'1'.repeat(40);
  const odds={completed:0,minimum_sample:100,missing:0,pending:0,held_out_predictions:0,estimated_success_pct:null,historical_success_pct:null,interval_95_pct:null,meaning:'SYNTHETIC_BROWSER_TEST: one-hour shadow outcomes',reasons:['Insufficient held-out observations'],limitations:['SYNTHETIC TEST FIXTURE']};
  const intel={as_of:now,actions:[{address,label:'SYNTHETIC TEST WALLET',symbol:'BTC-USDC-PERP',side:'long',decision:'WAIT',next_action:'Investigate with a paper risk plan',entry_drift_bps:'1',reasons:['Predictive edge unvalidated'],follow_evidence:odds,source:'SYNTHETIC TEST SOURCE',source_at:now,received_at:now,market_source_at:now,market_received_at:now}]};
  const trader={id:address,address,label:'SYNTHETIC TEST WALLET',freshness:'live',snapshot:{received_at:now,source_at:now,source:'SYNTHETIC TEST SOURCE',account_value:'100000',positions:[]},history:{version:'SYNTHETIC',fills_analyzed:20,complete_cycles:10,historical_win_rate_pct:70,net_before_funding_usdc:'10',profit_factor:'1.2',realized_pnl_drawdown_usdc:'4',median_holding_seconds:3600,unclosed_cycles:0,position_gaps:0,provider_limit_reached:false,source:'SYNTHETIC TEST SOURCE',received_at:now,first_fill_at:now-86400,last_fill_at:now-1,limitations:['SYNTHETIC TEST FIXTURE'],cycles:[],recent_fills:[]}};
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    const body=path==='/api/dashboard'?{as_of:now,environment:'test',auth_method:'cloudflare_access',live_trading:false,markets:[],providers:{},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:now,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false,kind:'indicative_swap_estimates'}}:path==='/api/traders'?{traders:[trader],events:[],intelligence:intel}:path==='/api/intelligence'?intel:{records:[]};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'Big Traders',exact:true}).click();
  await expect(page.getByText('Historical win rate · before funding')).toBeVisible();
  await expect(page.getByText('70%',{exact:true})).toBeVisible();
  await expect(page.locator('.action-card').getByText('Not validated',{exact:true}).first()).toBeVisible();
  await expect(page.locator('.action-card').getByText('70%',{exact:true})).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('all-market search keeps token identity, freshness and depth controls explicit on mobile',async({page})=>{
  const now=Date.now()/1000;
  await page.setViewportSize({width:390,height:844});
  let watched=false;
  await page.route('**/api/**',async route=>{
    const url=new URL(route.request().url());
    const dashboard={as_of:now,environment:'test',auth_method:'cloudflare_access',live_trading:false,markets:[],providers:{},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:now,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false,kind:'indicative_swap_estimates'}};
    let body:unknown={records:[]};
    if(url.pathname==='/api/dashboard')body=dashboard;
    if(url.pathname==='/api/intelligence')body={as_of:now,actions:[]};
    if(url.pathname==='/api/markets/watch'){watched=route.request().postDataJSON().enabled;body={markets:[]}}
    if(url.pathname==='/api/assets'){
      const global=url.searchParams.get('source')==='coinpaprika';
      body={items:[{id:global?'coinpaprika:synthetic-xrp':'kraken:XRP/USD',provider_id:global?'synthetic-xrp':'XRP/USD',source:global?'coinpaprika':'kraken',symbol:'XRP',name:global?'SYNTHETIC XRP TOKEN':'SYNTHETIC XRP/USD',active:true,instrument:global?'aggregate':'spot',quote_currency:'USD',watch_symbol:global?null:'XRP-USD',quote:{price:global?null:'1',status:global?'unavailable':'live',source_at:global?null:now,received_at:global?null:now,volume_24h:null,market_cap:null,change_24h_pct:null,price_kind:'SYNTHETIC TEST QUOTE'}}],page:1,limit:25,total:1,counts:{catalogue:1,global_prices:0,venue_markets:1,streaming_quotes:1},as_of:now,watched_markets:watched?[{id:'kraken:XRP/USD',provider:'kraken',symbol:'XRP-USD'}]:[],extra_book_limit:6,sessions:{kraken:{state:'connected'}},errors:{},catalogue_received_at:now,global_quotes_received_at:null,coverage:'SYNTHETIC TEST FIXTURE: no actual prices.',attribution:{label:'Powered by CoinPaprika',url:'https://coinpaprika.com',license:'SYNTHETIC TEST FIXTURE'}};
    }
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('/');
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Markets',exact:true}).click();
  const directory=page.getByRole('region',{name:'All crypto markets'});
  await expect(directory.getByText('SYNTHETIC XRP/USD',{exact:true})).toBeVisible();
  await page.getByLabel('Search all crypto markets').fill('XRP');
  await expect(directory.getByText('kraken:XRP/USD',{exact:true})).toBeVisible();
  await directory.getByRole('button',{name:'Add detailed book',exact:true}).click();
  await expect(directory.getByRole('button',{name:'Remove detailed book',exact:true})).toBeVisible();
  await page.getByLabel('Market coverage').selectOption('coinpaprika');
  await expect(directory.getByText('coinpaprika:synthetic-xrp',{exact:true})).toBeVisible();
  await expect(directory.locator('.catalogue-price').getByText('unavailable',{exact:true})).toBeVisible();
  await expect(directory.locator('.catalogue-row').getByRole('button',{name:'Add detailed book',exact:true})).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

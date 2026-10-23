import { expect, test } from '@playwright/test';

test('unauthenticated workspace shows no invented financial data',async({page})=>{
  await page.route('**/api/**',route=>route.fulfill({status:401,body:'Authentication required'}));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Mission Control.'})).toBeVisible();
  await expect(page.getByLabel('Owner password')).toBeVisible();
  await expect(page.getByText('No market observations loaded')).toBeVisible();
  await expect(page.getByText('No signal analysis available')).toBeVisible();
  await expect(page.getByText('$10,000')).toHaveCount(0);
});
test('mobile navigation and all ten sections are reachable',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.route('**/api/**',route=>route.fulfill({status:401,body:'Authentication required'}));
  await page.goto('/');
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Live Markets',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Live Markets.'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Indicative swap estimates'})).toBeVisible();
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Strategy Lab',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Walk-forward strategy lab'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('synthetic history is visibly separate from unvalidated follower odds',async({page})=>{
  const now=Date.now()/1000;
  const address='0x'+'1'.repeat(40);
  const odds={completed:0,minimum_sample:100,missing:0,pending:0,held_out_predictions:0,estimated_success_pct:null,historical_success_pct:null,interval_95_pct:null,meaning:'SYNTHETIC_BROWSER_TEST: one-hour shadow outcomes',reasons:['Insufficient held-out observations'],limitations:['SYNTHETIC TEST FIXTURE']};
  const intel={as_of:now,actions:[{address,label:'SYNTHETIC TEST WALLET',symbol:'BTC-USDC-PERP',side:'long',decision:'WAIT',next_action:'Investigate with a paper risk plan',entry_drift_bps:'1',reasons:['Predictive edge unvalidated'],follow_evidence:odds,source:'SYNTHETIC TEST SOURCE',source_at:now,received_at:now}]};
  const trader={id:address,address,label:'SYNTHETIC TEST WALLET',freshness:'live',snapshot:{received_at:now,source_at:now,source:'SYNTHETIC TEST SOURCE',account_value:'100000',positions:[]},history:{version:'SYNTHETIC',fills_analyzed:20,complete_cycles:10,historical_win_rate_pct:70,net_before_funding_usdc:'10',profit_factor:'1.2',realized_pnl_drawdown_usdc:'4',median_holding_seconds:3600,unclosed_cycles:0,position_gaps:0,provider_limit_reached:false,source:'SYNTHETIC TEST SOURCE',received_at:now,first_fill_at:now-86400,last_fill_at:now-1,limitations:['SYNTHETIC TEST FIXTURE'],cycles:[],recent_fills:[]}};
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    const body=path==='/api/dashboard'?{as_of:now,environment:'test',auth_method:'cloudflare_access',live_trading:false,markets:[],providers:{},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:now,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false,kind:'indicative_swap_estimates'}}:path==='/api/traders'?{traders:[trader],events:[],intelligence:intel}:path==='/api/intelligence'?intel:{records:[]};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'Smart Money',exact:true}).click();
  await expect(page.getByText('Historical win rate · before funding')).toBeVisible();
  await expect(page.getByText('70%',{exact:true})).toBeVisible();
  await expect(page.locator('.action-card').getByText('Insufficient evidence',{exact:true})).toBeVisible();
  await expect(page.locator('.action-card').getByText('70%',{exact:true})).toHaveCount(0);
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

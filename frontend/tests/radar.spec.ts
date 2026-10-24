import { expect, test, type Page } from '@playwright/test';

// All amounts, prices, balances, times and signals below are SYNTHETIC TEST FIXTURES.
const FIXED = new Date('2026-10-23T12:00:00Z');
const NOW = FIXED.getTime()/1000;

function dashboard(){
  return {as_of:NOW,environment:'test',auth_method:'cloudflare_access',live_trading:false,
    markets:[{provider:'kraken',symbol:'XRP-USD',instrument:'spot',quote:'USD',bid:'99.9',ask:'100',mid:'99.95',spread_bps:'10',imbalance:'0',visible_depth_usd:'10000',source_at:NOW,received_at:NOW,status:'live',integrity:'crc32_verified',bids:[['99.9','100']],asks:[['100','100']]}],
    providers:{kraken:{state:'connected',reason:null,reconnects:0}},signals:[],control:{stopped:false},
    account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],
    strategy_version:'SYNTHETIC_BROWSER_TEST',last_persist:NOW,journal_error:null,alerts_configured:false,
    changenow:{configured:false,approved:false,kind:'indicative_swap_estimates'}};
}

function radar(withSetup=true){
  return {as_of:NOW,strategy_version:'SYNTHETIC_RADAR_FIXTURE',mode:'paper_only',status:'observing',
    coverage:{universe:1,observed:1,warming_up:0,ready:1,candidates:withSetup?1:0},
    setups:withSetup?[{id:'SYNTHETIC_RADAR_ID',market_id:'kraken:XRP/USD',provider:'kraken',symbol:'XRP-USD',
      decision:'GO',state:'paper_ready',next_action:'SYNTHETIC: paper conditions met',created_at:NOW-10,expires_at:NOW+180,triggered_at:NOW,entry_deadline:NOW+30,
      entry_trigger:'100',entry_limit:'100.2',entry_vwap:'100',stop:'95',target:'112',notional_usd:'250',estimated_round_trip_cost_bps:'90',risk_reward:'2',maximum_modeled_loss:'15',
      success_probability_pct:null,validation_status:'unvalidated',reasons:['SYNTHETIC FIXTURE: no validated predictive edge'],facts:['SYNTHETIC FIXTURE: observed range condition'],source_at:NOW,received_at:NOW}]:[],
    limitations:['SYNTHETIC BROWSER TEST ONLY: no real trading recommendation']};
}

function connection(){
  return {provider:'kraken',status:'provider_app_required',connected:false,order_submission_enabled:false,
    withdrawals_enabled:false,app_hosting_plan:'free',trading_fees:'SYNTHETIC TEST: provider fees require review.',
    requirements:['SYNTHETIC FIXTURE: approved OAuth client not configured.'],
    documentation:'https://docs.kraken.com',fees_url:'https://www.kraken.com/features/fee-schedule'};
}

async function navigate(page:Page,name:string,mobile=false){
  if(mobile)await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name,exact:true}).click();
}

test('real-capital configuration starts blank, saves declared inputs and keeps exchange submission blocked on mobile',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.clock.install({time:FIXED});
  let profile:Record<string,unknown>|null=null;
  const posted:Record<string,string>[]=[];
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    let body:unknown={records:[]};
    if(path==='/api/dashboard')body=dashboard();
    if(path==='/api/intelligence')body={as_of:NOW,actions:[]};
    if(path==='/api/radar')body=radar(false);
    if(path==='/api/connections')body=connection();
    if(path==='/api/capital'){
      if(route.request().method()==='POST'){
        const values=route.request().postDataJSON() as Record<string,string>;
        posted.push(values);
        profile={...values,currency:'USD',source:'USER_DECLARED_UNVERIFIED',confirmed_at:NOW,stale:false,stale_reasons:[],execution_enabled:false};
      }
      body={profile,execution_enabled:false};
    }
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('/');
  await navigate(page,'Live Money',true);
  await page.getByRole('navigation',{name:'Live Money sections'}).getByRole('button',{name:'Budget & limits',exact:false}).click();
  const capital=page.getByRole('region',{name:'Real-capital configuration'});
  await expect(capital.getByLabel('Total real trading capital in USD')).toHaveValue('');
  await expect(capital.getByLabel('Available real cash in USD')).toHaveValue('');
  await expect(capital.getByLabel('Existing real crypto exposure in USD')).toHaveValue('');
  await expect(capital.getByLabel("Today's realized real profit or loss in USD")).toHaveValue('');
  await capital.getByLabel('Total real trading capital in USD').fill('5000');
  await capital.getByLabel('Available real cash in USD').fill('1000');
  await capital.getByLabel('Existing real crypto exposure in USD').fill('200');
  await capital.getByLabel("Today's realized real profit or loss in USD").fill('-10');
  await capital.getByRole('button',{name:'Save real-capital limits',exact:true}).click();
  await expect(capital.getByText('Real-capital limits saved as your declared inputs. No money moved and no exchange order was placed.')).toBeVisible();
  expect(posted).toEqual([{capital_usd:'5000',available_cash_usd:'1000',existing_crypto_exposure_usd:'200',daily_realized_pnl_usd:'-10',risk_per_trade_pct:'0.5',max_position_pct:'5',max_crypto_exposure_pct:'25',daily_loss_limit_pct:'2'}]);
  await page.getByRole('navigation',{name:'Live Money sections'}).getByRole('button',{name:'Connection',exact:false}).click();
  const exchange=page.getByRole('region',{name:'Your Kraken account'});
  await expect(exchange).toContainText('Not connected');
  await expect(exchange).toContainText('Real orders disabled');
  await expect(exchange.getByRole('button',{name:/place|submit|approve.*order/i})).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('an old synthetic GO cannot keep authorizing a paper entry after its market timestamps expire',async({page})=>{
  await page.clock.install({time:FIXED});
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    const body=path==='/api/dashboard'?dashboard():path==='/api/radar'?radar():path==='/api/intelligence'?{as_of:NOW,actions:[]}:{records:[]};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('/');
  const panel=page.getByRole('region',{name:'Opportunity radar'});
  await expect(panel.getByText('GO · PAPER ONLY',{exact:true})).toBeVisible();
  await expect(panel.getByRole('heading',{name:'XRP-USD',exact:true})).toBeVisible();
  for(const label of ['Entry trigger','Maximum entry','Stop hypothesis','Target hypothesis'])await expect(panel.getByText(label,{exact:true})).toBeVisible();
  await expect(panel.getByText('Not validated',{exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Record paper entry',exact:true})).toBeVisible();
  // Polls continue returning the same old server observation, not a newly observed quote.
  await page.clock.fastForward(6000);
  await expect(panel.getByText('GO · PAPER ONLY',{exact:true})).toHaveCount(0);
  await expect(panel.getByRole('button',{name:'Record paper entry',exact:true})).toHaveCount(0);
  await expect(panel.getByText('NO-GO',{exact:true})).toBeVisible();
  await expect(panel.locator('.radar-action').getByText('Wait for fresh provider observations. Retained prices cannot authorize a paper entry.',{exact:true})).toBeVisible();
});

test('real-budget sizing uses radar levels while risk PASS remains distinct from trade approval',async({page})=>{
  await page.clock.install({time:FIXED});
  const postPaths:string[]=[];
  let planInput:unknown=null;
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    let body:unknown={records:[]};
    if(route.request().method()==='POST')postPaths.push(path);
    if(path==='/api/dashboard')body=dashboard();
    if(path==='/api/intelligence')body={as_of:NOW,actions:[]};
    if(path==='/api/radar')body=radar();
    if(path==='/api/capital/plans'){
      planInput=route.request().postDataJSON();
      body={provider:'kraken',symbol:'XRP-USD',risk_decision:'PASS',trade_decision:'WAIT',notional_usd:'200',entry_cost_usd:'201',modeled_loss_usd:'12',net_target_profit_usd:'24',net_reward_risk:'2',risk_budget_usd:'25',remaining_daily_loss_budget_usd:'90',quantity:'2',entry_vwap:'100',stop:'95',target:'112',expires_at:NOW+5,profile_confirmed_at:NOW,source:'USER_DECLARED_UNVERIFIED',validation_status:'unvalidated',execution_enabled:false,snapshot:{provider:'kraken',symbol:'XRP-USD',source_at:NOW,received_at:NOW},reasons:['SYNTHETIC FIXTURE: manually declared capital'],limitations:['SYNTHETIC FIXTURE: no exchange order or proven predictive edge']};
    }
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('/');
  const radarPanel=page.getByRole('region',{name:'Opportunity radar'});
  await radarPanel.getByRole('button',{name:'Size with my real budget',exact:true}).click();
  const realPlan=page.getByRole('region',{name:'Real-capital manual trade plan'});
  await expect(realPlan.getByText('Risk checks passed',{exact:true})).toBeVisible();
  await expect(realPlan.getByText('Trade decision: WAIT.',{exact:true})).toBeVisible();
  await expect(realPlan.getByText('Not validated',{exact:true})).toBeVisible();
  expect(planInput).toEqual({provider:'kraken',symbol:'XRP-USD',stop:'95',target:'112'});
  expect(postPaths).toEqual(['/api/capital/plans']);
  await expect(realPlan.getByRole('button',{name:/place|submit|approve.*order/i})).toHaveCount(0);
});


import { expect, test, type Page } from '@playwright/test';

// Explicitly synthetic browser fixtures. No prices, positions, identities or
// success estimates in this file come from a connected account or live market.
const NOW=1_800_000_000;
const ADDRESS='0x'+'7'.repeat(40);
const OTHER_ADDRESS='0x'+'8'.repeat(40);

type EvidenceFixture={estimate:number|null;completed:number;interval:[number,number]|null};

async function mockBriefing(page:Page,evidence:EvidenceFixture){
  const writes:string[]=[];
  const clock={marketAt:NOW};
  await page.route('**/api/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(request.method()!=='GET')writes.push(request.method()+' '+path);
    const odds={completed:evidence.completed,minimum_sample:100,missing:0,pending:0,
      held_out_predictions:evidence.estimate===null?0:50,estimated_success_pct:evidence.estimate,
      historical_success_pct:evidence.estimate===null?0:61.4,interval_95_pct:evidence.interval,
      meaning:'SYNTHETIC TEST: held-out one-hour follower study, not a real estimate.',
      reasons:evidence.estimate===null?['Too few completed observations and no held-out calibration.']:[],
      limitations:['SYNTHETIC TEST FIXTURE. No actual wallet performance or forecast.']};
    const action={address:ADDRESS,label:'SYNTHETIC TEST WALLET',symbol:'ETH-USDC-PERP',asset:'ETH',
      instrument:'perpetual',quote_currency:'USDC',side:'long',decision:'NO-GO',decision_cause:'nearby_liquidation',
      next_action:'Review nearby liquidation risk before copying',entry_drift_bps:'-25',
      reported_average_entry_price:'2500',current_executable_price:'2493.75',position_size_native_units:'1',
      observation_kind:'current_public_position',
      timing_note:'Current public position snapshot; an opening or exact execution time is not established.',
      market_source_at:clock.marketAt,market_received_at:clock.marketAt,
      reasons:['The observed liquidation price is close to the current market price; a cheaper entry does not remove this risk.'],
      follow_evidence:odds,source:'SYNTHETIC PUBLIC DATA FIXTURE',source_at:NOW,received_at:NOW};
    const intelligence={as_of:clock.marketAt,actions:[action]};
    let body:unknown={records:[]};
    if(path==='/api/dashboard')body={as_of:NOW,environment:'test',auth_method:'cloudflare_access',live_trading:false,
      markets:[],providers:{},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},
      opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:NOW,journal_error:null,
      alerts_configured:false,changenow:{configured:false,approved:false,kind:'indicative_swap_estimates'}};
    else if(path==='/api/intelligence')body=intelligence;
    else if(path==='/api/traders')body={traders:[{id:ADDRESS,address:ADDRESS,label:'SYNTHETIC TEST WALLET',freshness:'live',
      snapshot:{received_at:NOW,source_at:NOW,source:'SYNTHETIC PUBLIC DATA FIXTURE',account_value:'10000',
        data_completeness:'SYNTHETIC TEST FIXTURE',baseline:false,
        positions:[{coin:'ETH',szi:'1',entryPx:'2500',unrealizedPnl:'-6.25',liquidationPx:'2485'}]}},
      {id:OTHER_ADDRESS,address:OTHER_ADDRESS,label:'SYNTHETIC OTHER WALLET',freshness:'live',
        snapshot:{received_at:NOW,source_at:NOW,source:'SYNTHETIC PUBLIC DATA FIXTURE',account_value:'5000',
          data_completeness:'SYNTHETIC TEST FIXTURE',baseline:false,positions:[]}}],
      events:[{id:'SYNTHETIC_INCREASE_EVENT',recorded_at:NOW,address:ADDRESS,coin:'ETH',action:'increased',
        before_size:'0.5',after_size:'1',source:'SYNTHETIC PUBLIC DATA FIXTURE',
        analysis:{decision:'NO-GO',reasons:['SYNTHETIC TEST: observed size increase is not a verified execution instruction.']}},
      {id:'SYNTHETIC_OTHER_WALLET_EVENT',recorded_at:NOW,address:OTHER_ADDRESS,coin:'BTC',action:'reduced',
        before_size:'0.02',after_size:'0.01',source:'SYNTHETIC PUBLIC DATA FIXTURE',
        analysis:{decision:'WAIT',reasons:['SYNTHETIC TEST: this historical review is not a current entry approval.']}}],
      intelligence};
    else if(path==='/api/radar')body={as_of:NOW,strategy_version:'SYNTHETIC',mode:'paper_only',status:'collecting',
      coverage:{universe:0,observed:0,warming_up:0,ready:0,candidates:0},setups:[],limitations:['SYNTHETIC TEST FIXTURE']};
    else if(path==='/api/capital')body={profile:null,execution_enabled:false};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  return {writes,clock};
}

test('tiny unvalidated sample hides success bounds and explains Ethereum entry in plain language',async({page},testInfo)=>{
  await page.clock.install({time:new Date(NOW*1000)});
  await page.setViewportSize({width:390,height:844});
  const {writes}=await mockBriefing(page,{estimate:null,completed:2,interval:[0,65.8]});
  await page.goto('/');
  const briefing=page.getByRole('region',{name:'Next action briefing'});
  await expect(briefing.getByRole('heading',{name:'Ethereum (ETH)',exact:true})).toBeVisible();
  await expect(briefing.getByText('Public wallet holds a position for a price rise (long).',{exact:true})).toBeVisible();
  await expect(briefing.getByText('Observed position size: 1 ETH. This snapshot does not establish the size of an individual execution.',{exact:true})).toBeVisible();
  await expect(briefing.getByText('Perpetual contract · USDC · not a Kraken spot order.',{exact:true})).toBeVisible();
  await expect(briefing.getByText('Not validated',{exact:true})).toHaveCount(1);
  await expect(briefing.getByText('2 of 100 minimum completed',{exact:true})).toBeVisible();
  await expect(briefing.getByText(/65\.8\s*%/)).toHaveCount(0);
  await expect(briefing.getByText('95% outcome interval',{exact:true})).toHaveCount(0);
  await expect(briefing.getByText('0.25%',{exact:true})).toBeVisible();
  await expect(briefing.getByText('Favorable versus the observed average entry',{exact:true})).toBeVisible();
  await expect(briefing.getByText('Adverse versus the observed average entry',{exact:true})).toHaveCount(0);
  await expect(briefing.getByText(/a cheaper entry does not remove this risk/)).toBeVisible();
  await expect(briefing.getByText('2,500 USDC',{exact:true})).toBeVisible();
  await expect(briefing.getByText('2,493.75 USDC',{exact:true})).toBeVisible();
  await expect(briefing.getByText(ADDRESS,{exact:true})).not.toBeVisible();
  await page.screenshot({path:testInfo.outputPath('synthetic-unvalidated-ethereum-mobile.png'),fullPage:true});
  await briefing.getByText(/^Source and wallet details/).click();
  await expect(briefing.getByText(ADDRESS,{exact:true})).toBeVisible();
  const copyButton=briefing.getByRole('button',{name:'Copy public wallet address',exact:true});
  await expect(copyButton).toBeVisible();
  expect((await copyButton.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await expect(briefing.getByText('Source: SYNTHETIC PUBLIC DATA FIXTURE',{exact:true})).toBeVisible();
  await briefing.getByText('How the success estimate is validated',{exact:true}).click();
  await expect(briefing.getByText(/65\.8\s*%/)).toHaveCount(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await briefing.getByRole('button',{name:/View this wallet[’']s actions/}).click();
  await expect(page.getByRole('heading',{name:/^Big Traders/})).toBeVisible();
  await expect(page.getByRole('heading',{name:'SYNTHETIC TEST WALLET',exact:true})).toBeVisible();
  const wallet=page.locator('#wallet-'+ADDRESS);
  const otherWallet=page.locator('#wallet-'+OTHER_ADDRESS);
  await expect(wallet.getByRole('heading',{name:'ETH · increased',exact:true})).toBeVisible();
  await expect(wallet).toContainText('Observed quantity: 0.5 → 1');
  await expect(wallet).toContainText('exact execution time is unknown');
  await expect(wallet.getByRole('heading',{name:'BTC · reduced',exact:true})).toHaveCount(0);
  await expect(otherWallet.getByRole('heading',{name:'BTC · reduced',exact:true})).toBeVisible();
  await expect(otherWallet.getByRole('heading',{name:'ETH · increased',exact:true})).toHaveCount(0);
  await expect(otherWallet).toContainText('WAIT · HISTORICAL');
  expect(writes).toEqual([]);
});

test('a backend-validated synthetic estimate disappears once its observation becomes stale',async({page},testInfo)=>{
  await page.clock.install({time:new Date(NOW*1000)});
  const {writes,clock}=await mockBriefing(page,{estimate:61.4,completed:140,interval:[52,69]});
  await page.goto('/');
  const briefing=page.getByRole('region',{name:'Next action briefing'});
  await expect(briefing.getByText('61.4%',{exact:true})).toBeVisible();
  await expect(briefing.getByText('52% – 69%',{exact:true})).toBeVisible();
  await expect(briefing.getByRole('heading',{name:'Skip this observed entry',exact:true})).toBeVisible();
  await expect(briefing.locator('.badge')).toHaveText('NO-GO');
  // API remains online, with fresh market quotes but the same old position.
  // HTTP success must not refresh the position's original observation time.
  clock.marketAt=NOW+95;
  await page.clock.fastForward(95_000);
  await expect(briefing.getByRole('heading',{name:'Wait for fresh market observations',exact:true})).toBeVisible();
  await expect(briefing.locator('.evidence-metrics').getByText('61.4%',{exact:true})).toHaveCount(0);
  await expect(briefing.getByText('52% – 69%',{exact:true})).toHaveCount(0);
  const estimateMetric=briefing.locator('.evidence-metrics > div').filter({has:page.getByText('Success odds · next hour',{exact:true})});
  await expect(estimateMetric.locator('strong')).toHaveText('Unavailable');
  await expect(briefing.getByText('95% outcome interval',{exact:true})).toHaveCount(0);
  await page.screenshot({path:testInfo.outputPath('synthetic-stale-estimate-hidden.png'),fullPage:true});
  expect(writes).toEqual([]);
});

test('a fresh wallet snapshot cannot validate stale executable market evidence',async({page})=>{
  await page.clock.install({time:new Date(NOW*1000)});
  const {writes,clock}=await mockBriefing(page,{estimate:61.4,completed:140,interval:[52,69]});
  clock.marketAt=NOW-6;
  await page.goto('/');
  const briefing=page.getByRole('region',{name:'Next action briefing'});
  await expect(briefing.getByRole('heading',{name:'Wait for fresh market observations',exact:true})).toBeVisible();
  await expect(briefing.getByText('A current matching market quote is unavailable or older than five seconds. Refresh the evidence before assessing an entry.',{exact:true})).toBeVisible();
  await expect(briefing.locator('.evidence-metrics').getByText('61.4%',{exact:true})).toHaveCount(0);
  await expect(briefing.getByText('95% outcome interval',{exact:true})).toHaveCount(0);
  await expect(briefing.getByText('2,493.75 USDC',{exact:true})).toHaveCount(0);
  await expect(briefing.getByText('Favorable versus the observed average entry',{exact:true})).toHaveCount(0);
  expect(writes).toEqual([]);
});


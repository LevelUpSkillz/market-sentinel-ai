import { expect, test, type Page } from '@playwright/test';

// Entirely SYNTHETIC browser fixtures. No credentials, balances, provider
// validations or orders in this file belong to a real account or exchange.
const NOW=1_800_000_000;
const KEY='SYNTHETIC_TEST_KEY_NOT_A_CREDENTIAL';
const SECRET='SYNTHETIC_TEST_SECRET_NOT_A_CREDENTIAL';
const APP_ORDER_ID='SYNTHETIC-IMMUTABLE-ORDER';
const CONFIRMATION='PLACE THIS REAL ORDER';

type Fixture={
  credentialEntry:boolean;connected:boolean;canTrade:boolean;liveEnabled:boolean;orderEnabled:boolean;
  linkFails:boolean;approvalNetworkFailure:boolean;reconciled:boolean;restoreActive:boolean;
  requests:{path:string;method:string;body:Record<string,unknown>|null}[];
};
function fixture(overrides:Partial<Fixture>={}):Fixture {
  return {credentialEntry:true,connected:true,canTrade:true,liveEnabled:true,orderEnabled:true,
    linkFails:false,approvalNetworkFailure:false,reconciled:false,restoreActive:false,requests:[],...overrides};
}
function dashboard(){return {as_of:NOW,environment:'SYNTHETIC_BROWSER_TEST',auth_method:'cloudflare_access',live_trading:false,
  markets:[],providers:{},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},
  opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:NOW,journal_error:null,
  alerts_configured:false,changenow:{configured:false,approved:false,kind:'indicative_swap_estimates'}}}
function preview(){return {id:APP_ORDER_ID,status:'validated',expires_at:NOW+30,symbol:'XRP-USD',side:'buy',
  quantity:'10',limit_price:'2',estimated_notional:'20',fee_reserve:'0.16',quote_currency:'USD',provider_validation:true,
  risk_disclosure:['SYNTHETIC TEST VALIDATION ONLY. No actual exchange account, price, fee or order.']}}

async function routes(page:Page,state:Fixture){
  await page.route('**/api/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    const method=request.method();
    const body=method==='GET'?null:request.postDataJSON() as Record<string,unknown>;
    state.requests.push({path,method,body});
    let response:unknown={records:[]};
    if(path==='/api/dashboard')response=dashboard();
    else if(path==='/api/intelligence')response={as_of:NOW,actions:[]};
    else if(path==='/api/capital')response={profile:null,execution_enabled:false};
    else if(path==='/api/connections')response={provider:'kraken',status:state.connected?'connected':'secure_setup_required',
      connected:state.connected,credential_entry_enabled:state.credentialEntry,
      live_order_submission_enabled:state.liveEnabled,order_submission_enabled:state.orderEnabled,
      withdrawals_enabled:false,requirements:['SYNTHETIC TEST: restricted private-owner API connection.'],
      connection:state.connected?{id:'SYNTHETIC-CONNECTION',verified_at:NOW,permissions:['query-funds','query-open-trades','query-closed-trades'],can_trade:state.canTrade}:null,
      markets:[{symbol:'XRP-USD',ready:true},{symbol:'BTC-USD',ready:false}],
      active_order:state.restoreActive?{...preview(),status:'unknown',order_ids:[],message:'SYNTHETIC TEST: durable submission needs reconciliation.'}:null};
    else if(path==='/api/connections/kraken'&&method==='POST'){
      if(state.linkFails){await route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({detail:'SYNTHETIC reflected '+SECRET})});return}
      state.connected=true;response={status:'connected'};
    }
    else if(path==='/api/connections/kraken/account')response={verified_at:NOW,
      balances:[{asset:'USD',balance:'100',available:'100'},{asset:'XRP',balance:'10',available:'10'}],
      open_orders:[],fees_note:'SYNTHETIC account fee context; not an actual fee quote.'};
    else if(path==='/api/connections/kraken/preview')response=preview();
    else if(path==='/api/connections/kraken/approve'){
      if(state.approvalNetworkFailure){await route.abort('failed');return}
      response={id:APP_ORDER_ID,status:'submitted',order_ids:['SYNTHETIC-PROVIDER-ORDER'],message:'SYNTHETIC TEST: request accepted, no actual order.'};
    }
    else if(path==='/api/connections/kraken/reconcile')response={id:APP_ORDER_ID,status:state.reconciled?'resolved':'unknown',
      order_ids:state.reconciled?['SYNTHETIC-PROVIDER-ORDER']:[],message:state.reconciled?'SYNTHETIC TEST: provider terminal record found.':'SYNTHETIC TEST: outcome remains unknown.'};
    else if(path==='/api/connections/kraken/disconnect'){state.connected=false;response={status:'disconnected'}}
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(response)});
  });
}
async function settings(page:Page,state:Fixture){
  await page.clock.install({time:new Date(NOW*1000)});
  await page.setViewportSize({width:390,height:844});
  await routes(page,state);await page.goto('/');
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await expect(page.getByRole('region',{name:'Your Kraken account',exact:true})).toBeVisible();
}
const writes=(state:Fixture,path:string)=>state.requests.filter(row=>row.path===path&&row.method==='POST');
async function prepareReview(page:Page){
  await page.getByRole('button',{name:'Refresh balances and open orders',exact:true}).click();
  await expect(page.getByText('recent account snapshot',{exact:false})).toBeVisible();
  await page.getByLabel('Kraken real order market',{exact:true}).selectOption('XRP-USD');
  await page.getByLabel('Kraken real order quantity',{exact:true}).fill('10');
  await page.getByLabel('Kraken real order limit price',{exact:true}).fill('2');
  await page.getByRole('button',{name:'Validate and review · no order placed',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Exact order awaiting your approval',exact:true})).toBeVisible();
}

test('secure backend gate hides credential inputs and does not poll private account data',async({page})=>{
  const state=fixture({credentialEntry:false,connected:false,liveEnabled:false,orderEnabled:false});
  await settings(page,state);
  await expect(page.getByLabel('Kraken API key',{exact:true})).toHaveCount(0);
  await expect(page.getByLabel('Kraken API secret',{exact:true})).toHaveCount(0);
  await expect(page.getByText(/Credential entry is disabled until/)).toBeVisible();
  await page.clock.fastForward(20_000);
  expect(state.requests.filter(row=>row.path==='/api/connections')).toHaveLength(1);
  expect(state.requests.filter(row=>row.path==='/api/connections/kraken/account')).toHaveLength(0);
  expect(writes(state,'/api/connections/kraken')).toHaveLength(0);
  expect(writes(state,'/api/connections/kraken/approve')).toHaveLength(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('dedicated credential form sends residence confirmations, clears secrets even on failure and never stores them',async({page})=>{
  const state=fixture({connected:false,linkFails:true,liveEnabled:false,orderEnabled:false});
  await settings(page,state);
  const key=page.getByLabel('Kraken API key',{exact:true}),secret=page.getByLabel('Kraken API secret',{exact:true});
  await expect(key).toHaveAttribute('type','password');await expect(secret).toHaveAttribute('type','password');
  await key.fill(KEY);await secret.fill(SECRET);
  await page.getByLabel('Kraken residence country code',{exact:true}).fill('CA');
  await page.getByLabel('Kraken residence region',{exact:true}).fill('Quebec');
  const submit=page.getByRole('button',{name:'Verify restricted Kraken connection',exact:true});
  await expect(submit).toBeDisabled();
  await page.getByLabel(/I confirm that this Kraken account and spot product/).check();
  await expect(submit).toBeDisabled();
  await page.getByLabel(/This is a newly dedicated API key/).check();
  await submit.click();
  await expect(key).toHaveValue('');await expect(secret).toHaveValue('');
  await expect(page.getByRole('alert').filter({hasText:'The Kraken request could not be completed.'})).toBeVisible();
  await expect(page.getByText('SYNTHETIC reflected '+SECRET,{exact:true})).toHaveCount(0);
  expect(writes(state,'/api/connections/kraken').map(row=>row.body)).toEqual([{api_key:KEY,api_secret:SECRET,country_code:'CA',region:'Quebec',eligibility_confirmed:true,dedicated_key_confirmed:true}]);
  const storage=await page.evaluate(()=>JSON.stringify({local:Object.entries(localStorage),session:Object.entries(sessionStorage)}));
  expect(storage).not.toContain(KEY);expect(storage).not.toContain(SECRET);
  state.linkFails=false;await key.fill(KEY);await secret.fill(SECRET);await submit.click();
  await expect(page.getByRole('region',{name:'Your Kraken account',exact:true}).getByText('Connected',{exact:true})).toBeVisible();
  await expect(key).toHaveCount(0);await expect(secret).toHaveCount(0);
  expect(writes(state,'/api/connections/kraken/approve')).toHaveLength(0);
});

test('read-only permissions and the backend live flag prevent real approval',async({page})=>{
  const state=fixture({canTrade:false,liveEnabled:false,orderEnabled:false});
  await settings(page,state);
  await page.getByRole('button',{name:'Refresh balances and open orders',exact:true}).click();
  await page.getByLabel('Kraken real order market',{exact:true}).selectOption('XRP-USD');
  await page.getByLabel('Kraken real order quantity',{exact:true}).fill('10');
  await page.getByLabel('Kraken real order limit price',{exact:true}).fill('2');
  await expect(page.getByRole('button',{name:'Validate and review · no order placed',exact:true})).toBeDisabled();
  expect(writes(state,'/api/connections/kraken/preview')).toHaveLength(0);
  state.canTrade=true;state.orderEnabled=true;
  await page.getByRole('button',{name:'Refresh connection status',exact:true}).click();
  await prepareReview(page);
  await expect(page.getByLabel('Real Kraken order approval phrase',{exact:true})).toBeDisabled();
  await expect(page.getByRole('button',{name:'Place this real buy limit order',exact:true})).toBeDisabled();
  expect(writes(state,'/api/connections/kraken/approve')).toHaveLength(0);
});

test('review preserves exact costs and requires unchanged details, individual phrase and unexpired evidence',async({page})=>{
  const state=fixture();await settings(page,state);await prepareReview(page);
  const review=page.locator('[aria-label="Exact Kraken order review"]');
  await expect(review.getByText('20.16 USD',{exact:true})).toBeVisible();
  await expect(review.getByText('10',{exact:true})).toBeVisible();
  await page.getByLabel('Kraken real order quantity',{exact:true}).fill('11');
  await expect(review).toHaveCount(0);
  expect(writes(state,'/api/connections/kraken/approve')).toHaveLength(0);
  await page.getByLabel('Kraken real order quantity',{exact:true}).fill('10');
  await page.getByRole('button',{name:'Validate and review · no order placed',exact:true}).click();
  const phrase=page.getByLabel('Real Kraken order approval phrase',{exact:true});
  const approve=page.getByRole('button',{name:'Place this real buy limit order',exact:true});
  await phrase.fill('place this real order');await expect(approve).toBeDisabled();
  await phrase.fill(CONFIRMATION);await expect(approve).toBeEnabled();
  await page.clock.fastForward(31_000);await expect(approve).toBeDisabled();
  await expect(review).toContainText('expired; validate a new review');
  expect(writes(state,'/api/connections/kraken/approve')).toHaveLength(0);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('ambiguous submission never resends and only explicit reconciliation can unlock a new review',async({page})=>{
  const state=fixture({approvalNetworkFailure:true});await settings(page,state);await prepareReview(page);
  await page.getByLabel('Real Kraken order approval phrase',{exact:true}).fill(CONFIRMATION);
  await page.getByRole('button',{name:'Place this real buy limit order',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Order submission outcome unknown',exact:true})).toBeVisible();
  expect(writes(state,'/api/connections/kraken/approve').map(row=>row.body)).toEqual([{preview_id:APP_ORDER_ID,confirmation:CONFIRMATION}]);
  await page.clock.fastForward(10_000);
  expect(writes(state,'/api/connections/kraken/approve')).toHaveLength(1);
  expect(writes(state,'/api/connections/kraken/reconcile')).toHaveLength(0);
  await page.getByRole('button',{name:'Refresh balances and open orders',exact:true}).click();
  await expect(page.getByRole('button',{name:'Validate and review · no order placed',exact:true})).toBeDisabled();
  const reconcile=page.getByRole('button',{name:'Reconcile this order with Kraken · no resend',exact:true});
  await reconcile.click();
  expect(writes(state,'/api/connections/kraken/reconcile').map(row=>row.body)).toEqual([{order_id:APP_ORDER_ID}]);
  await expect(page.getByRole('heading',{name:'Order submission outcome unknown',exact:true})).toBeVisible();
  state.reconciled=true;await reconcile.click();
  await expect(page.getByRole('heading',{name:'Kraken order reconciled to a terminal status',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Refresh balances and open orders',exact:true}).click();
  await expect(page.getByRole('button',{name:'Validate and review · no order placed',exact:true})).toBeEnabled();
  expect(writes(state,'/api/connections/kraken/approve')).toHaveLength(1);
});

test('durable active intent restores manual reconciliation after a page reload',async({page})=>{
  const state=fixture({restoreActive:true});await settings(page,state);
  await expect(page.getByRole('heading',{name:'Order submission outcome unknown',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Refresh balances and open orders',exact:true}).click();
  await expect(page.getByRole('button',{name:'Validate and review · no order placed',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Reconcile this order with Kraken · no resend',exact:true}).click();
  expect(writes(state,'/api/connections/kraken/reconcile').map(row=>row.body)).toEqual([{order_id:APP_ORDER_ID}]);
  expect(writes(state,'/api/connections/kraken/approve')).toHaveLength(0);
});

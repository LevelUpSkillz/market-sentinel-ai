import { expect, test, type Page } from '@playwright/test';

// Explicitly SYNTHETIC browser fixtures. No trader identity, return or action is real.
const TIME = new Date('2026-10-23T12:00:00Z');
const NOW = TIME.getTime()/1000;
const ADDRESS = '0x'+'a'.repeat(40);
const OTHER_ADDRESS = '0x'+'b'.repeat(40);
const LABEL = 'SYNTHETIC CANDIDATE ALPHA';

type FixtureState = {
  tracked:boolean;
  directoryFailure:boolean;
  searches:string[];
  posts:{address:string;label:string}[];
};

function dashboard(){
  return {as_of:NOW,environment:'test',auth_method:'cloudflare_access',live_trading:false,
    markets:[],providers:{},signals:[],control:{stopped:false},
    account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],
    strategy_version:'SYNTHETIC_DISCOVERY_FIXTURE',last_persist:NOW,journal_error:null,alerts_configured:false,
    changenow:{configured:false,approved:false,kind:'indicative_swap_estimates'}};
}

function directory(query:string){
  const rows=[
    {address:ADDRESS,label:LABEL,account_value:'1000',windows:{month:{pnl:'12',roi_pct:null,roi_raw:'0.125',volume:'100'},allTime:{pnl:'30',roi_pct:null,roi_raw:'0.3',volume:'300'}},independent_rank:null,data_completeness:'SYNTHETIC FIXTURE: provider-reported windows only; ROI units unverified.'},
    {address:OTHER_ADDRESS,label:'SYNTHETIC CANDIDATE BETA',account_value:null,windows:{month:{pnl:null,roi_pct:null,volume:null},allTime:{pnl:null,roi_pct:null,volume:null}},independent_rank:null,data_completeness:'SYNTHETIC FIXTURE: historical fields unavailable.'},
  ].filter(row=>!query||(row.label+' '+row.address).toLowerCase().includes(query.toLowerCase()));
  return {traders:rows,total:rows.length,page:1,limit:12,source:'SYNTHETIC PUBLIC PROVIDER DIRECTORY',
    received_at:NOW-300,source_at:null,status:'cached',
    selection_basis:'SYNTHETIC FIXTURE: transparent provider sample; not a worldwide skill ranking.',
    limitations:['SYNTHETIC FIXTURE: reported ROI is not an independently validated return or probability.']};
}

function traderEvidence(){
  return {traders:[{id:ADDRESS,address:ADDRESS,label:LABEL,freshness:'live',snapshot:{received_at:NOW,source_at:null,
    source:'SYNTHETIC POSITION SNAPSHOT',account_value:'1000',data_completeness:'SYNTHETIC',baseline:false,
    positions:[{coin:'XRP',szi:'1.25',entryPx:'2',unrealizedPnl:'0',liquidationPx:null}]}}],
    events:[{id:'SYNTHETIC_POSITION_EVENT',recorded_at:NOW,observed_at:NOW,address:ADDRESS,coin:'XRP',
      action:'increased',side:'long',before_size:'1',after_size:'1.25',source:'SYNTHETIC POSITION POLL',
      timing:'SYNTHETIC FIXTURE: exact execution time is unknown.',
      analysis:{decision:'NO-GO',reasons:['SYNTHETIC FIXTURE: an observed size change does not establish an executable copy trade.']}}],
    intelligence:{as_of:NOW,actions:[]}};
}

async function routes(page:Page,state:FixtureState){
  await page.route('**/api/**',async route=>{
    const url=new URL(route.request().url()),path=url.pathname;
    let body:unknown={records:[]};
    if(path==='/api/dashboard')body=dashboard();
    if(path==='/api/intelligence')body={as_of:NOW,actions:[]};
    if(path==='/api/radar')body={as_of:NOW,strategy_version:'SYNTHETIC',mode:'paper_only',status:'warming_up',coverage:{universe:0,observed:0,warming_up:0,ready:0,candidates:0},setups:[],limitations:['SYNTHETIC FIXTURE']};
    if(path==='/api/trader-directory'){
      const query=url.searchParams.get('q')||'';
      state.searches.push(query);
      if(state.directoryFailure){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'SYNTHETIC provider outage'})});return}
      body=directory(query);
    }
    if(path==='/api/traders'){
      if(route.request().method()==='POST'){
        const submitted=route.request().postDataJSON() as {address:string;label:string};
        state.posts.push(submitted);state.tracked=true;
        body={id:submitted.address,...submitted,recorded_at:NOW};
      }else body=state.tracked?traderEvidence():{traders:[],events:[],intelligence:{as_of:NOW,actions:[]}};
    }
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
}

async function smartMoney(page:Page){
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Big Traders',exact:true}).click();
}

test('synthetic public candidates can be searched and tracked without turning reported ROI into copy approval',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.clock.install({time:TIME});
  const state:FixtureState={tracked:false,directoryFailure:false,searches:[],posts:[]};
  await routes(page,state);
  await page.goto('/');
  await smartMoney(page);
  const panel=page.getByRole('region',{name:'Trader Actions'});
  await expect(panel.getByRole('heading',{name:LABEL,exact:true})).toBeVisible();
  const missing=panel.locator('.signal-card').filter({hasText:'SYNTHETIC CANDIDATE BETA'});
  await expect(missing.getByText('Unavailable',{exact:true})).toHaveCount(2);
  await expect(missing.getByText('0%',{exact:true})).toHaveCount(0);
  await panel.getByLabel('Search public trader candidates').fill('ALPHA');
  await page.clock.runFor(350);
  await expect(panel.locator('.signal-card')).toHaveCount(1);
  expect(state.searches).toContain('ALPHA');
  const candidate=panel.locator('.signal-card');
  await expect(candidate.getByText('0.125',{exact:true})).toBeVisible();
  await expect(candidate.getByText('Provider value · unit unverified',{exact:true})).toHaveCount(2);
  await expect(candidate.getByText('12.5%',{exact:true})).toHaveCount(0);
  await expect(candidate.getByText('Skill ranking: not independently validated.',{exact:true})).toBeVisible();
  await expect(candidate.getByText('Reported ROI is historical provider data, not a forecast or a probability of winning.',{exact:true})).toBeVisible();
  await candidate.getByRole('button',{name:'Track actions',exact:true}).click();
  await expect(candidate.getByRole('button',{name:'Tracking actions',exact:true})).toBeDisabled();
  expect(state.posts).toEqual([{address:ADDRESS,label:LABEL}]);
  const observed=panel.getByRole('row').filter({hasText:'XRP · increased'});
  await expect(observed.getByText('recent observation',{exact:true})).toBeVisible();
  await expect(observed.getByText('NO-GO · HISTORICAL',{exact:true})).toBeVisible();
  await expect(observed).toContainText('1 → 1.25');
  await expect(observed).toContainText('SYNTHETIC POSITION POLL');
  await expect(observed).toContainText('exact execution time is unknown');
  await expect(panel.getByText('Address added for observation. Public positions and subsequent changes will appear after collector polling. No trade was placed.',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('provider directory failure retains dated metrics while old wallet actions become historical',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.clock.install({time:TIME});
  const state:FixtureState={tracked:true,directoryFailure:false,searches:[],posts:[]};
  await routes(page,state);
  await page.goto('/');
  await smartMoney(page);
  const panel=page.getByRole('region',{name:'Trader Actions'});
  const observed=panel.getByRole('row').filter({hasText:'XRP · increased'});
  await expect(observed.getByText('recent observation',{exact:true})).toBeVisible();
  await expect(panel.locator('.signal-card').filter({hasText:LABEL}).getByText('0.125',{exact:true})).toBeVisible();
  state.directoryFailure=true;
  await page.clock.fastForward(61000);
  await expect(panel.getByRole('status').filter({hasText:'The experimental provider directory is unavailable.'})).toBeVisible();
  await expect(panel).toContainText('refresh unavailable');
  await page.clock.fastForward(31000);
  await expect(observed.getByText('historical observation',{exact:true})).toBeVisible();
  await expect(observed.getByText('recent observation',{exact:true})).toHaveCount(0);
  await expect(observed.getByText('NO-GO · HISTORICAL',{exact:true})).toBeVisible();
  await expect(panel.locator('.signal-card').filter({hasText:LABEL}).getByText('0.125',{exact:true})).toBeVisible();
  await expect(panel).toContainText('SYNTHETIC PUBLIC PROVIDER DIRECTORY');
  await expect(panel).toContainText('Provider directory data is delayed/receipt-time only, not a live position feed.');
  expect(state.posts).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

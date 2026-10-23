import { expect, test, type Locator, type Page } from '@playwright/test';

// SYNTHETIC TEST FIXTURES ONLY. These observations are not real BTC prices.
const TIME = new Date('2026-10-23T12:00:00Z');
const START = TIME.getTime()/1000;
type Feed = {at:number;sourceAt:number;receivedAt:number;mid:number;outage:boolean};

async function mockFeed(page:Page,feed:Feed){
  const requests:string[]=[];
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    requests.push(path);
    if(path==='/api/dashboard'&&feed.outage){
      await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'SYNTHETIC provider outage'})});
      return;
    }
    const dashboard={as_of:feed.at,environment:'test',auth_method:'cloudflare_access',live_trading:false,
      markets:[{provider:'kraken',symbol:'BTC-USD',instrument:'spot',quote:'USD',bid:String(feed.mid-0.05),ask:String(feed.mid+0.05),mid:String(feed.mid),spread_bps:'10',imbalance:'0',visible_depth_usd:'10000',source_at:feed.sourceAt,received_at:feed.receivedAt,
        status:'live',integrity:'crc32_verified',bids:[[String(feed.mid-0.05),'100']],asks:[[String(feed.mid+0.05),'100']]}],
      providers:{kraken:{state:'connected',reason:null,reconnects:0}},signals:[],control:{stopped:false},
      account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC_LIVE_CHART_TEST',last_persist:feed.at,journal_error:null,alerts_configured:false,
      changenow:{configured:false,approved:false,kind:'indicative_swap_estimates'}};
    let body:unknown={records:[]};
    if(path==='/api/dashboard')body=dashboard;
    if(path==='/api/intelligence')body={as_of:feed.at,actions:[]};
    if(path==='/api/traders')body={traders:[],events:[],intelligence:{as_of:feed.at,actions:[]}};
    if(path==='/api/radar')body={as_of:feed.at,strategy_version:'SYNTHETIC',mode:'paper_only',status:'warming_up',coverage:{universe:0,observed:0,warming_up:0,ready:0,candidates:0},setups:[],limitations:['SYNTHETIC FIXTURE']};
    if(path==='/api/assets')body={items:[],page:1,limit:25,total:0,counts:{catalogue:0,global_prices:0,venue_markets:1,streaming_quotes:1},as_of:feed.at,watched_markets:[],extra_book_limit:6,sessions:{kraken:{state:'connected'}},errors:{},catalogue_received_at:null,global_quotes_received_at:null,coverage:'SYNTHETIC TEST FIXTURE',attribution:{label:'SYNTHETIC FIXTURE',url:'https://coinpaprika.com',license:'SYNTHETIC TEST ONLY'}};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  return requests;
}

async function expectSamples(chart:Locator,count:number){
  await expect.poll(async()=>{
    const text=await chart.getByTestId('live-chart-sample-count').textContent();
    return Number(text?.match(/\d+/)?.[0]??NaN);
  }).toBe(count);
}

function sourcePoint(feed:Feed,seconds:number,mid:number){
  feed.at=START+seconds;feed.sourceAt=START+seconds;feed.receivedAt=START+seconds;feed.mid=mid;
}

test('live chart changes only as actual timestamped synthetic market observations arrive',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.clock.install({time:TIME});
  const feed:Feed={at:START,sourceAt:START,receivedAt:START,mid:101,outage:false};
  await mockFeed(page,feed);
  await page.goto('/');
  const chart=page.getByRole('region',{name:'Live market chart'});
  await expect(chart.getByTestId('live-chart-price')).toContainText('101');
  await expectSamples(chart,1);
  await expect(chart).toContainText(/kraken/i);
  await expect(chart).toContainText('BTC-USD');
  await expect(chart).toContainText(/source/i);
  await expect(chart).toContainText(/received/i);
  sourcePoint(feed,2,103);
  await page.clock.runFor(2100);
  await expect(chart.getByTestId('live-chart-price')).toContainText('103');
  await expectSamples(chart,2);
  const line=chart.getByTestId('live-chart-line');
  await expect(line).toBeAttached();
  const firstPath=await line.getAttribute('d');
  expect(firstPath).toBeTruthy();
  sourcePoint(feed,4,102);
  await page.clock.runFor(2100);
  await expect(chart.getByTestId('live-chart-price')).toContainText('102');
  await expectSamples(chart,3);
  await expect.poll(()=>line.getAttribute('d')).not.toBe(firstPath);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('API heartbeats and outages add no chart prices, and recovery leaves an explicit gap',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.clock.install({time:TIME});
  const feed:Feed={at:START,sourceAt:START,receivedAt:START,mid:101,outage:false};
  await mockFeed(page,feed);
  await page.goto('/');
  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Live Markets',exact:true}).click();
  const chart=page.getByRole('region',{name:'Live market chart'});
  await expectSamples(chart,1);
  sourcePoint(feed,2,103);
  await page.clock.runFor(2100);
  await expectSamples(chart,2);
  const line=chart.getByTestId('live-chart-line');
  const lastVerifiedPath=await line.getAttribute('d');
  // The API responds and even advertises status=live, but the provider source
  // timestamp does not advance. Once stale, an invalid price jump must not
  // change either the verified price summary or the observed chart series.
  for(const seconds of [4,6,8]){
    feed.at=START+seconds;feed.receivedAt=START+seconds;
    if(seconds===8)feed.mid=900;
    await page.clock.runFor(2100);
    await expectSamples(chart,2);
  }
  await expect(chart).toContainText(/stale|unavailable|paused/i);
  await expect(chart.getByTestId('live-chart-price')).toContainText('103');
  await expect(chart.getByTestId('live-chart-price')).not.toContainText('900');
  expect(await line.getAttribute('d')).toBe(lastVerifiedPath);
  feed.outage=true;
  await page.clock.runFor(2100);
  await expect(page.getByRole('alert').filter({hasText:'Connection issue:'})).toContainText('SYNTHETIC provider outage');
  await expectSamples(chart,2);
  expect(await line.getAttribute('d')).toBe(lastVerifiedPath);
  feed.outage=false;sourcePoint(feed,12,104);
  await page.clock.runFor(2100);
  await expectSamples(chart,3);
  sourcePoint(feed,14,105);
  await page.clock.runFor(2100);
  await expectSamples(chart,4);
  await expect(chart.getByTestId('live-chart-price')).toContainText('105');
  const recovered=await line.getAttribute('d');
  // Independent path moves show disjoint observed segments across the outage.
  expect((recovered?.match(/M/g)||[]).length).toBeGreaterThanOrEqual(2);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test('hidden pages stop dashboard, history and wallet polling, then refresh on return',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.clock.install({time:TIME});
  const feed:Feed={at:START,sourceAt:START,receivedAt:START,mid:101,outage:false};
  const requests=await mockFeed(page,feed);
  await page.goto('/');
  await expectSamples(page.getByRole('region',{name:'Live market chart'}),1);
  await expect.poll(()=>requests.filter(path=>path==='/api/records/market_snapshot').length).toBeGreaterThan(0);
  await expect.poll(()=>requests.filter(path=>path==='/api/intelligence').length).toBeGreaterThan(0);

  const visibility=async(state:'visible'|'hidden')=>{
    await page.evaluate(value=>{
      Object.defineProperty(document,'visibilityState',{configurable:true,get:()=>value});
      document.dispatchEvent(new Event('visibilitychange'));
    },state);
  };
  await visibility('hidden');
  const beforeHidden=requests.length;
  await page.clock.runFor(31_000);
  expect(requests.length).toBe(beforeHidden);
  const savedBeforeReturn=requests.filter(path=>path==='/api/records/market_snapshot').length;
  sourcePoint(feed,31,102);
  await visibility('visible');
  await expect.poll(()=>requests.filter(path=>path==='/api/records/market_snapshot').length).toBeGreaterThan(savedBeforeReturn);

  await page.getByLabel('Open navigation').click();
  await page.getByRole('button',{name:'Smart Money',exact:true}).click();
  await expect.poll(()=>requests.filter(path=>path==='/api/traders').length).toBeGreaterThan(0);
  await visibility('hidden');
  const walletsBeforeHidden=requests.filter(path=>path==='/api/traders').length;
  await page.clock.runFor(31_000);
  expect(requests.filter(path=>path==='/api/traders').length).toBe(walletsBeforeHidden);
  await visibility('visible');
  await expect.poll(()=>requests.filter(path=>path==='/api/traders').length).toBeGreaterThan(walletsBeforeHidden);
});

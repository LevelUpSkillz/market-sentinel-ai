import {expect,test,type Page} from '@playwright/test';

// Entirely SYNTHETIC acceptance evidence. No live account or provider is used.
const NOW=1800000000;
async function fixture(page:Page) {
  const requests:{path:string;method:string}[]=[];
  await page.clock.install({time:new Date(NOW*1000)});
  await page.route('**/api/**',async route=>{
    const request=route.request(),url=new URL(request.url()),path=url.pathname;
    requests.push({path,method:request.method()});
    const market=(symbol:string,mid:number)=>({provider:'kraken',symbol,instrument:'spot',quote:'USD',bid:String(mid-1),ask:String(mid+1),mid:String(mid),spread_bps:'10',imbalance:'0',visible_depth_usd:'10000',source_at:NOW,received_at:NOW,status:'live',integrity:'crc32_verified',bids:[[String(mid-1),'2'],[String(mid-2),'1']],asks:[[String(mid+1),'1'],[String(mid+2),'2']]});
    let value:unknown={records:[]};
    if(path==='/api/dashboard')value={as_of:NOW,environment:'SYNTHETIC',auth_method:'owner_password',live_trading:true,markets:[market('BTC-USD',100),market('ETH-USD',50)],providers:{kraken:{state:'connected'},coinbase:{state:'disabled'}},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[{provider:'kraken',symbol:'BTC-USD',price:'100',quantity:'2',source_at:NOW,received_at:NOW,side:'buy'},{provider:'kraken',symbol:'ETH-USD',price:'50',quantity:'1',source_at:NOW-120,received_at:NOW-120,side:'sell'}],strategy_version:'SYNTHETIC',last_persist:NOW,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
    if(path==='/api/intelligence')value={as_of:NOW,actions:[]};
    if(path==='/api/suggestions')value={as_of:NOW,cards:[],strategy_version:'SYNTHETIC',limitations:[]};
    if(path==='/api/price-history')value={provider:'kraken',symbol:url.searchParams.get('symbol'),interval_minutes:Number(url.searchParams.get('interval')),received_at:NOW,source_at:NOW,executable:false,candles:Array.from({length:90},(_,index)=>({at:NOW-(89-index)*60,open:String(100+index),high:String(103+index),low:String(99+index),close:String(102+index),closed:index<89}))};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(value)});
  });
  return requests;
}

for(const width of [320,390,768,1440])test(`terminal is usable at ${width}px without reading an account or placing an order`,async({page})=>{
  await page.setViewportSize({width,height:950});const requests=await fixture(page);await page.goto('/');
  await expect(page.getByRole('region',{name:'Workspace overview'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Live market chart'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Recent public trades'})).toContainText('kraken');
  await expect(page.getByLabel('Exchange price history',{exact:true}).getByTestId('history-price-line')).toHaveAttribute('d',/L/);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.getByRole('button',{name:'Chart ETH-USD on kraken',exact:true}).click();
  await expect(page.getByLabel('Live chart market',{exact:true})).toHaveValue('kraken|ETH-USD');
  await page.getByText('Explore the order book',{exact:false}).click();
  const depth=page.getByLabel('Visible order book depth');await expect(depth).toBeVisible();await expect(depth).toContainText('Buy orders');await expect(depth).toContainText('Sell orders');await expect(depth).toContainText('USD');
  expect(requests.some(request=>request.method!=='GET'||request.path.startsWith('/api/connections'))).toBeFalsy();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('chart zoom and panning use only the existing candle history and reset to the full series',async({page})=>{
  const requests=await fixture(page);await page.goto('/');const history=page.getByLabel('Exchange price history',{exact:true});
  await expect(history.getByTestId('history-window-count')).toHaveText('90 / 90 candles');
  const original=await history.getByTestId('history-price-line').getAttribute('d');
  await history.getByRole('button',{name:'Zoom in',exact:true}).click();await expect(history.getByTestId('history-window-count')).toHaveText('45 / 90 candles');
  const zoomed=await history.getByTestId('history-price-line').getAttribute('d');expect(zoomed).not.toBe(original);
  const latestClose=await history.locator('.history-point strong').textContent();
  await history.getByRole('button',{name:'Pan chart earlier',exact:true}).click();await expect(history.getByRole('button',{name:'Pan chart later',exact:true})).toBeEnabled();
  expect(await history.locator('.history-point strong').textContent()).not.toBe(latestClose);
  await history.getByRole('button',{name:'Reset',exact:true}).click();await expect(history.getByTestId('history-window-count')).toHaveText('90 / 90 candles');
  await expect(history.getByTestId('history-price-line')).toHaveAttribute('d',original!);
  expect(requests.filter(request=>request.path==='/api/price-history')).toHaveLength(1);
});

test('the activity feed and coverage ring become old when source events stop despite successful API polling',async({page})=>{
  await fixture(page);await page.goto('/');const feed=page.getByRole('region',{name:'Recent public trades'});
  await expect(feed).toContainText('units · fresh');
  await expect(page.getByRole('img',{name:'2 of 2 detailed market books are fresh'})).toBeVisible();
  await page.clock.runFor(6500);
  await expect(feed).not.toContainText('units · fresh');
  await expect(page.getByRole('img',{name:'0 of 2 detailed market books are fresh'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Data connection status'}).locator('.health-list')).not.toContainText('Fresh books');
});

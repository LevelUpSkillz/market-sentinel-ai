import {expect,test,type Page} from '@playwright/test';
// SYNTHETIC data. Motion is decorative and must never generate financial evidence.
async function setup(page:Page) {
  const writes:string[]=[],privateReads:string[]=[];
  await page.route('**/api/**',async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname,now=Date.now()/1000;
    if(req.method()!=='GET')writes.push(path);if(path.startsWith('/api/connections'))privateReads.push(path);
    let body:unknown={records:[]};
    if(path==='/api/dashboard')body={as_of:now,environment:'SYNTHETIC',auth_method:'owner_password',live_trading:true,markets:[{provider:'kraken',symbol:'BTC-USD',instrument:'spot',quote:'USD',bid:'100',ask:'102',mid:'101',spread_bps:'10',imbalance:'0',visible_depth_usd:'10000',source_at:now,received_at:now,status:'live',integrity:'crc32_verified',bids:[['100','2']],asks:[['102','2']]}],providers:{kraken:{state:'connected'},hyperliquid:{state:'disconnected'},coinbase:{state:'disabled'}},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:now,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
    if(path==='/api/intelligence')body={as_of:now,actions:[]};
    if(path==='/api/suggestions')body={as_of:now,cards:[],strategy_version:'SYNTHETIC',limitations:[]};
    if(path==='/api/price-history')body={provider:'kraken',symbol:'BTC-USD',interval_minutes:Number(url.searchParams.get('interval')),received_at:now,source_at:now,executable:false,candles:[{at:now-120,open:'99',high:'102',low:'98',close:'100',closed:true},{at:now-60,open:'100',high:'105',low:'99',close:'104',closed:true},{at:now,open:'104',high:'106',low:'102',close:'105',closed:false}]};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });return {writes,privateReads};
}
async function image(page:Page) { return page.getByTestId('orbital-visual').evaluate((node:HTMLCanvasElement)=>node.toDataURL()); }

test('orbital animation is visible, pausable and persistent without account reads or orders',async({page})=>{
  await page.setViewportSize({width:1440,height:1000});const calls=await setup(page);await page.goto('/');const canvas=page.getByTestId('orbital-visual');
  await expect(canvas).toBeVisible();await canvas.scrollIntoViewIfNeeded();await expect(canvas).toHaveAttribute('data-animating','true');
  const first=await image(page);await expect.poll(()=>image(page)).not.toBe(first);
  await page.getByRole('button',{name:'Pause visual effects',exact:true}).click();await expect(canvas).toHaveAttribute('data-animating','false');
  const paused=await image(page);await page.waitForTimeout(250);expect(await image(page)).toBe(paused);
  await expect(page.getByTestId('live-chart-price')).toContainText('101');
  await page.reload();await expect(page.getByRole('button',{name:'Enable visual effects',exact:true})).toBeVisible();await expect(page.getByTestId('orbital-visual')).toHaveAttribute('data-animating','false');
  await page.getByRole('button',{name:'Enable visual effects',exact:true}).click();await expect(page.getByTestId('orbital-visual')).toHaveAttribute('data-animating','true');
  await expect(page.getByLabel('Market source map')).toContainText('kraken');
  await expect(page.getByLabel('Market source map')).toContainText('Perpetual market data');
  expect(calls.writes).toEqual([]);expect(calls.privateReads).toEqual([]);
});

test('reduced-motion preference keeps the futuristic design static and all market controls usable',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});await page.setViewportSize({width:390,height:844});const calls=await setup(page);await page.goto('/');
  await expect(page.getByRole('button',{name:'Visual effects disabled by reduced-motion preference'})).toBeDisabled();const canvas=page.getByTestId('orbital-visual');await expect(canvas).toBeVisible();await expect(canvas).toHaveAttribute('data-animating','false');
  const first=await image(page);await page.waitForTimeout(200);expect(await image(page)).toBe(first);
  await expect(page.getByRole('button',{name:'Explore trade ideas',exact:false})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect(calls.writes).toEqual([]);expect(calls.privateReads).toEqual([]);
});

test('hidden pages stop ornamental frame generation and resume only when visible',async({page})=>{
  await setup(page);await page.goto('/');const canvas=page.getByTestId('orbital-visual');await canvas.scrollIntoViewIfNeeded();await expect(canvas).toHaveAttribute('data-animating','true');
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,get:()=> 'hidden'});document.dispatchEvent(new Event('visibilitychange'))});
  await expect(canvas).toHaveAttribute('data-animating','false');const still=await image(page);await page.waitForTimeout(200);expect(await image(page)).toBe(still);
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,get:()=> 'visible'});document.dispatchEvent(new Event('visibilitychange'))});
  await expect(canvas).toHaveAttribute('data-animating','true');
});

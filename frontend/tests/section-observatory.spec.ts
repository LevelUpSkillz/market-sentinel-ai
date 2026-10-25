import {expect,test,type Page} from '@playwright/test';
// SYNTHETIC fixtures only. No real balance, public identity or exchange request.
const NOW=1800000000,ADDRESS='0x'+'d'.repeat(40);
async function setup(page:Page) {
 const writes:string[]=[],accountReads:string[]=[];await page.clock.install({time:new Date(NOW*1000)});
 await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname;if(req.method()!=='GET')writes.push(path);if(path==='/api/connections/kraken/account')accountReads.push(path);
  const book={provider:'kraken',symbol:'BTC-USD',instrument:'spot',quote:'USD',status:'live',integrity:'crc32_verified',source_at:NOW,received_at:NOW,bid:'100',ask:'101',mid:'100.5',spread_bps:'10',imbalance:'0',visible_depth_usd:'10000',bids:[['100','2']],asks:[['101','3']]};
  let value:unknown={records:[]};
  if(path==='/api/dashboard')value={as_of:NOW,environment:'SYNTHETIC',auth_method:'owner_password',live_trading:false,markets:[book,{...book,provider:'hyperliquid',symbol:'ETH-USDC-PERP',instrument:'perpetual',quote:'USDC',integrity:'ordered_stream'}],providers:{kraken:{state:'connected'},hyperliquid:{state:'connected'}},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:NOW,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
  if(path==='/api/intelligence')value={as_of:NOW,actions:[]};
  if(path==='/api/suggestions')value={as_of:NOW,cards:[],strategy_version:'SYNTHETIC',limitations:[]};
  if(path==='/api/radar')value={as_of:NOW,strategy_version:'SYNTHETIC',mode:'paper_only',status:'warming_up',coverage:{universe:0,observed:0,warming_up:0,ready:0,candidates:0},setups:[],limitations:[]};
  if(path==='/api/traders')value={traders:[{id:ADDRESS,address:ADDRESS,label:'SYNTHETIC WALLET',freshness:'live',snapshot:{received_at:NOW,source_at:NOW,source:'SYNTHETIC public position snapshot',account_value:'100',data_completeness:'SYNTHETIC',baseline:true,positions:[{coin:'ETH',szi:'1',entryPx:'100',unrealizedPnl:'0'}]}}],events:[],intelligence:{as_of:NOW,actions:[]}};
  if(path==='/api/trader-directory')value={traders:[],total:0,page:1,limit:12,source:'SYNTHETIC',received_at:NOW,status:'cached',limitations:[],selection_basis:'SYNTHETIC'};
  if(path==='/api/assets')value={items:[],page:1,limit:25,total:0,counts:{catalogue:0,global_prices:0,venue_markets:2,streaming_quotes:2},as_of:NOW,watched_markets:[],extra_book_limit:6,sessions:{},errors:{},attribution:{label:'SYNTHETIC',url:'https://coinpaprika.com',license:'SYNTHETIC'}};
  if(path==='/api/connections')value={provider:'kraken',connected:false,credential_entry_enabled:false,order_submission_enabled:false,live_order_submission_enabled:false,connection:null,markets:[],active_order:null};
  if(path==='/api/connections/kraken/orders')value={as_of:NOW,orders:[]};
  if(path==='/api/capital')value={profile:null,execution_enabled:false};
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(value)});
 });return {writes,accountReads};
}
async function capture(page:Page,name:string) {
 await page.evaluate(()=>{const label=document.createElement('div');label.id='instrument-design-label';label.textContent='SYNTHETIC DESIGN REVIEW — NO REAL TRADES';label.style.cssText='position:fixed;top:0;left:0;right:0;padding:5px;background:#4a2756;color:white;text-align:center;font:9px sans-serif;z-index:9999';document.body.append(label)});
 const image=(await page.screenshot({type:'jpeg',quality:45,fullPage:false})).toString('base64');for(let i=0;i<Math.ceil(image.length/6000);i++)console.log('DESIGN_REVIEW '+name+' '+i+' '+Math.ceil(image.length/6000)+' '+image.slice(i*6000,(i+1)*6000));
 await page.evaluate(()=>document.getElementById('instrument-design-label')?.remove());
}

test('every research and settings page has a distinct visual instrument without mutations or private account reads',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});await page.setViewportSize({width:390,height:844});const calls=await setup(page);
 for(const [id,title] of [['live-markets','Order book landscape'],['smart-money','Public wallet constellation'],['opportunities','Opportunity flight recorder'],['radar','Signal investigation engine'],['forensics','Market investigation spectrum'],['strategy-lab','Walk-forward validation map'],['paper-risk','Practice capital orbit'],['alerts','Alert transmission console'],['settings','Workspace systems core']]){
  await page.goto('/#'+id);const panel=page.getByRole('region',{name:title,exact:true});await expect(panel).toBeVisible();await expect(panel.getByTestId('section-instrument')).toHaveAttribute('data-animating','false');
  await panel.getByRole('button',{name:'Flat',exact:true}).click();await expect(panel.getByRole('button',{name:'Flat',exact:true})).toHaveAttribute('aria-pressed','true');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 }
 expect(calls.writes).toEqual([]);expect(calls.accountReads).toEqual([]);
});

test('order-book instrument preserves quote currency and marks a retained snapshot old after source events stop',async({page})=>{
 await page.setViewportSize({width:1440,height:1000});const calls=await setup(page);await page.goto('/#live-markets');const panel=page.getByRole('region',{name:'Order book landscape'});
 await expect(panel).toContainText('Displayed buy orders200 USD');await expect(panel).toContainText('Fresh · under 5s');await panel.getByLabel('Depth visualization market').selectOption('hyperliquid|ETH-USDC-PERP');await expect(panel).toContainText('Displayed buy orders200 USDC');
 await panel.getByLabel('Inspect Order book landscape').selectOption('ask0');await expect(panel).toContainText('303 USDC');
 await page.clock.runFor(6500);await expect(panel).toContainText('Old or unavailable');await expect(panel).toContainText('RETAINED SNAPSHOT');expect(calls.writes).toEqual([]);expect(calls.accountReads).toEqual([]);
 await panel.scrollIntoViewIfNeeded();await capture(page,'depth-instrument-desktop');
});

test('wallet constellation opens the exact observed wallet and live-money instruments never load balances automatically',async({page})=>{
 await page.setViewportSize({width:390,height:844});const calls=await setup(page);await page.goto('/#smart-money');const panel=page.getByRole('region',{name:'Public wallet constellation'});
 await expect(panel.getByLabel('Inspect Public wallet constellation')).toBeVisible();await expect(panel).toContainText(ADDRESS);await panel.getByRole('button',{name:'Open wallet details',exact:false}).click();await expect(page.locator('#wallet-'+ADDRESS)).toBeFocused();
 await panel.scrollIntoViewIfNeeded();await capture(page,'wallet-instrument-mobile');
 await page.goto('/#live-money');const capital=page.getByRole('region',{name:'Capital protection array'});await expect(capital).toBeVisible();await expect(capital).toContainText('Last available USD—');await expect(capital).not.toContainText('$10,000');await capital.getByRole('button',{name:'Flat',exact:true}).click();expect(calls.accountReads).toEqual([]);expect(calls.writes).toEqual([]);
});

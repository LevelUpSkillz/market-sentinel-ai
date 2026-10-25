import {expect,test,type Page} from '@playwright/test';
// SYNTHETIC provider evidence only. The examples never access an exchange account.
const NOW=1800000000,ADDRESS='0x'+'c'.repeat(40);
async function fixture(page:Page) {
  const writes:string[]=[];await page.clock.install({time:new Date(NOW*1000)});
  await page.route('**/api/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;if(req.method()!=='GET')writes.push(path);
    let body:unknown={records:[]};
    if(path==='/api/dashboard')body={as_of:NOW,environment:'SYNTHETIC',auth_method:'owner_password',live_trading:false,markets:[],providers:{},signals:[],control:{stopped:false},account:{cash:'10000',initial_cash:'10000',realized_pnl:'0'},opportunities:[],paper:[],funding:[],trades:[],strategy_version:'SYNTHETIC',last_persist:NOW,journal_error:null,alerts_configured:false,changenow:{configured:false,approved:false}};
    if(path==='/api/intelligence')body={as_of:NOW,actions:[]};
    if(path==='/api/traders')body={traders:[{id:ADDRESS,address:ADDRESS,label:'SYNTHETIC PUBLIC WALLET',freshness:'live',snapshot:{received_at:NOW,source_at:NOW,source:'SYNTHETIC public position snapshot',account_value:'1000',positions:[{coin:'ETH',szi:'-2',entryPx:'100',positionValue:'180',marginUsed:'30',unrealizedPnl:'20',liquidationPx:'120'},{coin:'BTC',szi:'1',entryPx:'100',unrealizedPnl:'-5',liquidationPx:null}]},history:{version:'SYNTHETIC',fills_analyzed:3,complete_cycles:1,historical_win_rate_pct:0,net_before_funding_usdc:'-12',profit_factor:'0',realized_pnl_drawdown_usdc:'12',median_holding_seconds:600,unclosed_cycles:1,position_gaps:0,provider_limit_reached:false,source:'SYNTHETIC public fills',received_at:NOW,first_fill_at:NOW-1200,last_fill_at:NOW-600,limitations:['SYNTHETIC'],recent_fills:[{coin:'ETH',side:'A',action:'Open Short',price:'100',quantity:'2',source_at:NOW-600,closed_pnl_before_fees_usdc:'0',trading_fee_usdc:'0.1'}],cycles:[{coin:'BTC',side:'long',opened_at:NOW-1200,closed_at:NOW-600,trading_fees_usdc:'2',net_before_funding_usdc:'-12',entry_notional_usdc:'100',fills:2}]}}],events:[{id:'SYNTHETIC-CHANGE',coin:'ETH',address:ADDRESS,action:'increased',before_size:'-1',after_size:'-2',entry_price:'100',side:'short',recorded_at:NOW,observed_at:NOW,source:'SYNTHETIC observed position change',analysis:{decision:'WAIT',reasons:[]}}],intelligence:{as_of:NOW,actions:[]}};
    if(path==='/api/trader-directory')body={traders:[],total:0,page:1,limit:12,source:'SYNTHETIC',received_at:NOW,status:'cached',limitations:[],selection_basis:'SYNTHETIC'};
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });return writes;
}

test('public trader cards separate open gains, closed losses, entry prices and derivative collateral',async({page})=>{
  await page.setViewportSize({width:390,height:844});const writes=await fixture(page);await page.goto('/#smart-money');
  const view=page.getByRole('region',{name:'Clear trader trade details'});
  const eth=view.getByRole('article',{name:/ETH open position/});await expect(eth).toContainText('Short · for a price fall');await expect(eth).toContainText('Open gain');await expect(eth).toContainText('+20 USDC');await expect(eth).toContainText('Not locked in');await expect(eth).toContainText('Average entry price100 USDC');await expect(eth).toContainText('Token amount2 ETH');await expect(eth).toContainText('Margin in use30 USDC');
  await view.scrollIntoViewIfNeeded();
  await page.evaluate(()=>{const label=document.createElement('div');label.id='synthetic-review-label';label.textContent='SYNTHETIC DESIGN REVIEW — NO REAL TRADES';label.style.cssText='position:fixed;top:0;left:0;right:0;padding:5px;background:#4a2756;color:white;text-align:center;font:9px sans-serif;z-index:9999';document.body.append(label)});
  const encoded=(await page.screenshot({type:'jpeg',quality:45,fullPage:false})).toString('base64');
  for(let i=0;i<Math.ceil(encoded.length/6000);i++)console.log('DESIGN_REVIEW trader-details-mobile '+i+' '+Math.ceil(encoded.length/6000)+' '+encoded.slice(i*6000,(i+1)*6000));
  await page.evaluate(()=>document.getElementById('synthetic-review-label')?.remove());
  const btc=view.getByRole('article',{name:/BTC open position/});await expect(btc).toContainText('Open loss');await expect(btc).toContainText('-5 USDC');await expect(btc).toContainText('Margin in useNot available');
  await view.getByRole('button',{name:'Closed trades',exact:false}).click();const closed=view.getByRole('article',{name:'BTC closed position'});await expect(closed).toContainText('Closed loss');await expect(closed).toContainText('-12 USDC');await expect(closed).toContainText('funding not included');await expect(closed).toContainText('Average entry / exit priceNot stored in this summary');
  await view.getByRole('button',{name:'Actual executions',exact:false}).click();const fill=view.getByRole('article',{name:'ETH actual execution'});await expect(fill).toContainText('Execution price100 USDC');await expect(fill).toContainText('Token amount2 ETH');await expect(fill).toContainText('Execution value200 USDC');await expect(fill).toContainText('Trading fee0.1 USDC');await expect(fill).toContainText('Sell execution');
  await view.getByRole('button',{name:'Observed changes',exact:false}).click();const change=view.getByRole('article',{name:'ETH observed increased'});await expect(change).toContainText('1 → 2 ETH');await expect(change).toContainText('Average entry at observation100 USDC');await expect(change).toContainText('Realized profit / lossNot recorded by this snapshot');await expect(change).not.toContainText('+20 USDC');
  await view.getByLabel('Filter trader trades by token or wallet').fill('BTC');await expect(change).toHaveCount(0);await expect(view).toContainText('No matching token or wallet');expect(writes).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('old public positions remain explicitly old and do not become current from refreshed API responses',async({page})=>{
  await fixture(page);await page.goto('/#smart-money');const view=page.getByRole('region',{name:'Clear trader trade details'});
  await expect(view.getByText('Recent snapshot',{exact:true})).toHaveCount(2);await page.clock.fastForward(92000);await expect(view.getByText('Old snapshot',{exact:true})).toHaveCount(2);await expect(view.getByText('Recent snapshot',{exact:true})).toHaveCount(0);
});

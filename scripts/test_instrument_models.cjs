/* SYNTHETIC contracts for read-only financial visualization boundaries. */
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
(async()=>{
 const imported=await import(pathToFileURL(process.env.SENTINEL_INSTRUMENT_MODULE||'/tmp/sentinel-instrument-check/instrument-model.js').href);
 const api=imported.default||imported,NOW=1800000000;
 const book={provider:'kraken',symbol:'BTC-USD',instrument:'spot',quote:'USD',status:'live',integrity:'crc32_verified',source_at:NOW,received_at:NOW,bids:[['100','2'],['NaN','3'],['99','-1']],asks:[['101','3']]};
 const depth=api.depthModel(book,true,NOW);assert.equal(depth.old,false);assert.equal(depth.points.length,2);assert.equal(depth.points[0].value,200);assert.match(depth.points[0].hint,/200 USD/);
 const native=api.depthModel({...book,provider:'hyperliquid',symbol:'BTC-USDC-PERP',quote:'USDC'},true,NOW);assert.match(native.points[0].hint,/200 USDC/);assert.doesNotMatch(native.points[0].hint,/200 USD(?:\s|$)/);
 assert.equal(api.depthModel(book,true,NOW+6).old,true);assert.equal(api.depthModel({...book,integrity:'checksum_failed'},true,NOW).points.length,0);
 const wallets=api.walletModel([{address:'0x'+'a'.repeat(40),snapshot:{received_at:NOW,positions:[{coin:'ETH',szi:'-2'},{coin:'BTC',szi:'0'}]}}],true,NOW);
 assert.equal(wallets.links.length,1);assert.equal(wallets.points.filter(p=>p.group==='token').length,1);assert.equal(wallets.points.find(p=>p.group==='wallet').state,'ready');
 assert.equal(api.walletModel([{address:'0x'+'b'.repeat(40),snapshot:{received_at:NOW-91,positions:[]}}],true,NOW).points[0].state,'unknown');
 const events=api.journalModel([{id:'saved',recorded_at:NOW-60,snapshot:{symbol:'ETH-USD',spread_bps:'4.5'}},{id:'unknown',recorded_at:NOW,snapshot:{symbol:'BTC-USD',spread_bps:null}}],'forensic');assert.equal(events.points.length,1);assert.equal(events.points[0].value,4.5);assert.equal(events.points[0].at,NOW-60);
 const virtual=api.practiceModel({account:{cash:'800'},paper:[{status:'open',entry_notional:'200'},{status:'closed',entry_notional:'99999'}]});assert.equal(virtual.points[0].value,800);assert.equal(virtual.points[1].value,200);assert.equal(api.practiceModel(null).points.length,0);
 console.log('INSTRUMENT_MODEL_CONTRACT_PASS actual-depth/currency-separation/stale-rejection/wallet-links/recorded-only-forensics/virtual-capital-basis');
})().catch(error=>{console.error(error);process.exit(1)});

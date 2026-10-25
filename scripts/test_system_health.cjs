/* SYNTHETIC contracts: actual failures versus quiet-but-connected price books. */
const assert=require('node:assert/strict');const {pathToFileURL}=require('node:url');
(async()=>{const imported=await import(pathToFileURL(process.env.SENTINEL_HEALTH_MODULE||'/tmp/sentinel-instrument-check/system-health-model.js').href);const {systemHealth}=imported.default||imported,NOW=1800000000;
 const data={as_of:NOW+7,providers:{kraken:{state:'connected',last_message_at:NOW+7},coinbase:{state:'disabled'}},markets:[{provider:'kraken',received_at:NOW,source_at:NOW},{provider:'coinbase',received_at:0}],control:{stopped:false},journal_error:null};
 assert.equal(systemHealth(data,true,true,false).label,'Data connected');
 assert.equal(systemHealth({...data,as_of:NOW+31},true,true,false).tone,'warning');
 assert.equal(systemHealth({...data,providers:{...data.providers,kraken:{state:'reconnecting'}}},true,true,false).label,'Feed needs attention');
 assert.equal(systemHealth({...data,journal_error:'SYNTHETIC save failure'},true,true,false).tone,'critical');
 assert.equal(systemHealth(data,false,true,false).label,'Connection issue');
 assert.equal(systemHealth({...data,control:{stopped:true}},true,true,false).label,'New trades paused');
 assert.equal(systemHealth(null,false,false,true).label,'Checking');assert.equal(systemHealth(null,false,false,false).label,'Sign in required');
 console.log('SYSTEM_HEALTH_CONTRACT_PASS quiet-books-do-not-flicker/disabled-sources-ignored/real-outages-visible/history-save-failure/stop-control/no-auth-leak');
})().catch(error=>{console.error(error);process.exit(1)});

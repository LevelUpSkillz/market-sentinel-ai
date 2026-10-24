// SYNTHETIC function contract tests. Mock inference only, zero paid/real requests.
const {strict:assert}=require('node:assert');
const {onRequest,safeExplanation,cosine}=require(process.env.SENTINEL_AI_FUNCTION_MODULE||'/tmp/sentinel-ai-check/ai.js');
const ORIGIN='https://market.getlevelupskillz.com';
const evidence={id:'E1',card_id:'SYNTHETIC_PUBLIC',symbol:'BTC-USD',decision:'WAIT',source:'SYNTHETIC',source_at:1800000000,received_at:1800000000,expires_at:null,text:'SYNTHETIC observed condition; no private account data.'};
let calls=0,reads=0,status=200,numeric=false;
global.fetch=async(url,options)=>{reads++;assert.equal(url.hostname,'market-sentinel-ai-api.onrender.com');assert.equal(url.pathname,'/api/ai/context');assert.equal(options.method,'POST');return Response.json({as_of:1800000000,authority:'explanation_only',evidence:[evidence]},{status})};
const env={
 API_ORIGIN:'https://market-sentinel-ai-api.onrender.com',AI_FREE_PLAN_CONFIRMED:'true',
 AI:{run:async(model,input)=>{
  calls++;assert(!JSON.stringify(input).includes('PRIVATE_TEST_SECRET'));
  if(model.includes('bge-small'))return {data:[[1,0],[1,0]]};
  return {response:JSON.stringify({summary:numeric?'Win chance is 99%':'The idea needs more evidence.',
   caution:'Fees and incomplete history can invalidate it.',evidence_ids:['E1']})};
 }}
};
const request=(body={},origin=ORIGIN)=>new Request(ORIGIN+'/api/ai',{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify(body)});
(async()=>{
 let r=await onRequest({request:request({mode:'explain'}),env:{...env,AI_FREE_PLAN_CONFIRMED:'false'}});assert.equal(r.status,503);assert.equal(calls,0);assert.equal(reads,0);
 r=await onRequest({request:request({mode:'explain'},'https://evil.example'),env});assert.equal(r.status,403);assert.equal(calls,0);
 status=401;r=await onRequest({request:request({mode:'explain'}),env});assert.equal(r.status,401);assert.equal(calls,0);
 status=429;r=await onRequest({request:request({mode:'explain'}),env});assert.equal(r.status,429);assert.equal(calls,0);
 status=200;r=await onRequest({request:request({mode:'explain',api_secret:'PRIVATE_TEST_SECRET'}),env});assert.equal(r.status,400);assert.equal(calls,0);
 r=await onRequest({request:request({mode:'explain',language:'en'}),env});assert.equal(r.status,200);const valid=await r.json();assert.equal(valid.financial_action,false);assert.equal(valid.evidence[0].decision,'WAIT');
 numeric=true;r=await onRequest({request:request({mode:'challenge'}),env});assert.equal(r.status,503);numeric=false;
 r=await onRequest({request:request({mode:'search',query:'weak liquidity'}),env});assert.equal(r.status,200);const search=await r.json();assert.equal(search.kind,'semantic_search');assert.equal(search.matches[0].relevance,1);assert.match(search.note,/not trading quality/);
 assert.throws(()=>safeExplanation({summary:'Buy now',caution:'safe',evidence_ids:['E1']},new Set(['E1'])));assert.throws(()=>safeExplanation({summary:'Wait',caution:'Check',evidence_ids:['FAKE']},new Set(['E1'])));
 assert.deepEqual(safeExplanation({summary:'Wait for evidence.',caution:'Costs still apply.',evidence_ids:['E1']},new Set(['E1'])).evidence_ids,['E1']);
 assert.throws(()=>cosine([NaN],[1]));assert.throws(()=>cosine([1],[1,2]));
 console.log('AI_FUNCTION_CONTRACT_PASS auth/origin/quota/free-plan/claim-filter/semantic-search; mock inference only');
})().catch(e=>{console.error(e);process.exitCode=1});

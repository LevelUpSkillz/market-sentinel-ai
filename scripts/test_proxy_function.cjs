const assert=require('node:assert/strict');
const {onRequest}=require('/tmp/sentinel-proxy-check/[[path]].js');
const env={API_ORIGIN:'https://market-sentinel-ai-api.onrender.com'};
const root='https://market-research.getlevelupskillz.com';
let seen;
async function redirect(path,location,cookies=[]){global.fetch=async(url,options)=>{seen={url:String(url),options};const headers=new Headers({location});for(const cookie of cookies)headers.append('Set-Cookie',cookie);return new Response(null,{status:302,headers})};return onRequest({request:new Request(root+path,{headers:{cookie:'market_google_flow=SYNTHETIC_FLOW'}}),env})}
(async()=>{
 let response=await redirect('/api/auth/google/start','https://scftnhmrdxrysvnofcyd.supabase.co/auth/v1/authorize?provider=google',['market_google_flow=SYNTHETIC; Path=/api/auth/google; Secure; HttpOnly; SameSite=Lax']);
 assert.equal(response.status,302);assert.match(response.headers.get('location'),/^https:\/\/scftnhmrdxrysvnofcyd\.supabase\.co/);assert.equal(seen.options.redirect,'manual');assert.equal(seen.options.headers.get('cookie'),'market_google_flow=SYNTHETIC_FLOW');
 response=await redirect('/api/auth/google/callback?code=SYNTHETIC_CODE',root+'/#mission-control',['market_research_session=SYNTHETIC_SIGNED; Path=/; Secure; HttpOnly; SameSite=Strict','market_google_flow=; Path=/api/auth/google; Max-Age=0; Secure; HttpOnly']);
 assert.equal(response.status,302);assert.equal(response.headers.getSetCookie().length,2);assert.equal(response.headers.get('referrer-policy'),'no-referrer');assert.equal(response.headers.get('cache-control'),'no-store');
 for(const location of ['https://attacker.example.test/','https://other.supabase.co/auth/v1/authorize','https://market-research.getlevelupskillz.com/?token=SYNTHETIC','https://market-research.getlevelupskillz.com/evil']){
  response=await redirect('/api/auth/google/callback?code=SYNTHETIC',location);assert.equal(response.status,502);assert.equal(response.headers.get('location'),null);
 }
 response=await redirect('/api/auth/google/start','https://other.supabase.co/auth/v1/authorize');assert.equal(response.status,502);
 console.log('PROXY_AUTH_CONTRACT passed: exact redirect hosts, two cookies, no credential reflection, no automatic redirect following');
})().catch(error=>{console.error(error);process.exitCode=1});

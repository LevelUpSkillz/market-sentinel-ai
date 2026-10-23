// Cloudflare Pages same-origin API gateway: HttpOnly session cookies belong
// to the Pages hostname, not to Render's separate domain.
interface Env { API_ORIGIN: string }
interface Context { request: Request; env: Env }
const APP_ORIGIN = 'https://market.getlevelupskillz.com';
const MAX_BODY = 1024 * 1024;
const METHODS = new Set(['GET','HEAD','POST']);
const failure = (status:number,detail:string) => Response.json({detail},{status,headers:{'Cache-Control':'no-store'}});

export async function onRequest({request,env}:Context):Promise<Response> {
  if (!env.API_ORIGIN) return failure(503,'Backend is not configured');
  const incoming = new URL(request.url);
  const origin = request.headers.get('origin');
  if (!METHODS.has(request.method)) return failure(405,'Method not allowed');
  // Do not allow an attacker-controlled origin to be rewritten as trusted.
  if (origin && origin !== incoming.origin) return failure(403,'Origin denied');
  if (request.method === 'POST' && origin !== incoming.origin) return failure(403,'Origin required');

  const upstream = new URL(env.API_ORIGIN);
  if (upstream.protocol !== 'https:' || upstream.username || upstream.password ||
      !upstream.hostname.endsWith('.onrender.com') || upstream.pathname !== '/') {
    return failure(503,'Invalid backend configuration');
  }
  upstream.pathname = incoming.pathname;
  upstream.search = incoming.search;
  const headers = new Headers();
  for (const key of ['content-type','cookie','cf-access-jwt-assertion']) {
    const value=request.headers.get(key); if(value) headers.set(key,value);
  }
  // Render validates APP_ORIGIN even for login. The gateway verifies the
  // browser's true origin above, then supplies the configured application origin.
  headers.set('Origin',APP_ORIGIN);
  headers.set('Accept','application/json');
  let body:ArrayBuffer|undefined;
  if (request.method === 'POST') {
    const declared=Number(request.headers.get('content-length')||'0');
    if (!Number.isFinite(declared)||declared>MAX_BODY) return failure(413,'Request body too large');
    body=await request.arrayBuffer();
    if (body.byteLength>MAX_BODY) return failure(413,'Request body too large');
  }
  try {
    const response=await fetch(upstream.toString(),{method:request.method,headers,body,
      redirect:'manual',signal:AbortSignal.timeout(20000)});
    if (response.status>=300&&response.status<400) return failure(502,'Unexpected upstream redirect');
    const result=new Headers({'Content-Type':response.headers.get('content-type')||'application/json',
      'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY'});
    const cookie=response.headers.get('set-cookie'); if(cookie) result.set('Set-Cookie',cookie);
    const retry=response.headers.get('retry-after'); if(retry) result.set('Retry-After',retry);
    return new Response(response.body,{status:response.status,headers:result});
  } catch {
    return failure(502,'Market Sentinel API is temporarily unavailable');
  }
}

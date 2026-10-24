interface Env { API_ORIGIN: string }
interface Context { request: Request; env: Env }
export async function onRequest({ request, env }: Context): Promise<Response> {
  if (!env.API_ORIGIN) return Response.json({detail:'Backend is not configured'}, {status:503});
  const incoming = new URL(request.url);
  const upstream = new URL(env.API_ORIGIN);
  if (upstream.protocol !== 'https:' || upstream.username || upstream.password || !upstream.hostname.endsWith('.onrender.com')) {
    return Response.json({detail:'Invalid backend configuration'}, {status:503});
  }
  upstream.pathname = incoming.pathname;
  upstream.search = incoming.search;
  const headers = new Headers();
  for (const key of ['content-type','cookie','origin','cf-access-jwt-assertion']) {
    const value = request.headers.get(key); if (value) headers.set(key,value);
  }
  headers.set('Accept','application/json');
  try {
    const response = await fetch(upstream, {method:request.method,headers,
      body:['GET','HEAD'].includes(request.method)?undefined:request.body,
      redirect:'manual',signal:AbortSignal.timeout(20000)});
    const result = new Headers({'Content-Type':response.headers.get('content-type') || 'application/json',
      'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY'});
    const cookieHeaders=response.headers as Headers & {getSetCookie?:()=>string[];getAll?:(name:string)=>string[]};
    const cookies=cookieHeaders.getSetCookie?.()||cookieHeaders.getAll?.('Set-Cookie')||[response.headers.get('set-cookie')].filter((value):value is string=>!!value);
    for(const cookie of cookies)result.append('Set-Cookie',cookie);
    if(incoming.pathname.startsWith('/api/auth/google/')&&response.status>=300&&response.status<400){
      const location=response.headers.get('location');
      if(!location)return Response.json({detail:'Authentication redirect is unavailable'}, {status:502});
      const target=new URL(location);
      const provider=incoming.pathname==='/api/auth/google/start'&&target.protocol==='https:'&&target.hostname.endsWith('.supabase.co')&&target.pathname==='/auth/v1/authorize';
      const callback=incoming.pathname==='/api/auth/google/callback'&&target.protocol==='https:'&&target.hostname==='market-research.getlevelupskillz.com'&&target.pathname==='/'&&!target.search&&['#radar','#google-signin-failed'].includes(target.hash);
      if(!provider&&!callback)return Response.json({detail:'Authentication redirect denied'}, {status:502});
      result.set('Location',target.toString());
    }
    const download=response.headers.get('content-disposition'); if(download)result.set('Content-Disposition',download);
    const retry = response.headers.get('retry-after'); if (retry) result.set('Retry-After',retry);
    return new Response(response.body,{status:response.status,headers:result});
  } catch {
    return Response.json({detail:'Market Sentinel API is temporarily unavailable'}, {status:502,headers:{'Cache-Control':'no-store'}});
  }
}

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
  for (const key of ['content-type','cookie','origin']) {
    const value = request.headers.get(key); if (value) headers.set(key,value);
  }
  headers.set('Accept','application/json');
  try {
    const response = await fetch(upstream, {method:request.method,headers,
      body:['GET','HEAD'].includes(request.method)?undefined:request.body,
      redirect:'manual',signal:AbortSignal.timeout(20000)});
    const result = new Headers({'Content-Type':response.headers.get('content-type') || 'application/json',
      'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY'});
    const cookie = response.headers.get('set-cookie'); if (cookie) result.set('Set-Cookie',cookie);
    const retry = response.headers.get('retry-after'); if (retry) result.set('Retry-After',retry);
    return new Response(response.body,{status:response.status,headers:result});
  } catch {
    return Response.json({detail:'Market Sentinel API is temporarily unavailable'}, {status:502,headers:{'Cache-Control':'no-store'}});
  }
}

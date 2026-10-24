from contextlib import asynccontextmanager
from dataclasses import asdict
from decimal import Decimal as D
import hashlib
import logging
import re
import time
import uuid
from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from .config import Settings
from .storage import Store
from .runtime import Runtime
from .security import verify_password,session_token,verify_session,SESSION_TTL
from .engine import paper_open,paper_close,POLICY,VERSION,evaluate_paper_plan
from .lab import walk_forward
from .traders import ADDRESS
from .changenow import estimate
from .access import AccessVerifier
from .smart_money import intelligence
from .catalogue import EXTRA_BOOK_LIMIT
from .capital import save_profile,get_profile,evaluate_real_plan
from .kraken_account import KrakenAccount, AccountError
from .backup import export_backup, BackupError
from .chart import PriceHistory
from .token_directory import browse as browse_tokens
from .suggestions import suggestions
from .ai_research import evidence_packet
from .members import active_member, members, invite, revoke, VIEWER_GET, shared_research, public_radar
from .google_auth import GoogleAuth,research_session,FLOW_COOKIE,SESSION_COOKIE,TTL

def connection_status():
    # Legacy capital-planning compatibility; never imply authenticated access.
    return {'provider':'kraken','status':'secure_setup_required','connected':False,
        'order_submission_enabled':False,'withdrawals_enabled':False,
        'app_hosting_plan':'free',
        'trading_fees':'Kraken transaction fees apply; no fee-free trading is promised.',
        'requirements':[
            'Use a dedicated Kraken API key with funds and order-query permissions.',
            'Only enable trading permissions for individually approved spot orders.',
            'Never enable withdrawals, funding or transfers.',
            'Regional eligibility, actual balances, pair rules and fees must be verified.',
            'Live orders require a configured encrypted server-side vault and explicit owner approval.'
        ],
        'documentation':'https://support.kraken.com/au/articles/360041395271-using-the-kraken-api-with-a-third-party-service',
        'fees_url':'https://www.kraken.com/features/fee-schedule'}

class KrakenConnect(BaseModel):
    model_config = ConfigDict(extra='forbid')
    api_key: str = Field(min_length=8,max_length=512)
    api_secret: str = Field(min_length=8,max_length=4096)
    country_code: str = Field(pattern=r'^[A-Z]{2}$')
    region: str = Field(min_length=1,max_length=100)
    eligibility_confirmed: bool
    dedicated_key_confirmed: bool

class KrakenOrderPreviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    symbol: str = Field(pattern=r'^[A-Z0-9.]{1,20}-USD$')
    side: str = Field(pattern=r'^(buy|sell)$')
    quantity: str = Field(min_length=1,max_length=40)
    limit_price: str = Field(min_length=1,max_length=40)

class KrakenOrderApproval(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preview_id: uuid.UUID
    confirmation: str = Field(max_length=64)

class KrakenOrderReconcile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    order_id: uuid.UUID

class AIResearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: str = Field(pattern=r'^(explain|challenge|search)$')
    card_id: str | None = Field(default=None,max_length=180)

class Login(BaseModel):
    password: str = Field(min_length=1,max_length=256)
class PaperOrder(BaseModel):
    provider: str = Field(pattern=r'^(kraken|coinbase)$')
    symbol: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,40}-USD$')
    notional: str = Field(pattern=r'^\d{1,4}(\.\d{1,2})?$')
    idempotency_key: uuid.UUID
class EntryPlan(BaseModel):
    provider: str = Field(pattern=r'^(kraken|coinbase)$')
    symbol: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,40}-USD$')
    notional: str = Field(pattern=r'^\d{1,4}(\.\d{1,2})?$')
    stop: str = Field(pattern=r'^\d{1,9}(\.\d{1,8})?$')
    target: str = Field(pattern=r'^\d{1,9}(\.\d{1,8})?$')
class Watch(BaseModel):
    address: str = Field(pattern=r'^0x[0-9a-fA-F]{40}$')
    label: str = Field(default='Public wallet',max_length=60)
class MarketWatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    market_id: str = Field(min_length=1,max_length=150)
    enabled: bool = True
class CapitalProfile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    capital_usd: str = Field(max_length=40)
    available_cash_usd: str = Field(max_length=40)
    existing_crypto_exposure_usd: str = Field(max_length=40)
    daily_realized_pnl_usd: str = Field(max_length=40)
    risk_per_trade_pct: str = Field(max_length=20)
    max_position_pct: str = Field(max_length=20)
    max_crypto_exposure_pct: str = Field(max_length=20)
    daily_loss_limit_pct: str = Field(max_length=20)
class RealPlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str = Field(pattern=r'^(kraken|coinbase)$')
    symbol: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,40}-USD$')
    stop: str = Field(pattern=r'^\d{1,12}(\.\d{1,18})?$')
    target: str = Field(pattern=r'^\d{1,12}(\.\d{1,18})?$')
class QuoteRequest(BaseModel):
    source: str = Field(pattern=r'^(btc|eth|usdc)$')
    destination: str = Field(pattern=r'^(btc|eth|usdc)$')
    amount: str = Field(pattern=r'^\d{1,7}(\.\d{1,8})?$')
class ResearchInvite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    email: str=Field(min_length=3,max_length=254)


class Control(BaseModel):
    stopped: bool
class Bar(BaseModel):
    timestamp: float = Field(allow_inf_nan=False)
    close: str = Field(max_length=40)
class Lab(BaseModel):
    bars: list[Bar] = Field(min_length=120,max_length=5000)
    source: str = Field(min_length=1,max_length=500)
    fee_bps: float = Field(default=60,ge=0,le=500,allow_inf_nan=False)
    slippage_bps: float = Field(default=5,ge=0,le=500,allow_inf_nan=False)
    latency_bars: int = Field(default=1,ge=0,le=3)


def create_app(settings=None,store=None):
    settings = settings or Settings()
    settings.validate()
    store = store or Store(settings.database_url)
    runtime = Runtime(store,settings)
    kraken_account = KrakenAccount(store,settings,runtime.books)
    access = AccessVerifier(settings.access_team,settings.access_aud,settings.owner_email)
    price_history = PriceHistory()
    google_auth=GoogleAuth(store,settings)
    @asynccontextmanager
    async def lifespan(app):
        try:
            await runtime.start()
            yield
        finally:
            await runtime.stop()
            store.close()
    app = FastAPI(title='Market Sentinel AI',version='0.6.2',lifespan=lifespan,
                  docs_url='/docs' if settings.environment=='development' else None,redoc_url=None)
    app.state.store,app.state.runtime,app.state.settings = store,runtime,settings
    app.state.kraken_account = kraken_account
    app.state.access,app.state.google_auth=access,google_auth
    if settings.environment=='development':
        app.add_middleware(CORSMiddleware,allow_origins=[settings.origin],allow_credentials=True,allow_methods=['GET','POST'],allow_headers=['Content-Type'])

    @app.middleware('http')
    async def guard(request,call_next):
        path = request.url.path
        if path in ['/health/live','/health/ready']:
            return await call_next(request)
        try:
            length=int(request.headers.get('content-length','0') or '0')
        except ValueError:
            return Response('Invalid Content-Length',status_code=400)
        if length>1024*1024:
            return Response('Request body too large',status_code=413)
        # Content-Length is optional; bound chunked bodies before JSON parsing.
        if request.method not in ['GET','HEAD','OPTIONS']:
            chunks,size = [],0
            async for chunk in request.stream():
                size += len(chunk)
                if size>1024*1024:
                    return Response('Request body too large',status_code=413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        # Defense in depth: origin validation is checked even on login and logout.
        google_identity=research_session(request.cookies.get(SESSION_COOKIE),settings.session_secret,settings.environment)
        google_owner=bool(google_identity and google_identity['role']=='owner' and settings.google_owner_enabled and google_identity['email']==settings.owner_email.lower())
        if request.method not in ['GET','HEAD','OPTIONS']:
            origin=request.headers.get('origin')
            permitted=origin==settings.origin
            if origin and origin==getattr(settings,'research_origin',''):
                permitted=path=='/api/auth/google/logout' or (google_owner and path!='/api/session/login')
            if not permitted:return Response('Origin denied',status_code=403)
        peer = request.client.host if request.client else 'unknown'
        client_key = hashlib.sha256(peer.encode()).hexdigest()
        if not store.rate('api:'+client_key,600):
            return Response('Rate limit exceeded',status_code=429,headers={'Retry-After':'60'})
        request.state.role='anonymous'
        request.state.auth_method='none'
        if path not in ['/api/session/login','/api/auth/options','/api/auth/google/start','/api/auth/google/callback','/api/auth/google/logout'] and request.method!='OPTIONS':
            token=request.headers.get('cf-access-jwt-assertion')
            owner_session=verify_session(request.cookies.get('sentinel_session'),settings.session_secret,settings.environment)
            identity=None
            if owner_session:
                request.state.role='owner';request.state.auth_method='owner_password'
            elif settings.access_aud and await access.verify(token):
                request.state.role='owner';request.state.auth_method='cloudflare_access'
            else:
                identity=google_identity
                if google_owner:request.state.role='owner';request.state.auth_method='supabase_google'
                elif identity and identity['role']=='viewer' and (active_member(store,identity['email']) or identity['email']==settings.owner_email.lower()):request.state.role='viewer';request.state.auth_method='supabase_google'
            if request.state.role=='anonymous':
                return Response('Invitation required' if identity else 'Authentication required',status_code=403 if identity else 401,headers={'Cache-Control':'no-store'})
            if request.state.role=='viewer' and not (request.method=='GET' and path in VIEWER_GET):
                return Response('Research access only. Owner account data and changes are unavailable.',status_code=403,headers={'Cache-Control':'no-store'})
            actor_key=hashlib.sha256(('owner' if request.state.role=='owner' else identity['email']).encode()).hexdigest()
            if not store.rate('identity:'+actor_key,180 if request.state.role=='owner' else 90):return Response('Request limit reached',status_code=429,headers={'Retry-After':'60','Cache-Control':'no-store'})
        response = await call_next(request)
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})
        return response

    @app.exception_handler(RequestValidationError)
    async def safe_request_validation(request,error):
        # Pydantic validation errors can contain rejected API credentials in
        # their input fields. Never echo raw validation details to clients.
        return JSONResponse({'detail':'Invalid request fields.'},status_code=422)

    @app.exception_handler(ValueError)
    async def invalid(request,error):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':str(error)},status_code=422)

    @app.get('/health/live')
    async def live():
        return {'status':'alive','app_version':'0.7.0','live_trading':kraken_account.enabled,
                'individual_order_approval_required':True,'autonomous_trading':False,'withdrawals_enabled':False}

    @app.get('/health/ready')
    async def ready(response:Response):
        try:
            store.get_state('control')
            ok = runtime.healthy()
        except Exception:
            ok = False
        if not ok:
            response.status_code=503
        return {'status':'ready' if ok else 'degraded','live_trading':kraken_account.enabled,
                'individual_order_approval_required':True,'autonomous_trading':False,'withdrawals_enabled':False}

    @app.post('/api/session/login')
    async def login(body:Login,request:Request,response:Response):
        peer = request.client.host if request.client else 'unknown'
        if not store.rate('login:'+hashlib.sha256(peer.encode()).hexdigest(),5,900):
            raise HTTPException(429,'Too many login attempts; retry after 15 minutes')
        if not settings.session_secret or not verify_password(body.password,settings.password_hash):
            store.put('audit',{'action':'login.denied','actor':'anonymous'})
            raise HTTPException(401,'Invalid credentials or owner access is not configured')
        response.set_cookie('sentinel_session',session_token(settings.session_secret,settings.environment),
            httponly=True,secure=settings.environment!='development',samesite='strict',max_age=SESSION_TTL,path='/')
        store.put('audit',{'action':'login.success','actor':'owner'})
        return {'authenticated':True,'scope':'owner'}

    @app.get('/api/session')
    async def session(request:Request):
        if request.state.role=='viewer':return {'authenticated':True,'scope':'research','role':'viewer','read_only':True,'live_trading':False,'autonomous_trading':False}
        return {'authenticated':True,'scope':'owner','role':'owner','read_only':False,'live_trading':kraken_account.enabled,'autonomous_trading':False}

    @app.post('/api/session/logout')
    async def logout(response:Response):
        response.delete_cookie('sentinel_session',path='/')
        return {'authenticated':False}

    @app.get('/api/dashboard')
    async def dashboard(request:Request):
        if request.state.role=='viewer':
            return {'role':'viewer','read_only':True,'as_of':time.time(),'environment':settings.environment,'live_trading':False,
                'markets':[m for m in runtime.market_view() if m['provider']!='coinbase'],
                'providers':{p:({'state':'owner_display_only','reason':'Available only in the owner workspace'} if p=='coinbase' else v) for p,v in runtime.status.items()},'signals':[],
                'control':{'stopped':True,'reason':'research_only'},'account':None,'opportunities':[],'paper':[],
                'funding':list(runtime.funding.values()),'trades':[t for t in list(runtime.trades)[-40:] if t.get('provider')!='coinbase'],
                'strategy_version':VERSION,'last_persist':runtime.last_persist,'journal_error':None,
                'changenow':{'configured':False,'approved':False,'kind':'indicative_swap_estimates'},
                'auth_method':'supabase_google','alerts_configured':False,
                'hosting':{'tier':settings.hosting_tier,'continuous_collection_guaranteed':False,'database_expiry':settings.database_expiry or None}}
        return {'role':'owner','read_only':False,'as_of':time.time(),'environment':settings.environment,'live_trading':kraken_account.enabled,
            'markets':runtime.market_view(),'providers':runtime.status,'signals':runtime.current_signals(),
            'control':store.get_state('control'),'account':store.get_state('account'),
            'opportunities':store.list('opportunity',20),'paper':store.list('paper',1000),
            'funding':list(runtime.funding.values()),'trades':list(runtime.trades)[-40:],
            'strategy_version':VERSION,'last_persist':runtime.last_persist,'journal_error':runtime.last_error,
            'collector':{'state':runtime.collector_state,'jobs':runtime.job_status,'independent_of_dashboard':True},
            'changenow':{'configured':bool(settings.changenow_key),'approved':settings.changenow_approved,'kind':'indicative_swap_estimates'},
            'auth_method':request.state.auth_method,'alerts_configured':bool(settings.ntfy_topic),'hosting':{'tier':settings.hosting_tier,'continuous_collection_guaranteed':False,'database_expiry':settings.database_expiry or None},
            'data_policy':'Only explicitly approved public providers are connected.'}

    @app.get('/api/records/{kind}')
    async def records(request:Request,kind:str,q:str='',limit:int=100):
        if kind not in ['opportunity','paper','forensic','alert','audit','lab','market_snapshot','trader_event','quote','entry_plan','radar_signal','real_plan','trader_cohort']:
            raise HTTPException(404,'Unknown record type')
        rows=store.list(kind,max(1,min(limit,1000)),q[:200])
        if request.state.role=='viewer':rows=[r for r in rows if r.get('provider')!='coinbase' and r.get('snapshot',{}).get('provider')!='coinbase']
        return {'records':shared_research(rows) if request.state.role=='viewer' else rows,'as_of':time.time()}

    @app.get('/api/tokens')
    async def tokens(q:str=Query('',max_length=100),section:str=Query('all',pattern=r'^(all|new|gainers|decliners|best|worst|predicted-best|predicted-worst)$'),page:int=Query(1,ge=1,le=100000),limit:int=Query(25,ge=1,le=100)):
        return browse_tokens(runtime.catalogue,runtime.books,q,section,page,limit)

    @app.get('/api/assets')
    async def assets(q:str=Query('',max_length=100),source:str=Query('live',pattern=r'^(live|all|coinpaprika|kraken|hyperliquid)$'),
                     page:int=Query(1,ge=1,le=100000),limit:int=Query(25,ge=1,le=100),
                     active:str=Query('active',pattern=r'^(active|inactive|all)$')):
        result = runtime.catalogue.search(q,source,page,limit,active)
        result['watched_markets'] = runtime.live_watch
        result['extra_book_limit'] = EXTRA_BOOK_LIMIT
        return result

    @app.post('/api/markets/watch')
    async def market_watch(body:MarketWatch):
        return runtime.set_market_watch(body.market_id,body.enabled)

    @app.post('/api/ai/context')
    async def ai_context(body:AIResearchRequest):
        try:return evidence_packet(runtime,store,body.mode,body.card_id)
        except LookupError as error:raise HTTPException(409,str(error)) from None
        except ValueError as error:raise HTTPException(429,str(error)) from None

    @app.get('/api/price-history')
    async def historical_prices(symbol:str=Query(...,pattern=r'^[A-Z0-9.]{1,40}-(USD|USDC-PERP)$'),
                                provider:str=Query('kraken',pattern=r'^(kraken|hyperliquid)$'),
                                interval:int=Query(1,ge=1,le=15)):
        if provider not in settings.providers:
            raise HTTPException(503,'This public provider is not enabled')
        known = any(row.get('watch_symbol')==symbol and row.get('active')
                    for row in runtime.catalogue.venues.get(provider,{}).values())
        if not known and (provider,symbol) not in runtime.books:
            raise HTTPException(404,'Choose an observed spot or perpetual market')
        try:return await price_history.get(symbol,interval,provider)
        except ValueError as error:raise HTTPException(503,str(error)) from None

    @app.get('/api/suggestions')
    async def trade_suggestions():
        return suggestions(runtime.radar.snapshot(runtime.books),intelligence(store,runtime.books),
                           store,stopped=store.get_state('control')['stopped'])

    @app.get('/api/radar')
    async def radar(request:Request):
        result=runtime.radar.snapshot(runtime.books)
        return public_radar(result) if request.state.role=='viewer' else result

    @app.post('/api/radar/{signal_id}/paper')
    async def radar_paper(signal_id:str):
        paper_id = str(uuid.uuid5(uuid.NAMESPACE_URL,'market-sentinel:radar:'+signal_id))
        prior = store.get('paper',paper_id)
        if prior:return prior
        view = runtime.radar.snapshot(runtime.books)
        setup = next((r for r in view['setups'] if r['id']==signal_id),None)
        if not setup or setup['decision']!='GO':
            raise HTTPException(409,'This paper setup is unavailable, expired or no longer passes current checks')
        book = runtime.books.get((setup['provider'],setup['symbol']))
        if not book:raise HTTPException(409,'A fresh detailed book is required')
        result = paper_open(store,book,setup['notional_usd'],paper_id)
        result.update(origin_signal_id=signal_id,radar_setup=setup,strategy_version=view['strategy_version'])
        store.replace(result['id'],result)
        return result

    @app.get('/api/capital')
    async def capital():
        return {'profile':get_profile(store),'execution_enabled':kraken_account.status()['order_submission_enabled'],'connection':dict(connection_status(),**kraken_account.status())}

    @app.post('/api/capital')
    async def capital_update(body:CapitalProfile):
        return {'profile':save_profile(store,body.model_dump()),'execution_enabled':False,'connection':connection_status()}

    @app.post('/api/capital/plans')
    async def real_plan(body:RealPlanRequest):
        if getattr(settings,'coinbase_display_only',False) and body.provider=='coinbase':raise HTTPException(403,'Coinbase is available for personal price display only')
        book = runtime.books.get((body.provider,body.symbol))
        if not book:raise HTTPException(409,'Inspect the matching detailed market book before calculating a real-capital plan')
        result = evaluate_real_plan(store,book,body.stop,body.target)
        result['preferred_execution_venue'] = 'kraken'
        result['connection'] = dict(connection_status(),**kraken_account.status())
        result['venue_warning'] = 'This plan uses the named source venue. Other venues require their own actual quotes, balances, fee tiers and product rules.'
        return store.put('real_plan',result)

    @app.exception_handler(AccountError)
    async def kraken_account_error(request,error):
        # AccountError messages are fixed and contain no submitted credentials.
        return JSONResponse({'detail':str(error)},status_code=409)

    @app.exception_handler(BackupError)
    async def backup_error(request,error):
        return JSONResponse({'detail':str(error)},status_code=409)

    @app.post('/api/backup/export')
    async def backup_export():
        # Guard middleware authenticates the owner before this handler.
        # A deliberately low limit prevents costly repeated snapshots.
        if not store.rate('backup:owner',2,3600):
            raise HTTPException(429,'Backup export limit reached; retry later.')
        archive=export_backup(store)
        return Response(content=archive,media_type='application/json',
            headers={'Content-Disposition':'attachment; filename="market-sentinel-research-backup.json"',
                     'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.get('/api/auth/options')
    async def auth_options():
        return {'google_ready':google_auth.ready,
            'research_login_ready':google_auth.ready,'owner_google_enabled':google_auth.ready and settings.google_owner_enabled,
            'research_url':getattr(settings,'research_origin','') or None,'owner_url':settings.origin,'invite_only':True}

    @app.get('/api/auth/google/start')
    async def google_start(request:Request):
        peer=hashlib.sha256((request.client.host if request.client else 'unknown').encode()).hexdigest()
        if not store.rate('google-start:'+peer,5,300):raise HTTPException(429,'Sign-in request limit reached. Try later.')
        url,nonce=google_auth.start()
        response=RedirectResponse(url,status_code=302)
        response.set_cookie(FLOW_COOKIE,nonce,httponly=True,secure=True,samesite='lax',max_age=300,path='/api/auth/google')
        return response

    @app.get('/api/auth/google/callback')
    async def google_callback(request:Request):
        origin=getattr(settings,'research_origin','') or settings.origin
        try:
            session=await google_auth.finish(request.query_params.get('code'),request.cookies.get(FLOW_COOKIE))
            identity=research_session(session,settings.session_secret,settings.environment)
            response=RedirectResponse(origin+('/#mission-control' if identity and identity['role']=='owner' else '/#radar'),status_code=302)
            response.set_cookie(SESSION_COOKIE,session,httponly=True,secure=True,samesite='strict',max_age=TTL,path='/')
        except ValueError:
            response=RedirectResponse(origin+'/#google-signin-failed',status_code=302)
        response.delete_cookie(FLOW_COOKIE,path='/api/auth/google',secure=True,httponly=True,samesite='lax')
        response.headers['Referrer-Policy']='no-referrer'
        return response

    @app.post('/api/auth/google/logout')
    async def google_logout():
        response=JSONResponse({'authenticated':False})
        response.delete_cookie(SESSION_COOKIE,path='/',secure=True,httponly=True,samesite='strict')
        return response

    @app.get('/api/members')
    async def member_list():
        return {'members':members(store),'limit':10,'role':'viewer','expires_after_days':30}

    @app.post('/api/members')
    async def member_invite(body:ResearchInvite):
        if not store.rate('members:owner',10,3600):raise HTTPException(429,'Invitation update limit reached')
        return invite(store,body.email,settings.owner_email)

    @app.post('/api/members/revoke')
    async def member_revoke(body:ResearchInvite):
        return revoke(store,body.email)

    @app.get('/api/connections')
    async def connections():
        return dict(connection_status(),**kraken_account.status())

    @app.post('/api/connections/kraken')
    async def kraken_connect(body:KrakenConnect):
        if not store.rate('kraken:connect',3,300):raise HTTPException(429,'Account verification limit reached. Retry after five minutes.')
        return await kraken_account.connect(**body.model_dump())

    @app.get('/api/connections/kraken/account')
    async def kraken_account_snapshot():
        if not store.rate('kraken:account',6):raise HTTPException(429,'Account refresh limit reached. Retry after one minute.')
        return await kraken_account.account()

    @app.get('/api/connections/kraken/orders')
    async def kraken_order_history():
        return kraken_account.order_history()

    @app.post('/api/connections/kraken/disconnect')
    async def kraken_disconnect():
        return kraken_account.disconnect()

    @app.post('/api/connections/kraken/preview')
    async def kraken_preview(body:KrakenOrderPreviewRequest):
        if not store.rate('kraken:preview',4):raise HTTPException(429,'Order review limit reached. Retry after one minute.')
        return await kraken_account.preview(**body.model_dump())

    @app.post('/api/connections/kraken/approve')
    async def kraken_approve(body:KrakenOrderApproval):
        if not store.rate('kraken:approve',4):raise HTTPException(429,'Order approval limit reached. Check the saved order status before trying again.')
        return await kraken_account.approve(str(body.preview_id),body.confirmation)

    @app.post('/api/connections/kraken/reconcile')
    async def kraken_reconcile(body:KrakenOrderReconcile):
        if not store.rate('kraken:reconcile',6):raise HTTPException(429,'Reconciliation limit reached. Retry a read after one minute; do not resend the order.')
        return await kraken_account.reconcile(str(body.order_id))

    @app.get('/api/opportunities/{id}')
    async def opportunity(id:str):
        doc = store.get('opportunity',id)
        if not doc:
            raise HTTPException(404,'Opportunity not found')
        return doc

    @app.post('/api/paper/open')
    async def open_position(body:PaperOrder):
        if getattr(settings,'coinbase_display_only',False) and body.provider=='coinbase':raise HTTPException(403,'Coinbase is available for personal price display only')
        book = runtime.books.get((body.provider,body.symbol))
        if not book:
            raise HTTPException(409,'Live book unavailable; no synthetic fill will be substituted')
        return paper_open(store,book,body.notional,str(body.idempotency_key))

    @app.post('/api/paper/{id}/close')
    async def close_position(id:str):
        position = store.get('paper',id)
        if not position:
            raise HTTPException(404,'Paper position not found')
        book = runtime.books.get((position['provider'],position['symbol']))
        if not book:
            raise HTTPException(409,'Original venue book unavailable')
        return paper_close(store,id,book)

    @app.post('/api/plans')
    async def plan(body:EntryPlan):
        if getattr(settings,'coinbase_display_only',False) and body.provider=='coinbase':raise HTTPException(403,'Coinbase is available for personal price display only')
        book=runtime.books.get((body.provider,body.symbol))
        if not book:raise HTTPException(409,'A live book is required for plan evaluation')
        positions=[p for p in store.list('paper',10000) if p['status']=='open']
        exposure=sum((D(p['entry_notional']) for p in positions),D(0))
        now=time.time()
        day_pnl=sum((D(p.get('net_pnl','0')) for p in store.list('paper',10000) if p.get('closed_at',0)>=now-now%86400),D(0))
        result=evaluate_paper_plan(book,body.notional,body.stop,body.target,exposure=exposure,
            cash=D(store.get_state('account')['cash']),daily_pnl=day_pnl,stopped=store.get_state('control')['stopped'])
        doc=store.put('entry_plan',result)
        if result['decision']=='GO':
            store.put('alert',{'title':body.symbol+' paper experiment passed risk checks; predictive edge remains unvalidated.',
                'status':'queued' if settings.ntfy_topic else 'inbox_only','plan_id':doc['id'],'mode':'paper_only','attempts':0})
        return doc

    @app.post('/api/control')
    async def control(body:Control):
        with store.transaction():
            store.set_state('control',{'stopped':body.stopped,'changed_at':time.time()})
            store.put('audit',{'action':'emergency_stop' if body.stopped else 'resume','actor':'owner'})
        return store.get_state('control')

    @app.get('/api/traders')
    async def traders(request:Request):
        items = []
        for trader in store.list('watchlist',10):
            snapshot = store.get_state('trader:'+trader['address'])
            history=store.get_state('trader_history:'+trader['address'])
            if history:history={k:v for k,v in history.items() if k!='raw_fills'}
            items.append(dict(trader,snapshot=snapshot,history=history,history_error=store.get_state('trader_history_error:'+trader['address']),error=store.get_state('trader_error:'+trader['address']),
                freshness='live' if snapshot and time.time()-snapshot['received_at']<90 else 'stale' if snapshot else 'unavailable'))
        result={'traders':items,'events':store.list('trader_event',100),'intelligence':intelligence(store,runtime.books),
            'disclosure':'Manual and automatically discovered large-trade participants. Size, identity and trading success are not equivalent.'}
        return shared_research(result) if request.state.role=='viewer' else result

    @app.get('/api/intelligence')
    async def market_intelligence(request:Request):
        result=intelligence(store,runtime.books)
        return shared_research(result) if request.state.role=='viewer' else result

    @app.get('/api/trader-directory')
    async def trader_directory(q:str=Query('',max_length=100),page:int=Query(1,ge=1,le=100),
                               limit:int=Query(12,ge=1,le=50)):
        # A dashboard request only reads the bounded background cache. It cannot
        # trigger a provider download or change the owner's watched addresses.
        return runtime.trader_directory.directory(q,page,limit)

    @app.post('/api/traders')
    async def add_trader(body:Watch):
        address = body.address.lower()
        with store.transaction():
            if len(store.list('watchlist',10))>=10 and not store.get('watchlist',address):
                raise ValueError('Watchlist limit: 10 public addresses')
            result = store.put('watchlist',{'address':address,'label':body.label,'added_at':time.time()},id=address)
            store.put('audit',{'action':'watchlist.add','address':address,'actor':'owner'})
        return result

    @app.post('/api/lab')
    async def lab(body:Lab):
        result = walk_forward([b.model_dump() for b in body.bars],body.source,body.fee_bps,body.slippage_bps,body.latency_bars)
        # Preserve the exact input and assumptions for reproducibility.
        return store.put('lab',dict(result,input=body.model_dump()))

    @app.post('/api/quotes/changenow')
    async def quote(body:QuoteRequest):
        if not store.rate('quote:owner',12):
            raise HTTPException(429,'Quote request limit reached; retry after one minute')
        key='quote-cache:'+body.source+':'+body.destination+':'+body.amount
        cached=store.get_state(key)
        if cached and time.time()-cached['received_at']<30:
            return dict(cached,cached=True)
        result=await estimate(settings,body.source,body.destination,body.amount)
        doc=store.put('quote',result)
        store.set_state(key,doc)
        return dict(doc,cached=False)

    @app.post('/api/alerts/test')
    async def test_alert():
        if not settings.ntfy_topic or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',settings.ntfy_topic):
            raise HTTPException(409,'Configure a private ntfy.sh topic of at least 16 characters in backend secrets')
        return store.put('alert',{'title':'Market Sentinel mobile delivery test — no trading action.','status':'queued','attempts':0,'mode':'delivery_test'})

    return app


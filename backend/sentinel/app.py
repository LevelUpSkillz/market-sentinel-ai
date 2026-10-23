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
from fastapi.responses import JSONResponse
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

def connection_status():
    # A preferred venue is not an authenticated account connection.
    return {'provider':'kraken','status':'secure_setup_required','connected':False,
        'order_submission_enabled':False,'withdrawals_enabled':False,
        'app_hosting_plan':'free','trading_fees':'Kraken transaction fees apply; no fee-free trading is promised.',
        'requirements':['Kraken supports owner-created API keys for account access and trading; OAuth is an alternative that requires a provider-approved client.',
            'This app still needs an encrypted server-side credential flow and verified account permissions before either route can connect.',
            'A future restricted connection must exclude funding, transfers and withdrawals. Public wallet watching does not authorize trading.',
            'Provider permission for this app’s market-data use and regional eligibility must be verified.',
            'Every future order requires verified Kraken balances/product rules, current venue costs and a separate user approval.'],
        'documentation':'https://support.kraken.com/au/articles/360041395271-using-the-kraken-api-with-a-third-party-service',
        'oauth_documentation':'https://docs-legacy.kraken.com/api/docs/oauth/kraken-connect/',
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
    @asynccontextmanager
    async def lifespan(app):
        try:
            await runtime.start()
            yield
        finally:
            await runtime.stop()
            store.close()
    app = FastAPI(title='Market Sentinel AI',version='0.4.1',lifespan=lifespan,
                  docs_url='/docs' if settings.environment=='development' else None,redoc_url=None)
    app.state.store,app.state.runtime,app.state.settings = store,runtime,settings
    app.state.kraken_account = kraken_account
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
        if request.method not in ['GET','HEAD','OPTIONS'] and request.headers.get('origin')!=settings.origin:
            return Response('Origin denied',status_code=403)
        peer = request.client.host if request.client else 'unknown'
        client_key = hashlib.sha256(peer.encode()).hexdigest()
        if not store.rate('api:'+client_key,180):
            return Response('Rate limit exceeded',status_code=429,headers={'Retry-After':'60'})
        if path not in ['/api/session/login'] and request.method!='OPTIONS':
            token=request.headers.get('cf-access-jwt-assertion')
            allowed=await access.verify(token) if settings.access_aud else verify_session(request.cookies.get('sentinel_session'),settings.session_secret,settings.environment)
            if not allowed:
                return Response('Authentication required',status_code=401)
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
        return {'status':'alive','app_version':'0.4.1','live_trading':False}

    @app.get('/health/ready')
    async def ready(response:Response):
        try:
            store.get_state('control')
            ok = runtime.healthy()
        except Exception:
            ok = False
        if not ok:
            response.status_code=503
        return {'status':'ready' if ok else 'degraded','live_trading':False}

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
        return {'authenticated':True,'scope':'paper'}

    @app.get('/api/session')
    async def session():
        return {'authenticated':True,'scope':'paper','live_trading':False}

    @app.post('/api/session/logout')
    async def logout(response:Response):
        response.delete_cookie('sentinel_session',path='/')
        return {'authenticated':False}

    @app.get('/api/dashboard')
    async def dashboard():
        return {'as_of':time.time(),'environment':settings.environment,'live_trading':False,
            'markets':runtime.market_view(),'providers':runtime.status,'signals':runtime.current_signals(),
            'control':store.get_state('control'),'account':store.get_state('account'),
            'opportunities':store.list('opportunity',20),'paper':store.list('paper',1000),
            'funding':list(runtime.funding.values()),'trades':list(runtime.trades)[-40:],
            'strategy_version':VERSION,'last_persist':runtime.last_persist,'journal_error':runtime.last_error,
            'collector':{'state':runtime.collector_state,'jobs':runtime.job_status,'independent_of_dashboard':True},
            'changenow':{'configured':bool(settings.changenow_key),'approved':settings.changenow_approved,'kind':'indicative_swap_estimates'},
            'auth_method':'cloudflare_access' if settings.access_aud else 'owner_password','alerts_configured':bool(settings.ntfy_topic),'hosting':{'tier':settings.hosting_tier,'continuous_collection_guaranteed':False,'database_expiry':settings.database_expiry or None},
            'data_policy':'Only explicitly approved public providers are connected.'}

    @app.get('/api/records/{kind}')
    async def records(kind:str,q:str='',limit:int=100):
        if kind not in ['opportunity','paper','forensic','alert','audit','lab','market_snapshot','trader_event','quote','entry_plan','radar_signal','real_plan','trader_cohort']:
            raise HTTPException(404,'Unknown record type')
        return {'records':store.list(kind,max(1,min(limit,1000)),q[:200]),'as_of':time.time()}

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

    @app.get('/api/radar')
    async def radar():
        return runtime.radar.snapshot(runtime.books)

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
        return {'profile':get_profile(store),'execution_enabled':False,'connection':connection_status()}

    @app.post('/api/capital')
    async def capital_update(body:CapitalProfile):
        return {'profile':save_profile(store,body.model_dump()),'execution_enabled':False,'connection':connection_status()}

    @app.post('/api/capital/plans')
    async def real_plan(body:RealPlanRequest):
        book = runtime.books.get((body.provider,body.symbol))
        if not book:raise HTTPException(409,'Inspect the matching detailed market book before calculating a real-capital plan')
        result = evaluate_real_plan(store,book,body.stop,body.target)
        result['preferred_execution_venue'] = 'kraken'
        result['connection'] = connection_status()
        result['venue_warning'] = 'This plan uses the named source venue. Other venues require their own actual quotes, balances, fee tiers and product rules.'
        return store.put('real_plan',result)

    @app.exception_handler(AccountError)
    async def kraken_account_error(request,error):
        # AccountError messages are fixed and contain no submitted credentials.
        return JSONResponse({'detail':str(error)},status_code=409)

    @app.get('/api/connections')
    async def connections():
        return dict(connection_status(),**kraken_account.status())

    @app.post('/api/connections/kraken')
    async def kraken_connect(body:KrakenConnect):
        return await kraken_account.connect(**body.model_dump())

    @app.get('/api/connections/kraken/account')
    async def kraken_account_snapshot():
        return await kraken_account.account()

    @app.post('/api/connections/kraken/disconnect')
    async def kraken_disconnect():
        return kraken_account.disconnect()

    @app.post('/api/connections/kraken/preview')
    async def kraken_preview(body:KrakenOrderPreviewRequest):
        return await kraken_account.preview(**body.model_dump())

    @app.post('/api/connections/kraken/approve')
    async def kraken_approve(body:KrakenOrderApproval):
        return await kraken_account.approve(str(body.preview_id),body.confirmation)

    @app.post('/api/connections/kraken/reconcile')
    async def kraken_reconcile(body:KrakenOrderReconcile):
        return await kraken_account.reconcile(str(body.order_id))

    @app.get('/api/opportunities/{id}')
    async def opportunity(id:str):
        doc = store.get('opportunity',id)
        if not doc:
            raise HTTPException(404,'Opportunity not found')
        return doc

    @app.post('/api/paper/open')
    async def open_position(body:PaperOrder):
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
    async def traders():
        items = []
        for trader in store.list('watchlist',10):
            snapshot = store.get_state('trader:'+trader['address'])
            history=store.get_state('trader_history:'+trader['address'])
            if history:history={k:v for k,v in history.items() if k!='raw_fills'}
            items.append(dict(trader,snapshot=snapshot,history=history,history_error=store.get_state('trader_history_error:'+trader['address']),error=store.get_state('trader_error:'+trader['address']),
                freshness='live' if snapshot and time.time()-snapshot['received_at']<90 else 'stale' if snapshot else 'unavailable'))
        return {'traders':items,'events':store.list('trader_event',100),'intelligence':intelligence(store,runtime.books),
            'disclosure':'Manual and automatically discovered large-trade participants. Size, identity and trading success are not equivalent.'}

    @app.get('/api/intelligence')
    async def market_intelligence():
        return intelligence(store,runtime.books)

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

from contextlib import asynccontextmanager
from dataclasses import asdict
from decimal import Decimal as D
import hashlib
import logging
import re
import time
import uuid
from fastapi import FastAPI, HTTPException, Request, Response
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

class Login(BaseModel):
    password: str = Field(min_length=1,max_length=256)
class PaperOrder(BaseModel):
    provider: str = Field(pattern=r'^(kraken|coinbase)$')
    symbol: str = Field(pattern=r'^(BTC|ETH|SOL)-USD$')
    notional: str = Field(pattern=r'^\d{1,4}(\.\d{1,2})?$')
    idempotency_key: uuid.UUID
class EntryPlan(BaseModel):
    provider: str = Field(pattern=r'^(kraken|coinbase)$')
    symbol: str = Field(pattern=r'^(BTC|ETH|SOL)-USD$')
    notional: str = Field(pattern=r'^\d{1,4}(\.\d{1,2})?$')
    stop: str = Field(pattern=r'^\d{1,9}(\.\d{1,8})?$')
    target: str = Field(pattern=r'^\d{1,9}(\.\d{1,8})?$')
class Watch(BaseModel):
    address: str = Field(pattern=r'^0x[0-9a-fA-F]{40}$')
    label: str = Field(default='Public wallet',max_length=60)
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
    access = AccessVerifier(settings.access_team,settings.access_aud,settings.owner_email)
    @asynccontextmanager
    async def lifespan(app):
        try:
            await runtime.start()
            yield
        finally:
            await runtime.stop()
            store.close()
    app = FastAPI(title='Market Sentinel AI',version='0.2.0',lifespan=lifespan,
                  docs_url='/docs' if settings.environment=='development' else None,redoc_url=None)
    app.state.store,app.state.runtime,app.state.settings = store,runtime,settings
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

    @app.exception_handler(ValueError)
    async def invalid(request,error):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':str(error)},status_code=422)

    @app.get('/health/live')
    async def live():
        return {'status':'alive','app_version':'0.2.0','live_trading':False}

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
        if kind not in ['opportunity','paper','forensic','alert','audit','lab','market_snapshot','trader_event','quote','entry_plan']:
            raise HTTPException(404,'Unknown record type')
        return {'records':store.list(kind,max(1,min(limit,1000)),q[:200]),'as_of':time.time()}

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

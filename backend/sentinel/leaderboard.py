"""Experimental owner-only public frontend directory, never a global skill rank.

The undocumented upstream JSON is decoded one row at a time. No full response or
full parsed leaderboard is retained on the free Render instance.
"""
import asyncio
import codecs
import heapq
import json
import logging
import time
import unicodedata
from decimal import Decimal as D
import httpx
from .models import decimal
from .traders import ADDRESS

SOURCE_URL = 'https://stats-data.hyperliquid.xyz/Mainnet/leaderboard'
SOURCE = 'Hyperliquid experimental public frontend leaderboard'
VERSION = 'public-directory-v1'
CACHE_KEY = 'public_leaderboard'
ERROR_KEY = 'public_leaderboard_error'
CACHE_SECONDS = 6*3600
MAX_BUFFER_BYTES = 1024*1024
MAX_DOWNLOAD_BYTES = 100*1024*1024
MAX_ROWS = 200000
CANDIDATE_LIMIT = 100
WINDOWS = ('day','week','month','allTime')
SELECTION_BASIS = ('Discovery shortlist only: prefer more available reported windows, then more positive reported P&L windows, '
    'then provider-reported all-time P&L; deterministic address tie-break. Overlapping windows are not independent evidence. '
    'Search covers at most 100 retained candidates, not all public addresses or all traders worldwide.')
LIMITATIONS = [
    'This is an undocumented official-frontend dependency. Availability, schema stability and redistribution permission are not established.',
    'Only this provider’s returned public sample is observed; selection and survivorship bias remain. No worldwide best-trader claim is made.',
    'Display labels are unverified provider labels, not verified identities. An anonymous public address does not identify a real person.',
    'Account value, P&L and volume use provider account units; settlement-currency, fee and funding semantics have not been independently verified.',
    'Raw ROI units are not independently verified. No percentage conversion, success probability or independent skill rank is supplied.',
    'Cash-flow-adjusted returns, account drawdown, external hedges and executable copyability are unavailable from this feed.',
    'Metrics have receipt time only, refresh at most every six hours, and do not establish current positions or a profitable follower entry.',
]
log = logging.getLogger('sentinel')
_INCOMPLETE = object()


def _invalid_constant(value):
    raise ValueError('Non-standard non-finite JSON constant')


class LeaderboardDecoder:
    """Incremental strict root-object/leaderboardRows-array JSON decoder."""
    def __init__(self,max_buffer=MAX_BUFFER_BYTES):
        self.buffer = ''
        self.state = 'root'
        self.key = None
        self.found = False
        self.rows = 0
        self.root_keys = 0
        self.max_buffer = max_buffer
        self.peak_buffer_bytes = 0
        self.decoder = json.JSONDecoder(parse_float=D,parse_constant=_invalid_constant)

    def _take_value(self):
        try:value,end = self.decoder.raw_decode(self.buffer)
        except json.JSONDecodeError:return _INCOMPLETE
        if isinstance(value,(int,float,D)) and not isinstance(value,bool):
            if end==len(self.buffer) or self.buffer[end] not in ',}] \r\n\t':return _INCOMPLETE
        self.buffer = self.buffer[end:]
        return value

    def feed(self,text):
        # Callers supply small decoded chunks. A single oversized row is rejected.
        self.buffer += text
        size = len(self.buffer.encode('utf-8'))
        self.peak_buffer_bytes = max(self.peak_buffer_bytes,size)
        if size>self.max_buffer:raise ValueError('Leaderboard pending JSON exceeds memory bound')
        while True:
            self.buffer = self.buffer.lstrip()
            if not self.buffer:return
            first = self.buffer[0]
            if self.state=='root':
                if first!='{':raise ValueError('Leaderboard root must be an object')
                self.buffer = self.buffer[1:];self.state = 'key'
            elif self.state in ('key','required_key'):
                if first=='}' and self.state=='key':
                    self.buffer = self.buffer[1:];self.state = 'done';continue
                if first!='"':raise ValueError('Invalid leaderboard root member')
                key = self._take_value()
                if key is _INCOMPLETE:return
                self.root_keys += 1
                if self.root_keys>32:raise ValueError('Too many leaderboard root members')
                if key=='leaderboardRows' and self.found:raise ValueError('Duplicate leaderboardRows member')
                self.key = key;self.state = 'colon'
            elif self.state=='colon':
                if first!=':':raise ValueError('Missing leaderboard member separator')
                self.buffer = self.buffer[1:];self.state = 'value'
            elif self.state=='value':
                if self.key=='leaderboardRows':
                    if first!='[':raise ValueError('leaderboardRows must be an array')
                    self.found = True;self.buffer = self.buffer[1:];self.state = 'row'
                else:
                    value = self._take_value()
                    if value is _INCOMPLETE:return
                    self.state = 'root_separator'
            elif self.state in ('row','required_row'):
                if first==']' and self.state=='row':
                    self.buffer = self.buffer[1:];self.state = 'root_separator';continue
                if first!='{':raise ValueError('Leaderboard rows must be objects')
                row = self._take_value()
                if row is _INCOMPLETE:return
                self.rows += 1
                if self.rows>MAX_ROWS:raise ValueError('Leaderboard row limit exceeded')
                self.state = 'row_separator'
                yield row
            elif self.state=='row_separator':
                if first==',':self.buffer = self.buffer[1:];self.state = 'required_row'
                elif first==']':self.buffer = self.buffer[1:];self.state = 'root_separator'
                else:raise ValueError('Invalid leaderboard row separator')
            elif self.state=='root_separator':
                if first==',':self.buffer = self.buffer[1:];self.state = 'required_key'
                elif first=='}':self.buffer = self.buffer[1:];self.state = 'done'
                else:raise ValueError('Invalid leaderboard root separator')
            elif self.state=='done':
                raise ValueError('Trailing data after leaderboard object')

    def finish(self):
        if self.state!='done' or self.buffer.strip() or not self.found:
            raise ValueError('Missing, truncated or malformed leaderboardRows response')


def _number(value,nonnegative=False):
    if value is None:return None
    if isinstance(value,bool) or len(str(value))>100:raise ValueError('Invalid reported metric')
    out = decimal(value)
    if abs(out)>D('1e18') or (out and out.adjusted() < -18):raise ValueError('Reported metric exceeds numeric bounds')
    if nonnegative and out<0:raise ValueError('Negative provider account value or volume')
    # Normalization prevents harmless trailing zero exponents from expanding output.
    return format(out.normalize() if out else D(0),'f')


def _candidate(row):
    address = row.get('ethAddress')
    if not isinstance(address,str) or not ADDRESS.fullmatch(address) or int(address,16)==0:return None
    address = address.lower()
    try:
        account = _number(row.get('accountValue'),True)
        metrics = row.get('windowPerformances')
        if not isinstance(metrics,list):return None
        windows = {}
        for item in metrics:
            if not isinstance(item,list) or len(item)!=2 or not isinstance(item[0],str) or not isinstance(item[1],dict):return None
            name,raw = item
            if name not in WINDOWS:continue
            if name in windows:return None
            window = {'pnl':_number(raw.get('pnl')),'roi_raw':_number(raw.get('roi')),
                'roi_pct':None,'volume':_number(raw.get('vlm'),True)}
            if any(window[k] is not None for k in ('pnl','roi_raw','volume')):windows[name] = window
        if len(windows)<2:return None
    except (ValueError,ArithmeticError):return None
    label = row.get('displayName')
    label = ''.join(c for c in label if not unicodedata.category(c).startswith('C'))[:100].strip() if isinstance(label,str) else ''
    positive = sum(D(w['pnl'])>0 for w in windows.values() if w['pnl'] is not None)
    all_time = windows.get('allTime',{}).get('pnl')
    score = (len(windows),positive,D(all_time) if all_time is not None else D('-1e18'))
    result = {'address':address,'label':label or 'Public candidate '+address[:8]+'…','label_verified':False,
        'account_value':account,'currency':'provider account units','windows':windows,'independent_rank':None,
        'success_probability':None,'success_probability_pct':None,'identity_verified':False,
        'risk_adjusted_status':'insufficient_cash_flow_and_history_evidence',
        'data_completeness':str(len(windows))+' of 4 reported windows available; complete trade history, cash flows, drawdown and copyability are unverified.',
        'selection_metrics':{'reported_windows':len(windows),'positive_reported_pnl_windows':positive},
        'source_at':None}
    return score,result


async def read_candidates(response,max_download=MAX_DOWNLOAD_BYTES,max_buffer=MAX_BUFFER_BYTES):
    """Return compact selected rows and diagnostics without buffering the feed."""
    encoding = response.headers.get('content-encoding','identity').lower()
    if encoding not in ('','identity'):raise ValueError('Unexpected compressed leaderboard response despite identity request')
    length = response.headers.get('content-length')
    if length and int(length)>max_download:raise ValueError('Leaderboard download exceeds byte limit')
    utf8 = codecs.getincrementaldecoder('utf-8')('strict')
    parser = LeaderboardDecoder(max_buffer)
    heap,selected = [],{}
    downloaded = eligible = rejected = duplicates = 0
    async for chunk in response.aiter_bytes(chunk_size=16384):
        downloaded += len(chunk)
        if downloaded>max_download:raise ValueError('Leaderboard download exceeds byte limit')
        for row in parser.feed(utf8.decode(chunk)):
            if parser.rows%200==0:await asyncio.sleep(0)
            item = _candidate(row)
            if item is None:rejected += 1;continue
            eligible += 1
            score,candidate = item
            address = candidate['address']
            if address in selected:
                duplicates += 1
                if score<=selected[address][0]:continue
                selected[address] = (score,candidate)
                heap = [(v[0],a) for a,v in selected.items()];heapq.heapify(heap)
            elif len(selected)<CANDIDATE_LIMIT:
                selected[address] = (score,candidate);heapq.heappush(heap,(score,address))
            elif (score,address)>heap[0]:
                _,old = heapq.heapreplace(heap,(score,address))
                selected.pop(old,None);selected[address] = (score,candidate)
    # Finish UTF-8 separately, then demand a closed array/object and no trailing data.
    for _ in parser.feed(utf8.decode(b'',final=True)):raise ValueError('Unexpected final decoded row')
    parser.finish()
    if not selected:raise ValueError('No eligible multi-window public trader rows')
    ordered = sorted(selected.values(),key=lambda item:(item[0],item[1]['address']),reverse=True)
    return {'traders':[item[1] for item in ordered],'rows_scanned':parser.rows,'eligible_rows':eligible,
        'rejected_rows':rejected,'duplicate_selected_rows':duplicates,'download_bytes':downloaded,
        'peak_buffer_bytes':parser.peak_buffer_bytes,'candidate_limit':CANDIDATE_LIMIT}


class TraderDirectory:
    def __init__(self,store,enabled=True):
        self.store,self.enabled = store,enabled
        self.cache = store.get_state(CACHE_KEY)
        self.error = store.get_state(ERROR_KEY)

    async def refresh(self,client=None,now=None):
        supplied_now = now is not None
        now = time.time() if now is None else now
        if not self.enabled:return self.directory(now=now)
        if self.error and now<self.error.get('retry_at',0):return self.directory(now=now)
        if self.cache and 0<=now-self.cache['received_at']<CACHE_SECONDS:return self.directory(now=now)
        owns = client is None
        client = client or httpx.AsyncClient(timeout=httpx.Timeout(20,connect=10),follow_redirects=False)
        try:
            async with asyncio.timeout(120):
                async with client.stream('GET',SOURCE_URL,headers={'Accept':'application/json','Accept-Encoding':'identity'},
                                         timeout=httpx.Timeout(20,connect=10),follow_redirects=False) as response:
                    response.raise_for_status()
                    data = await read_candidates(response)
            receipt = now if supplied_now else time.time()
            cache = dict(data,version=VERSION,source=SOURCE,source_url=SOURCE_URL,received_at=receipt,source_at=None)
            with self.store.transaction():
                self.store.set_state(CACHE_KEY,cache)
                self.store.set_state(ERROR_KEY,None)
                self.store.put('trader_cohort',{'version':VERSION,'source':SOURCE,'received_at':receipt,'source_at':None,
                    'addresses':[r['address'] for r in data['traders']],'rows_scanned':data['rows_scanned'],
                    'candidates':data['traders'],
                    'selection_basis':SELECTION_BASIS,'note':'Dated discovery cohort; not a validated skill ranking.'},at=receipt)
            self.cache,self.error = cache,None
            log.info('public_trader_directory_refreshed rows=%s candidates=%s bytes=%s peak_buffer=%s',data['rows_scanned'],len(data['traders']),data['download_bytes'],data['peak_buffer_bytes'])
        except asyncio.CancelledError:raise
        except Exception as error:
            failed_at = now if supplied_now else time.time()
            attempts = (self.error or {}).get('attempts',0)+1
            status = error.response.status_code if isinstance(error,httpx.HTTPStatusError) else None
            delay = 3600 if status in (402,403,429) else min(3600,120*2**min(attempts-1,5))
            failure = {'error':type(error).__name__,'http_status':status,'at':failed_at,'attempts':attempts,'retry_at':failed_at+delay,
                'note':'Retained last good data keeps its original receipt time; no substitute performance data.'}
            self.store.set_state(ERROR_KEY,failure);self.error = failure
            log.warning('public_trader_directory_unavailable error=%s status=%s',type(error).__name__,status)
        finally:
            if owns:await client.aclose()
        return self.directory(now=now if supplied_now else time.time())

    def directory(self,q='',page=1,limit=20,now=None):
        now = time.time() if now is None else now
        page,limit = max(1,int(page)),min(50,max(1,int(limit)))
        query = q[:100].strip().casefold()
        received = self.cache.get('received_at') if self.cache and self.enabled else None
        rows = self.cache.get('traders',[]) if self.cache and self.enabled else []
        matched = [r for r in rows if not query or query in (r['address']+' '+r['label']).casefold()]
        status = 'disabled' if not self.enabled else 'unavailable' if not self.cache else 'stale' if self.error or not 0<=now-received<CACHE_SECONDS else 'cached_reported_metrics'
        return {'traders':matched[(page-1)*limit:page*limit],'total':len(matched),'page':page,'limit':limit,
            'source':SOURCE,'source_url':SOURCE_URL,'received_at':received,'source_at':None,'status':status,
            'limitations':list(LIMITATIONS),'selection_basis':SELECTION_BASIS,'error':self.error if self.enabled else None,
            'rows_scanned':self.cache.get('rows_scanned') if self.cache and self.enabled else None,
            'candidate_limit':CANDIDATE_LIMIT,'independent_rank':None,'success_probability':None,
            'experimental':True,'currency':'provider account units'}

    view = directory

    async def run(self):
        while True:
            await self.refresh()
            await asyncio.sleep(60)


PublicLeaders = TraderDirectory

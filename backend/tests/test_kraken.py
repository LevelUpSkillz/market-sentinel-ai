"""Synthetic Kraken contract tests. No real credentials, network, or orders."""
import base64
from dataclasses import FrozenInstanceError
from decimal import localcontext
import json
import unittest
from urllib.parse import parse_qs

import httpx

from sentinel.kraken import KrakenClient, KrakenError, LimitOrder, signature

KEY = 'SYNTHETIC_PUBLIC_KEY'
SECRET = base64.b64encode(b'SYNTHETIC TEST SECRET ONLY').decode()
CID = '6d1b345e-2821-40e2-ad83-4ecb18a06876'
OTHER_CID = '7d1b345e-2821-40e2-ad83-4ecb18a06876'


def order(**changes):
    return LimitOrder(**{'pair':'XBTUSD','side':'buy','volume':'0.00125000','price':'37500.10',
                         'cl_ord_id':CID,'deadline':'2030-01-01T00:00:30Z',**changes})


class KrakenSignatureTests(unittest.TestCase):
    def test_official_documentation_signature_vector(self):
        # The following key is Kraken's public documentation example, NOT a key
        # belonging to any user. This published vector independently checks HMAC.
        secret = 'kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=='
        body = 'nonce=1616492376594&ordertype=limit&pair=XBTUSD&price=37500&type=buy&volume=1.25'
        self.assertEqual(signature('/0/private/AddOrder','1616492376594',body,secret),
            '4/dpxb3iT4tp/ZCVEwSnEsLxx0bqyhLpdfOpc6fn7OR8+UClSV5n9E6aSS8MPtnRfp32bAb0nmbRn6H8ndwLUQ==')

    def test_order_is_immutable_and_excludes_margin_and_arbitrary_fields(self):
        instruction = order()
        with self.assertRaises(FrozenInstanceError):
            instruction.price = '1'
        self.assertEqual(instruction.payload()['timeinforce'],'IOC')
        self.assertNotIn('leverage',instruction.payload())
        with self.assertRaises(TypeError):
            order(leverage='2')
        for change in [{'pair':'https://attacker.test'},{'side':'margin'},{'price':'NaN'},
                       {'price':'+1'},{'price':'1%'},{'volume':'0'},{'volume':0.1},
                       {'cl_ord_id':'reusable-short-id'},{'deadline':'2030-01-01'}]:
            with self.subTest(change=change),self.assertRaises(KrakenError):
                order(**change)


class KrakenContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_signed_requests_use_exact_form_bytes_and_external_nonce(self):
        nonces = iter([1616492376594,1616492376595])
        seen = []
        def handler(request):
            seen.append(request)
            self.assertEqual(request.method,'POST')
            self.assertEqual(str(request.url),'https://api.kraken.com/0/private/GetApiKeyInfo')
            body = request.content.decode()
            nonce = parse_qs(body)['nonce'][0]
            self.assertEqual(request.headers['API-Key'],KEY)
            self.assertEqual(request.headers['API-Sign'],signature(request.url.path,nonce,body,SECRET))
            self.assertNotIn(SECRET,body)
            return httpx.Response(200,json={'error':[],'result':{'apiKey':KEY,'iban':'PRIVATE_IBAN',
                'permissions':['query-funds'],'validUntil':'0','queryFrom':'0','queryTo':'0'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = KrakenClient(KEY,SECRET,lambda:next(nonces),client)
            result = await adapter.key_info()
            await adapter.key_info()
            self.assertNotIn(KEY,repr(adapter))
        self.assertNotIn(KEY,json.dumps(result))
        self.assertNotIn('PRIVATE_IBAN',json.dumps(result))
        self.assertEqual(result['permissions'],['query-funds'])
        self.assertEqual([parse_qs(item.content.decode())['nonce'][0] for item in seen],['1616492376594','1616492376595'])

    async def test_async_durable_nonce_callback_supported(self):
        async def nonce():
            return 42
        def handler(request):
            self.assertEqual(parse_qs(request.content.decode())['nonce'],['42'])
            return httpx.Response(200,json={'error':[],'result':{'permissions':[]}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await KrakenClient(KEY,SECRET,nonce,client).key_info()

    async def test_balance_exactness_hold_deduction_and_credit_exclusion(self):
        body = '{"error":[],"result":{"ZUSD":{"balance":12345678901234567890.123456789012345678,"hold_trade":"0.000000000000000001","credit":"100","credit_used":"20"},"XXBT":{"balance":"1","hold_trade":"2"}}}'
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,text=body))) as client:
            # Exact results must survive even an unrelated caller's low context.
            with localcontext() as context:
                context.prec = 6
                result = await KrakenClient(KEY,SECRET,lambda:1,client).balances()
        self.assertEqual(result['ZUSD']['spot_available'],'12345678901234567890.123456789012345677')
        self.assertEqual(result['ZUSD']['available'],'12345678901234567970.123456789012345677')
        self.assertEqual(result['ZUSD']['credit_used'],'20')
        self.assertEqual(result['XXBT']['spot_available'],'0')

    async def test_balance_missing_hold_nonfinite_or_negative_hold_fails_closed(self):
        for values in [{'balance':'100'},{'balance':'NaN','hold_trade':'0'},
                       {'balance':'100','hold_trade':'-1'},{'balance':'100','hold_trade':'0','credit_used':'NaN'}]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'error':[],'result':{'ZUSD':values}}))) as client:
                with self.assertRaises(KrakenError):
                    await KrakenClient(KEY,SECRET,lambda:1,client).balances()

    async def test_pair_metadata_public_and_account_fee_is_actual_percent(self):
        paths = []
        def handler(request):
            paths.append(request.url.path)
            if request.method=='GET':
                self.assertNotIn('API-Key',request.headers)
                self.assertEqual(request.url.params['pair'],'XBTUSD')
                return httpx.Response(200,json={'error':[],'result':{'XXBTZUSD':{'base':'XXBT','quote':'ZUSD','pair_decimals':1,'lot_decimals':8,'ordermin':'0.0001','costmin':'0.5','status':'online'}}})
            self.assertEqual(parse_qs(request.content.decode())['pair'],['XBTUSD'])
            return httpx.Response(200,json={'error':[],'result':{'fees':{'XXBTZUSD':{'fee':'0.40','nextfee':'0.35'}}}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = KrakenClient(KEY,SECRET,lambda:1,client)
            metadata = await adapter.asset_pairs('XBTUSD')
            fees = await adapter.fees('XBTUSD')
        self.assertEqual(metadata['XXBTZUSD']['ordermin'],'0.0001')
        self.assertEqual(fees,{'fees':{'XXBTZUSD':{'fee':'0.40'}},'fee_units':'percent'})
        self.assertEqual(paths,['/0/public/AssetPairs','/0/private/TradeVolume'])

    async def test_validation_and_live_submission_have_identical_immutable_fields(self):
        calls = []
        nonces = iter([1,2])
        def handler(request):
            fields = {key:values[0] for key,values in parse_qs(request.content.decode()).items()}
            calls.append(fields)
            self.assertEqual(request.url.path,'/0/private/AddOrder')
            return httpx.Response(200,json={'error':[],'result':{} if fields['validate']=='true' else {'txid':['OABC12-DEF345-GHI678']}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = KrakenClient(KEY,SECRET,lambda:next(nonces),client)
            validated = await adapter.validate_limit_order(order())
            submitted = await adapter.submit_limit_order(order())
        self.assertFalse(validated['submitted'])
        self.assertTrue(submitted['submitted'])
        self.assertEqual(submitted['txid'],['OABC12-DEF345-GHI678'])
        for fields in calls:
            self.assertEqual(fields['cl_ord_id'],CID)
            self.assertEqual(fields['price'],'37500.10')
            self.assertEqual(fields['volume'],'0.00125000')
            self.assertEqual(fields['timeinforce'],'IOC')
            self.assertEqual(fields['oflags'],'fciq')
            self.assertNotIn('leverage',fields)
        self.assertEqual({key:value for key,value in calls[0].items() if key not in ('nonce','validate')},
                         {key:value for key,value in calls[1].items() if key not in ('nonce','validate')})

    async def test_pair_eligibility_passes_only_valid_country_code(self):
        calls = []
        def handler(request):
            calls.append(request)
            self.assertEqual(request.url.params['country_code'],'US')
            return httpx.Response(200,json={'error':[],'result':{'XXBTZUSD':{'base':'XXBT','quote':'ZUSD'}}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = KrakenClient(KEY,SECRET,lambda:1,client)
            await adapter.asset_pairs('XBTUSD',country_code='US')
            for code in ['us','USA','U1','US&x=y',True,12]:
                with self.subTest(code=code),self.assertRaises(KrakenError):
                    await adapter.asset_pairs('XBTUSD',country_code=code)
        self.assertEqual(len(calls),1)

    async def test_submission_timeout_is_unknown_and_never_retried(self):
        calls = []
        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout('SYNTHETIC_SECRET_LEAK '+KEY,request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = KrakenClient(KEY,SECRET,lambda:1,client)
            with self.assertRaises(KrakenError) as error:
                await adapter.submit_limit_order(order())
        self.assertEqual(len(calls),1)
        self.assertTrue(error.exception.uncertain)
        self.assertEqual(error.exception.code,'submission_unknown')
        self.assertNotIn(KEY,str(error.exception))
        self.assertNotIn('SYNTHETIC_SECRET_LEAK',str(error.exception))
        self.assertTrue(error.exception.__suppress_context__)

    async def test_read_timeout_has_no_order_submission_claim(self):
        def handler(request):
            raise httpx.ConnectError(KEY,request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(KrakenError) as error:
                await KrakenClient(KEY,SECRET,lambda:1,client).balances()
        self.assertFalse(error.exception.uncertain)
        self.assertEqual(error.exception.code,'unavailable')
        self.assertNotIn(KEY,str(error.exception))

    async def test_gateway_malformed_missing_txid_and_deadline_are_unknown(self):
        responses = [httpx.Response(503,text=KEY),httpx.Response(200,text=KEY),
            httpx.Response(200,json={'error':[],'result':{}}),
            httpx.Response(200,json={'error':['EService:Deadline elapsed '+KEY]}),
            httpx.Response(200,json={'error'…1600 tokens truncated…001','costmin':'0.5'}}
        self.fee = '0.40'
        self.validated = []
        self.submitted = []
        self.country_codes = []
        self.submit_error = None
        self.submit_started = asyncio.Event()
        self.submit_release = None
        self.reconciled = {'orders':{},'complete':True,'absence_proves_failure':False}


class FakeKraken:
    def __init__(self,state,key,secret,nonce):
        self.state,self.nonce = state,nonce
        if key not in (API_KEY,OTHER_KEY) or secret!=API_SECRET:
            raise AssertionError('Synthetic vault did not recover the original test credentials')

    async def key_info(self):
        return deepcopy(self.state.info)

    async def balances(self):
        return deepcopy(self.state.balances)

    async def open_orders(self):
        return deepcopy(self.state.orders)

    async def open_positions(self):
        return deepcopy(self.state.positions)

    async def asset_pairs(self,pair,country_code=None):
        self.state.country_codes.append(country_code)
        return deepcopy(self.state.metadata)

    async def fees(self,pair):
        return {'fees':{key:{'fee':self.state.fee} for key in self.state.metadata},'fee_units':'percent'}

    async def validate_limit_order(self,order):
        self.state.validated.append(order)
        return {'validated':True,'submitted':False,'cl_ord_id':order.cl_ord_id}

    async def submit_limit_order(self,order):
        self.state.submitted.append(order)
        self.state.submit_started.set()
        if self.state.submit_release:
            await self.state.submit_release.wait()
        if self.state.submit_error:
            raise self.state.submit_error
        return {'submitted':True,'txid':['OABC12-DEF345-GHI678'],'cl_ord_id':order.cl_ord_id}

    async def orders_by_client_id(self,client_id,submitted_at):
        return deepcopy(self.state.reconciled)


class KrakenAccountTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = NOW
        self.clock = patch('sentinel.kraken_account.time.time',lambda:self.now)
        self.clock.start()
        self.store = Store('sqlite:///:memory:')
        self.state = FakeState()
        self.settings = SimpleNamespace(kraken_vault_key=Fernet.generate_key().decode(),kraken_live_enabled=True)
        self.books = {}
        self.refresh_book()
        self.account = KrakenAccount(self.store,self.settings,self.books,
                                     lambda key,secret,nonce:FakeKraken(self.state,key,secret,nonce))
        save_profile(self.store,profile(),self.now)

    def tearDown(self):
        self.store.close()
        self.clock.stop()

    def refresh_book(self,at=None):
        book = Book('kraken','BTC-USD')
        book.update([('99','10000')],[('100','10000')],self.now if at is None else at,
                    self.now if at is None else at,snapshot=True)
        book.integrity = 'crc32_verified'
        self.books[('kraken','BTC-USD')] = book

    async def connect(self,**changes):
        return await self.account.connect(**{'api_key':API_KEY,'api_secret':API_SECRET,'country_code':'US',
            'region':'SYNTHETIC REGION','eligibility_confirmed':True,'dedicated_key_confirmed':True,**changes})

    async def preview(self,**changes):
        return await self.account.preview(**{'symbol':'BTC-USD','side':'buy','quantity':'0.1','limit_price':'100',**changes})

    async def test_secrets_encrypted_at_rest_and_absent_from_status_account_and_audit(self):
        status = await self.connect()
        saved = self.store.get_state(CONNECTION_KEY)
        self.assertNotIn(API_KEY,json.dumps(saved))
        self.assertNotIn(API_SECRET,json.dumps(saved))
        plaintext = json.loads(Fernet(self.settings.kraken_vault_key.encode()).decrypt(saved['cipher'].encode()))
        self.assertEqual(plaintext['api_key'],API_KEY)
        self.assertEqual(plaintext['api_secret'],API_SECRET)
        report = await self.account.account()
        exposed = json.dumps([status,report,self.store.list('audit')])
        self.assertNotIn(API_KEY,exposed)
        self.assertNotIn(API_SECRET,exposed)
        self.assertNotIn(saved['cipher'],exposed)
        self.assertFalse(status['withdrawals_enabled'])
        self.assertFalse(status['autonomous_trading'])

    async def test_missing_vault_and_unconfirmed_eligibility_never_persist_credentials(self):
        for changes in [{'eligibility_confirmed':False},{'dedicated_key_confirmed':False},
                        {'country_code':'us'},{'country_code':'USA'},{'region':''}]:
            with self.subTest(changes=changes),self.assertRaises(AccountError):
                await self.connect(**changes)
            self.assertIsNone(self.store.get_state(CONNECTION_KEY))
        self.settings.kraken_vault_key = ''
        with self.assertRaises(AccountError):
            await self.connect()

    async def test_withdrawal_funding_unknown_and_missing_read_permissions_rejected(self):
        for extra in ['withdraw-funds','add-funds','earn-funds','add-withdraw-address','export-data','unknown-future-permission']:
            self.state.info['permissions'] = sorted(TRADE_PERMISSIONS|{extra})
            with self.subTest(extra=extra),self.assertRaises(AccountError):
                await self.connect()
            self.assertIsNone(self.store.get_state(CONNECTION_KEY))
        self.state.info['permissions'] = ['query-funds','modify-trades']
        with self.assertRaises(AccountError):
            await self.connect()

    async def test_read_only_key_cannot_preview_or_submit(self):
        self.state.info['permissions'] = ['query-funds','query-open-trades','query-closed-trades']
        report = await self.connect()
        self.assertFalse(report['order_submission_enabled'])
        with self.assertRaises(AccountError):
            await self.preview()
        self.assertEqual(self.state.submitted,[])

    async def test_revoked_permissions_and_near_expiry_block_approval(self):
        await self.connect()
        preview = await self.preview()
        self.state.info['permissions'].remove('modify-trades')
        with self.assertRaises(AccountError):
            await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.state.info['permissions'] = sorted(TRADE_PERMISSIONS)
        self.state.info['validUntil'] = str(int(self.now+60))
        with self.assertRaises(AccountError):
            await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(self.state.submitted,[])

    async def test_credit_open_orders_margin_and_unknown_holdings_block_orders(self):
        await self.connect()
        cases = [({'ZUSD':{'credit':'1'}},{},{}),({'ZUSD':{'credit_used':'1'}},{},{}),
                 ({},{'SYNTHETIC_OPEN':{'status':'open'}},{}),({},{},{'SYNTHETIC_MARGIN':{'vol':'1'}}),
                 ({'UNKNOWN':{'balance':'1','spot_available':'1','credit':'0','credit_used':'0'}},{},{})]
        original = deepcopy(self.state.balances)
        for balances,orders,positions in cases:
            self.state.balances = deepcopy(original)
            for asset,values in balances.items():
                self.state.balances.setdefault(asset,{}).update(values)
            self.state.orders,self.state.positions = orders,positions
            with self.subTest(balances=balances,orders=orders,positions=positions),self.assertRaises(AccountError):
                await self.preview()
        self.assertEqual(self.state.validated,[])
        self.assertEqual(self.state.submitted,[])

    async def test_declared_cash_position_exposure_pertrade_and_daily_limits(self):
        await self.connect()
        cases = [profile(available_cash_usd='5'),profile(max_position_pct='0.01'),
                 profile(existing_crypto_exposure_usd='2499'),profile(risk_per_trade_pct='0.01'),
                 profile(daily_realized_pnl_usd='-200'),
                 profile(daily_loss_limit_pct='1',daily_realized_pnl_usd='-99')]
        for values in cases:
            save_profile(self.store,values,self.now)
            with self.subTest(profile=values),self.assertRaises(AccountError):
                await self.preview()
        save_profile(self.store,profile(),self.now)
        with self.assertRaises(AccountError):
            await self.preview(quantity='5.01')
        self.assertEqual(self.state.validated,[])

    async def test_verified_cash_and_asset_availability_cannot_use_held_amounts(self):
        await self.connect()
        self.state.balances['ZUSD']['spot_available'] = '10'
        with self.assertRaises(AccountError):
            await self.preview()
        self.state.balances = {'ZUSD':{'balance':'1000','spot_available':'1000','credit':'0','credit_used':'0'},
                              'XXBT':{'balance':'1','spot_available':'0.05','credit':'0','credit_used':'0'}}
        with self.assertRaises(AccountError):
            await self.preview(side='sell',limit_price='99')
        self.assertEqual(self.state.submitted,[])

    async def test_stale_or_bad_integrity_books_cannot_preview_or_approve(self):
        await self.connect()
        self.books[('kraken','BTC-USD')].integrity = 'disconnected'
        with self.assertRaises(AccountError):
            await self.preview()
        self.refresh_book()
        preview = await self.preview()
        self.now += 6
        with self.assertRaises(AccountError):
            await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(self.state.submitted,[])

    async def test_actual_pair_identity_tick_lot_minimum_and_fee_required(self):
        await self.connect()
        original = deepcopy(self.state.metadata)
        for changes in [{'base':'XETH'},{'quote':'ZEUR'},{'status':'post_only'},
                        {'tick_size':'0.03'},{'lot_decimals':0},{'ordermin':'1'},{'costmin':'1000'}]:
            self.state.metadata = deepcopy(original)
            self.state.metadata['XXBTZUSD'].update(changes)
            with self.subTest(changes=changes),self.assertRaises(AccountError):
                await self.preview()
        self.state.metadata = deepcopy(original)
        self.state.fee = '999'
        with self.assertRaises(AccountError):
            await self.preview()
        self.assertTrue(all(code=='US' for code in self.state.country_codes))
        self.assertEqual(self.state.submitted,[])

    async def test_preview_is_not_submission_and_requires_exact_per_order_phrase(self):
        await self.connect()
        preview = await self.preview()
        self.assertEqual(preview['status'],'validated')
        self.assertEqual(self.state.submitted,[])
        for phrase in ['',True,'approve','place this real order','PLACE THIS REAL ORDER ']:
            with self.subTest(phrase=phrase),self.assertRaises(AccountError):
                await self.account.approve(preview['id'],phrase)
        result = await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(result['status'],'submitted')
        self.assertEqual(self.state.submitted,self.state.validated)
        self.assertEqual(self.state.submitted[0].cl_ord_id,preview['cl_ord_id'])
        self.assertEqual(self.state.submitted[0].price,preview['limit_price'])
        self.assertEqual(self.state.submitted[0].volume,preview['quantity'])
        self.assertEqual(self.store.list('paper'),[])

    async def test_expiry_changed_profile_and_emergency_stop_require_new_review(self):
        await self.connect()
        preview = await self.preview()
        self.now += 31
        with self.assertRaises(AccountError):
            await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.now = NOW
        self.refresh_book()
        preview = await self.preview()
        self.now += 1
        save_profile(self.store,profile(available_cash_usd='9000'),self.now)
        with self.assertRaises(AccountError):
            await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.refresh_book()
        preview = await self.preview()
        self.store.set_state('control',{'stopped':True})
        with self.assertRaises(AccountError):
            await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(self.state.submitted,[])

    async def test_duplicate_approval_race_sends_once(self):
        await self.connect()
        preview = await self.preview()
        self.state.submit_release = asyncio.Event()
        first = asyncio.create_task(self.account.approve(preview['id'],'PLACE THIS REAL ORDER'))
        await asyncio.wait_for(self.state.submit_started.wait(),1)
        second = asyncio.create_task(self.account.approve(preview['id'],'PLACE THIS REAL ORDER'))
        await asyncio.sleep(0)
        self.state.submit_release.set()
        results = await asyncio.wait_for(asyncio.gather(first,second),1)
        self.assertEqual(len(self.state.submitted),1)
        self.assertTrue(all(item['status'] in ('submitting','submitted') for item in results))

    async def test_unknown_timeout_never_resends_and_empty_reconciliation_stays_blocked(self):
        await self.connect()
        preview = await self.preview()
        self.state.submit_error = KrakenError('submission_unknown','SYNTHETIC timeout',uncertain=True)
        result = await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(result['status'],'unknown')
        self.assertEqual((await self.account.approve(preview['id'],'PLACE THIS REAL ORDER'))['status'],'unknown')
        self.assertEqual((await self.account.reconcile(preview['id']))['status'],'unknown')
        self.assertEqual(self.store.get_state('kraken_live_active'),preview['id'])
        self.assertEqual(len(self.state.submitted),1)

    async def test_partial_reconciliation_does_not_clear_active_order(self):
        await self.connect()
        preview = await self.preview()
        await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.state.reconciled = {'orders':{'SYNTHETIC_ORDER':{'status':'closed','cl_ord_id':preview['id']}},
                                 'complete':False,'absence_proves_failure':False}
        result = await self.account.reconcile(preview['id'])
        self.assertNotEqual(result['status'],'resolved')
        self.assertEqual(self.store.get_state('kraken_live_active'),preview['id'])
        self.state.reconciled['complete'] = True
        result = await self.account.reconcile(preview['id'])
        self.assertEqual(result['status'],'resolved')
        self.assertIsNone(self.store.get_state('kraken_live_active'))
        self.assertEqual(len(self.state.submitted),1)

    async def test_restored_validated_intent_never_submits_even_with_fresh_state(self):
        await self.connect()
        preview = await self.preview()
        saved = self.store.get('real_order',preview['id'])
        saved.update(restored_execution_disabled=True,execution_enabled=False)
        self.store.replace(preview['id'],saved)
        try:
            await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        except AccountError:
            pass
        self.assertEqual(self.state.submitted,[])

    async def test_fee_increase_between_preview_and_approval_requires_new_review(self):
        await self.connect()
        preview = await self.preview()
        self.state.fee = '0.50'
        with self.assertRaises(AccountError):
            await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(self.state.submitted,[])

    async def test_dynamic_kraken_altcoin_uses_verified_identity_country_and_fresh_book(self):
        await self.connect()
        book = Book('kraken','LINK-USD')
        book.update([('99','10000')],[('100','10000')],self.now,self.now,snapshot=True)
        book.integrity = 'crc32_verified'
        self.books[('kraken','LINK-USD')] = book
        self.state.metadata = {'LINKUSD':{'base':'LINK','quote':'ZUSD','wsname':'LINK/USD','altname':'LINKUSD',
            'status':'online','pair_decimals':2,'lot_decimals':8,'tick_size':'0.01','ordermin':'0.01','costmin':'0.5'}}
        preview = await self.preview(symbol='LINK-USD')
        self.assertEqual(preview['symbol'],'LINK-USD')
        self.assertEqual(preview['pair'],'LINKUSD')
        result = await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        self.assertEqual(result['status'],'submitted')
        self.assertEqual(self.state.submitted[0].pair,'LINKUSD')
        self.assertTrue(all(code=='US' for code in self.state.country_codes))

    async def test_unresolved_order_allows_credential_removal_and_same_key_reconciliation(self):
        await self.connect()
        preview = await self.preview()
        await self.account.approve(preview['id'],'PLACE THIS REAL ORDER')
        original = self.store.get_state(CONNECTION_KEY)
        disconnected = self.account.disconnect()
        saved = self.store.get_state(CONNECTION_KEY)
        self.assertFalse(saved.get('cipher'))
        self.assertEqual(saved['id'],original['id'])
        self.assertEqual(saved['fingerprint'],original['fingerprint'])
        self.assertFalse(disconnected['connected'])
        self.assertEqual(self.store.get_state('kraken_live_active'),preview['id'])
        with self.assertRaises(AccountError):
            await self.connect(api_key=OTHER_KEY)
        reconnected = await self.connect()
        self.assertTrue(reconnected['connected'])
        self.assertEqual(self.store.get_state(CONNECTION_KEY)['id'],original['id'])
        self.state.reconciled = {'orders':{'SYNTHETIC_ORDER':{'status':'closed','cl_ord_id':preview['id']}},
                                 'complete':True,'absence_proves_failure':False}
        self.assertEqual((await self.account.reconcile(preview['id']))['status'],'resolved')
        self.assertEqual(len(self.state.submitted),1)

    async def test_restricted_order_history_query_ranges_block_linking(self):
        for field in ('queryFrom','queryTo'):
            self.state.info[field] = str(int(self.now-100))
            with self.subTest(field=field),self.assertRaises(AccountError):
                await self.connect()
            self.state.info[field] = '0'
        self.assertIsNone(self.store.get_state(CONNECTION_KEY))

    async def test_nonce_is_monotonic_across_account_recreation_and_clock_stall(self):
        with patch('sentinel.kraken_account.time.time_ns',return_value=1800000000000000000):
            first = self.account._nonce(API_KEY)
            second = self.account._nonce(API_KEY)
            recreated = KrakenAccount(self.store,self.settings,self.books)
            third = recreated._nonce(API_KEY)
        self.assertLess(first,second)
        self.assertLess(second,third)

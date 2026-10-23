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
        responses = [
            httpx.Response(503, text=KEY),
            httpx.Response(200, text=KEY),
            httpx.Response(200, json={'error': [], 'result': {}}),
            httpx.Response(200, json={'error': ['EService:Deadline elapsed ' + KEY]}),
        ]
        for response in responses:
            with self.subTest(response=response.status_code):
                calls = []
                def handler(request):
                    calls.append(request)
                    return response
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    with self.assertRaises(KrakenError) as error:
                        await KrakenClient(KEY, SECRET, lambda: 1, client).submit_limit_order(order())
                self.assertEqual(len(calls), 1)
                self.assertTrue(error.exception.uncertain)
                self.assertNotIn(KEY, str(error.exception))


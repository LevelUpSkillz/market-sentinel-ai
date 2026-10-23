"""Broad WebSocket quote collection; distinct from validated execution books."""
import asyncio
from decimal import Decimal as D
import json
import logging
import time
from websockets.asyncio.client import connect

log = logging.getLogger('sentinel')


def ticker_subscriptions(symbols,method='subscribe'):
    symbols = sorted(symbols)
    return [{'method':method,'params':{'channel':'ticker','symbol':symbols[i:i+50],
        'event_trigger':'trades','snapshot':True}} for i in range(0,len(symbols),50)]


async def directory_stream(catalogue,provider):
    url = 'wss://ws.kraken.com/v2' if provider=='kraken' else 'wss://api.hyperliquid.xyz/ws'
    catalogue.sessions[provider] = {'state':'connecting','received_at':None}
    subscriptions = set()
    try:
        async with connect(url,open_timeout=15,ping_interval=20,ping_timeout=20,max_size=8*1024*1024,max_queue=128) as socket:
            first = {'method':'subscribe','params':{'channel':'instrument','include_tokenized_assets':False}} if provider=='kraken' else {'method':'subscribe','subscription':{'type':'allMids'}}
            await socket.send(json.dumps(first))
            last_data = time.monotonic()
            logged = False
            while True:
                message = json.loads(await asyncio.wait_for(socket.recv(),40),parse_float=D)
                now = time.time()
                if message.get('success') is False or message.get('channel')=='error':
                    raise ValueError('Directory subscription rejected')
                channel = message.get('channel')
                if provider=='kraken' and channel=='instrument':
                    desired = catalogue.kraken_instruments(message['data'],now,message.get('type')=='snapshot')
                    for request in ticker_subscriptions(subscriptions-desired,'unsubscribe'):
                        request['params'].pop('snapshot',None)
                        await socket.send(json.dumps(request))
                        await asyncio.sleep(.2)
                    for request in ticker_subscriptions(desired-subscriptions):
                        await socket.send(json.dumps(request))
                        await asyncio.sleep(.2)
                    subscriptions = desired
                    last_data = time.monotonic()
                elif provider=='kraken' and channel=='ticker':
                    for row in message.get('data',[]):catalogue.kraken_tick(row,now)
                    last_data = time.monotonic()
                elif provider=='hyperliquid' and channel=='allMids':
                    catalogue.hyperliquid_mids(message['data']['mids'],now)
                    last_data = time.monotonic()
                if channel in ('ticker','allMids'):
                    catalogue.sessions[provider] = {'state':'connected','received_at':now}
                    if not logged:
                        log.info('directory_quotes_observed provider=%s markets=%s',provider,len(catalogue.venues.get(provider,{})))
                        logged = True
                if time.monotonic()-last_data>90:raise TimeoutError('Directory data stalled')
    except asyncio.CancelledError:
        catalogue.disconnected(provider,'stopped')
        raise
    except Exception as error:
        catalogue.disconnected(provider,type(error).__name__)
        raise  # Runtime supervisor reconnects with bounded exponential backoff.

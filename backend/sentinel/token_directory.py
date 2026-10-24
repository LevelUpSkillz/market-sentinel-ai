"""Plain token browsing from observed data. No forecasts or cross-source identity guesses."""
from decimal import Decimal
import time

NAMES={'BTC':'Bitcoin','XBT':'Bitcoin','ETH':'Ethereum','SOL':'Solana','XRP':'XRP','ADA':'Cardano','DOGE':'Dogecoin','AVAX':'Avalanche','DOT':'Polkadot','LINK':'Chainlink','LTC':'Litecoin','BCH':'Bitcoin Cash','ATOM':'Cosmos','UNI':'Uniswap','AAVE':'Aave','XLM':'Stellar','ETC':'Ethereum Classic','ALGO':'Algorand','FIL':'Filecoin','NEAR':'NEAR Protocol','USDT':'Tether','USDC':'USD Coin','DAI':'Dai','TRX':'TRON','SHIB':'Shiba Inu','SUI':'Sui','APT':'Aptos','ARB':'Arbitrum','OP':'Optimism','PEPE':'Pepe','WIF':'dogwifhat','BONK':'Bonk','0G':'0G'}
SECTIONS={'all','new','gainers','decliners','best','worst','predicted-best','predicted-worst'}

def browse(catalogue,books,q='',section='all',page=1,limit=25,now=None):
    now=time.time() if now is None else now
    if section not in SECTIONS:raise ValueError('Unknown token section')
    result={'items':[],'page':page,'limit':limit,'total':0,'as_of':now,'section':section,
        'basis':'Reported 24-hour price change. This is not a forecast or a recommendation.',
        'status':'available','source':'kraken','currency':'USD'}
    if section.startswith('predicted-'):
        return dict(result,status='unavailable',basis='No validated forecast available. Observed price changes are not predictions.')
    rows=[]
    if section=='new':
        result.update(source='coinpaprika',basis='Tokens marked new by the source catalogue. This does not establish a new Kraken listing or launch date.')
        if now-catalogue.assets.get('at',0)>6*3600+60:
            return dict(result,status='unavailable',basis='Fresh listing information is unavailable.')
        source=[r for r in catalogue.assets['items'].values() if r.get('active') and r.get('is_new') is True]
    else:
        source=[r for r in catalogue.venues.get('kraken',{}).values() if r.get('active') and r.get('instrument')=='spot' and r.get('quote_currency')=='USD'] if 'kraken' in catalogue.providers else []
    for row in source:
        label=row['name'] if row['source']=='coinpaprika' else NAMES.get(row['symbol'],row['symbol'])
        if q.strip().casefold() not in (label+' '+row['symbol']).casefold():continue
        quote=catalogue.quote_view(row,now)
        move=quote.get('change_24h_pct')
        current=quote.get('status') in {'live','streaming','delayed'}
        if section in {'gainers','decliners','best','worst'}:
            if move is None or not current:continue
            change=Decimal(move)
            if section in {'gainers','best'} and change<=0 or section in {'decliners','worst'} and change>=0:continue
        rows.append({'id':row['id'],'name':label,'symbol':row['symbol'],'provider':row['source'],
            'chart_symbol':row.get('watch_symbol'),'currency':'USD','quote':quote,
            'detailed':(row['source'],row.get('watch_symbol')) in books})
    if section in {'gainers','decliners','best','worst'}:
        rows.sort(key=lambda r:Decimal(r['quote']['change_24h_pct']),reverse=section in {'gainers','best'})
        if section in {'best','worst'}:rows=rows[:10]
    else:rows.sort(key=lambda r:(r['name'].casefold(),r['id']))
    result.update(items=rows[(page-1)*limit:page*limit],total=len(rows))
    if not rows:result['status']='no_observations'
    return result

"""Disposable PostgreSQL: overlapping Google callbacks consume PKCE exactly once."""
import asyncio
import os
import uuid
import httpx
import unittest
from sentinel.storage import Store
from sentinel.config import Settings
from sentinel.google_auth import GoogleAuth,research_session

@unittest.skipUnless(os.getenv('TEST_POSTGRES_URL'),'Separate test PostgreSQL required')
class GooglePostgresTests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  from psycopg.conninfo import conninfo_to_dict
  url=os.environ['TEST_POSTGRES_URL']
  if not conninfo_to_dict(url).get('dbname','').startswith('test_'):raise RuntimeError('Disposable test database required')
  self.first,self.second=Store(url),Store(url);self.schema='test_google_'+uuid.uuid4().hex
  self.first.execute('CREATE SCHEMA '+self.schema)
  for store in [self.first,self.second]:store.execute('SET search_path TO '+self.schema+',public')
  for table in ['schema_version','state','records','rate_limits']:self.first.execute('CREATE TABLE '+self.schema+'.'+table+' (LIKE public.'+table+' INCLUDING ALL)')
 def tearDown(self):
  self.first.execute('DROP SCHEMA '+self.schema+' CASCADE');self.first.close();self.second.close()
 async def test_two_connections_cannot_exchange_the_same_flow_twice(self):
  settings=Settings(environment='test',session_secret='SYNTHETIC_PG_SECRET_'*4,owner_email='owner@example.test',research_origin='https://research.example.test',supabase_auth_url='https://synthetic.supabase.co',supabase_publishable_key='SYNTHETIC_PUBLIC',google_owner_enabled=True)
  calls=[]
  def handler(request):
   calls.append(request.url.path)
   if request.url.path.endswith('/token'):return httpx.Response(200,json={'access_token':'SYNTHETIC_NOT_STORED'})
   return httpx.Response(200,json={'id':'SYNTHETIC_OWNER','email':settings.owner_email,'email_confirmed_at':'yes','identities':[{'provider':'google','identity_data':{'email':settings.owner_email,'email_verified':True}}]})
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as remote:
   one,two=GoogleAuth(self.first,settings,remote),GoogleAuth(self.second,settings,remote);_,nonce=one.start()
   results=await asyncio.gather(one.finish('SYNTHETIC_CODE',nonce),two.finish('SYNTHETIC_CODE',nonce),return_exceptions=True)
  self.assertEqual(sum(isinstance(r,str) for r in results),1);self.assertEqual(sum(isinstance(r,ValueError) for r in results),1)
  token=next(r for r in results if isinstance(r,str));self.assertEqual(research_session(token,settings.session_secret,'test')['role'],'owner')
  self.assertEqual(len(calls),2)

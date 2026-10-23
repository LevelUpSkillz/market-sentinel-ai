"""Synthetic causal radar checks. Fixtures are never seeded into production."""
import copy
import unittest
from decimal import Decimal as D
from sentinel.catalogue import Catalogue
from sentinel.models import Book
from sentinel.radar import Radar,VERSION
from sentinel.storage import Store

NOW = 1800000000
KEY = 'kraken:TEST/USD'


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.store = Store('sqlite:///:memory:')
        self.catalogue = Catalogue(self.store,('kraken',))
        self.catalogue.kraken_instruments({'pairs':[{'base':'TEST','quote':'USD','symbol':'TEST/USD','status':'online'}]},NOW,True)
        self.catalogue.sessions['kraken'] = {'state':'connected','received_at':NOW}
        self.radar = Radar(self.store)
    def tearDown(self):self.store.close()

    def quote(self,at,price):
        self.catalogue.quotes[KEY] = {'price':str(price),'source_at':at,'received_at':at,'valid':True,'transport':'websocket','timestamp_basis':'provider_event'}

    def book(self,at,price='100.4',quantity='100'):
        b = Book('kraken','TEST-USD')
        price = D(price)
        b.update([(str(price-D('.01')),quantity)],[(str(price+D('.01')),quantity)],at,at,snapshot=True)
        b.integrity = 'crc32_verified'
        return b

    def warm(self,radar=None):
        radar = radar or self.radar
        for seconds in range(0,301,5):
            self.quote(NOW+seconds,D(100)+D(seconds)/1000)
            result = radar.tick(self.catalogue,{},now=NOW+seconds)
        return result

    def trigger(self):
        self.warm()
        self.quote(NOW+305,'100.4')
        books = {('kraken','TEST-USD'):self.book(NOW+305)}
        return self.radar.tick(self.catalogue,books,now=NOW+305),books

    def test_no_history_or_missing_windows_never_invent_setup(self):
        self.quote(NOW,'100')
        first = self.radar.tick(self.catalogue,{},now=NOW)
        self.assertEqual(first['setups'],[])
        self.assertEqual(first['coverage']['warming_up'],1)
        for seconds in range(30,601,30):
            self.quote(NOW+seconds,100+seconds/1000)
            result = self.radar.tick(self.catalogue,{},now=NOW+seconds)
        self.assertEqual(result['setups'],[])
        self.assertEqual(result['coverage']['ready'],0)

    def test_real_observation_bins_and_missing_depth_do_not_greenlight_entry(self):
        result = self.warm()
        self.assertEqual(result['coverage']['ready'],1)
        setup = result['setups'][0]
        self.assertEqual(setup['decision'],'WAIT')
        self.assertEqual(setup['state'],'needs_depth')
        self.assertIsNone(setup['entry_vwap'])
        self.assertIsNone(setup['success_probability_pct'])
        self.assertEqual(setup['validation_status'],'unvalidated')
        self.assertEqual(len(setup['baseline']['bins']),10)
        self.assertEqual(setup['baseline']['end_at'],NOW+300)
        self.assertEqual(setup['baseline']['high'],'100.295')
        self.assertEqual(setup['baseline']['low'],'100')
        self.assertLess(max(r['last_at'] for r in setup['baseline']['bins']),NOW+300)

    def test_future_prices_cannot_change_a_saved_baseline_or_levels(self):
        before = copy.deepcopy(self.warm()['setups'][0])
        self.quote(NOW+305,'100.4')
        after = self.radar.tick(self.catalogue,{},now=NOW+305)['setups'][0]
        for field in ('id','baseline','entry_trigger','entry_limit','stop','target','created_at','expires_at'):
            self.assertEqual(before[field],after[field])
        self.assertEqual(after['triggered_at'],NOW+305)

    def test_trigger_and_fresh_depth_can_only_approve_paper_eligibility(self):
        account = self.store.get_state('account')
        result,books = self.trigger()
        setup = result['setups'][0]
        self.assertEqual(setup['decision'],'GO')
        self.assertEqual(setup['state'],'paper_ready')
        self.assertEqual(setup['mode'],'paper_only')
        self.assertGreaterEqual(D(setup['risk_reward']),D(2))
        self.assertGreater(D(setup['maximum_modeled_loss']),D(0))
        self.assertEqual(setup['entry_deadline'],NOW+335)
        self.assertIsNone(setup['success_probability_pct'])
        self.assertEqual(self.store.get_state('account'),account)
        self.assertEqual(self.store.list('paper'),[])
        record = self.store.get('radar_signal',setup['id'])
        self.assertEqual(record['decision'],'GO')
        self.assertEqual(record['snapshot']['provider'],'kraken')
        self.assertEqual(record['strategy_version'],VERSION)

    def test_first_trigger_deadline_is_not_extended_by_new_quotes(self):
        result,books = self.trigger()
        original_deadline = result['setups'][0]['entry_deadline']
        for seconds in range(310,336,5):
            self.quote(NOW+seconds,'100.4')
            books[('kraken','TEST-USD')] = self.book(NOW+seconds)
            result = self.radar.tick(self.catalogue,books,now=NOW+seconds)
        setup = result['setups'][0]
        self.assertEqual(setup['entry_deadline'],original_deadline)
        self.assertEqual(setup['decision'],'NO-GO')
        self.assertEqual(setup['state'],'expired')

    def test_stale_stop_and_entry_chasing_are_rechecked_between_ticks(self):
        _,books = self.trigger()
        stale = self.radar.snapshot(books,now=NOW+311)['setups'][0]
        self.assertEqual(stale['decision'],'NO-GO')
        self.assertEqual(stale['state'],'stale')
        # Even without a new radar tick, current depth can invalidate a past GO.
        books[('kraken','TEST-USD')] = self.book(NOW+306,'101')
        chased = self.radar.snapshot(books,now=NOW+306)['setups'][0]
        self.assertEqual(chased['decision'],'NO-GO')
        self.assertIn('entry exceeds',chased['next_action'])
        self.store.set_state('control',{'stopped':True})
        stopped = self.radar.snapshot(books,now=NOW+306)['setups'][0]
        self.assertEqual(stopped['decision'],'NO-GO')
        self.assertIn('Emergency stop',stopped['next_action'])

    def test_cash_exposure_daily_loss_and_liquidity_rejections_apply(self):
        _,books = self.trigger()
        account = self.store.get_state('account')
        self.store.set_state('account',dict(account,cash='1'))
        poor = self.radar.snapshot(books,now=NOW+305)['setups'][0]
        self.assertEqual(poor['decision'],'NO-GO')
        self.assertTrue(any('cash' in r for r in poor['reasons']))
        self.store.set_state('account',account)
        books[('kraken','TEST-USD')] = self.book(NOW+305,quantity='.00001')
        shallow = self.radar.snapshot(books,now=NOW+305)['setups'][0]
        self.assertEqual(shallow['decision'],'NO-GO')
        self.assertTrue(any('liquidity' in r for r in shallow['reasons']))
        books[('kraken','TEST-USD')] = self.book(NOW+305)
        self.store.put('paper',{'status':'closed','net_pnl':'-200','closed_at':NOW+304})
        loss_stopped = self.radar.snapshot(books,now=NOW+305)['setups'][0]
        self.assertEqual(loss_stopped['decision'],'NO-GO')
        self.assertTrue(any('Daily' in r for r in loss_stopped['reasons']))

    def test_gap_and_restart_need_new_baselines_and_repeated_event_does_not_warm(self):
        self.warm()
        self.quote(NOW+320,'100.32')
        gap = self.radar.tick(self.catalogue,{},now=NOW+320)
        self.assertEqual(gap['coverage']['ready'],0)
        restarted = Radar(self.store)
        for seconds in range(320,326):
            result = restarted.tick(self.catalogue,{},now=NOW+seconds)
        self.assertEqual(result['coverage']['ready'],0)
        self.assertEqual(result['setups'],[])
        series = restarted.series[KEY]
        self.assertEqual(sum(b['points'] for b in series['bins'].values()),1)

    def test_triggered_setup_cannot_regain_go_after_a_source_gap(self):
        result,books = self.trigger()
        self.assertEqual(result['setups'][0]['decision'],'GO')
        # Still inside its original 30-second trigger deadline, but continuity
        # was lost long enough that the old setup could have crossed invalidation.
        self.quote(NOW+325,'100.4')
        books[('kraken','TEST-USD')] = self.book(NOW+325)
        resumed = self.radar.tick(self.catalogue,books,now=NOW+325)
        self.assertEqual(resumed['coverage']['ready'],0)
        self.assertEqual(resumed['setups'][0]['decision'],'NO-GO')
        self.assertEqual(resumed['setups'][0]['state'],'invalidated')
        self.assertTrue(any('data gap' in reason for reason in resumed['setups'][0]['reasons']))
        self.assertEqual(self.radar.snapshot(books,now=NOW+325)['setups'][0]['decision'],'NO-GO')

    def test_current_exit_liquidity_and_spread_are_included_in_review(self):
        result,books = self.trigger()
        original_cost = D(result['setups'][0]['estimated_round_trip_cost_bps'])
        book = books[('kraken','TEST-USD')]
        book.update([('100.2','100')],[('100.41','100')],NOW+305,NOW+305,snapshot=True)
        wider = self.radar.snapshot(books,now=NOW+305)['setups'][0]
        self.assertGreater(D(wider['estimated_round_trip_cost_bps']),original_cost)
        book.update([('100.39','.0001')],[('100.41','100')],NOW+305,NOW+305,snapshot=True)
        thin_exit = self.radar.snapshot(books,now=NOW+305)['setups'][0]
        self.assertEqual(thin_exit['decision'],'NO-GO')
        self.assertIn('exit liquidity',thin_exit['next_action'])

    def test_other_sources_future_or_invalid_quotes_cannot_populate_baseline(self):
        self.quote(NOW,'100')
        quote = self.catalogue.quotes[KEY]
        for changes in [{'source_at':NOW+1},{'timestamp_basis':'receipt_only'},{'transport':'rest'},{'valid':False}]:
            before = dict(quote)
            quote.update(changes)
            result = self.radar.tick(self.catalogue,{},now=NOW)
            self.assertEqual(result['coverage']['observed'],0)
            quote.clear();quote.update(before)
        self.catalogue.venues['kraken'][KEY]['quote_currency']='USDC'
        self.assertEqual(self.radar.tick(self.catalogue,{},now=NOW)['coverage']['universe'],0)

    def test_saved_research_records_are_not_duplicated_on_every_tick(self):
        self.warm()
        self.assertEqual(len(self.store.list('radar_signal')),1)
        self.quote(NOW+305,'100.4')
        for _ in range(20):self.radar.tick(self.catalogue,{},now=NOW+305)
        self.assertEqual(len(self.store.list('radar_signal')),1)
        self.assertLessEqual(len(self.store.list('radar_signal')[0]['transitions']),20)

    def test_first_eligible_book_and_risk_inputs_survive_later_rejection(self):
        result,books = self.trigger()
        identity = result['setups'][0]['id']
        original = self.store.get('radar_signal',identity)['first_paper_ready']
        self.assertEqual(original['source_at'],NOW+305)
        self.assertEqual(original['risk_inputs']['cash'],'10000')
        self.store.set_state('account',{'cash':'1','initial_cash':'10000','realized_pnl':'0'})
        self.quote(NOW+310,'100.4')
        books[('kraken','TEST-USD')] = self.book(NOW+310)
        rejected = self.radar.tick(self.catalogue,books,now=NOW+310)['setups'][0]
        self.assertEqual(rejected['decision'],'NO-GO')
        record = self.store.get('radar_signal',identity)
        self.assertEqual(record['first_paper_ready'],original)
        self.assertEqual(record['decision'],'NO-GO')
        self.assertEqual(self.store.list('paper'),[])

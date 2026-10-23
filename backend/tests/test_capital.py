"""SYNTHETIC real-capital declarations and books; no connected account or orders."""
from decimal import Decimal as D
import unittest
from sentinel.capital import save_profile, get_profile, evaluate_real_plan
from sentinel.models import Book
from sentinel.storage import Store

NOW = 1800000000.0


def inputs(**changes):
    body = {'capital_usd':'10000', 'available_cash_usd':'10000', 'existing_crypto_exposure_usd':'0',
        'daily_realized_pnl_usd':'0', 'risk_per_trade_pct':'0.5', 'max_position_pct':'10',
        'max_crypto_exposure_pct':'25', 'daily_loss_limit_pct':'2'}
    body.update(changes)
    return body


def book(*, now=NOW, asks=None):
    b = Book('kraken', 'TEST-USD')
    b.update([('99','1000')], asks or [('100','1000')], now, now, snapshot=True)
    return b


class CapitalTests(unittest.TestCase):
    def setUp(self):self.store = Store('sqlite:///:memory:')
    def tearDown(self):self.store.close()

    def test_profile_is_persistent_unverified_and_isolated_from_simulated_money(self):
        account = self.store.get_state('account')
        profile = save_profile(self.store, inputs(), NOW)
        self.assertEqual(profile, get_profile(self.store, NOW))
        self.assertEqual(profile['currency'], 'USD')
        self.assertEqual(profile['source'], 'USER_DECLARED_UNVERIFIED')
        self.assertFalse(profile['execution_enabled'])
        self.assertFalse(profile['stale'])
        self.assertEqual(self.store.get_state('account'), account)
        self.assertEqual(self.store.list('paper'), [])
        self.assertEqual(self.store.list('audit')[0]['action'], 'real_capital.update')

    def test_missing_nonfinite_out_of_range_and_unexpected_credentials_rejected(self):
        cases = [inputs(capital_usd='0'), inputs(capital_usd='10000001'), inputs(available_cash_usd='10001'),
            inputs(existing_crypto_exposure_usd='-1'), inputs(risk_per_trade_pct='2.01'),
            inputs(max_position_pct='25.1'), inputs(max_crypto_exposure_pct='100.1'),
            inputs(daily_loss_limit_pct='10.1'), inputs(risk_per_trade_pct='0'),
            inputs(capital_usd='NaN'), inputs(daily_realized_pnl_usd='Infinity'),
            inputs(capital_usd='1e-99999999'), inputs(daily_realized_pnl_usd='0e-99999999'),
            inputs(capital_usd=10000), inputs(currency='CAD'), inputs(exchange_private_key='SYNTHETIC')]
        incomplete = inputs(); incomplete.pop('available_cash_usd'); cases.append(incomplete)
        for body in cases:
            with self.subTest(body=body):
                with self.assertRaises(ValueError):save_profile(self.store, body, NOW)
        self.assertIsNone(get_profile(self.store, NOW))
        self.assertEqual(self.store.list('audit'), [])

    def test_extreme_price_exponents_are_rejected_without_expanding_output(self):
        save_profile(self.store, inputs(), NOW)
        for stop,target in [('1e-99999999','110'), ('98','1e99999999'), ('0e-99999999','110')]:
            with self.assertRaises(ValueError):evaluate_real_plan(self.store, book(), stop, target, NOW)

    def test_stale_after_24_hours_or_utc_day_change_and_future_confirmation(self):
        start = (int(NOW)//86400)*86400+86399
        save_profile(self.store, inputs(), start)
        self.assertFalse(get_profile(self.store, start)['stale'])
        self.assertTrue(get_profile(self.store, start+2)['stale'])
        self.assertTrue(any('UTC day' in r for r in get_profile(self.store, start+2)['stale_reasons']))
        self.assertTrue(get_profile(self.store, start+86400)['stale'])
        self.assertTrue(get_profile(self.store, start-10)['stale'])

    def test_passing_risk_size_is_not_go_or_execution_permission(self):
        account = self.store.get_state('account')
        save_profile(self.store, inputs(), NOW)
        plan = evaluate_real_plan(self.store, book(), '98', '110', NOW)
        self.assertEqual(plan['risk_decision'], 'PASS')
        self.assertEqual(plan['trade_decision'], 'WAIT')
        self.assertFalse(plan['execution_enabled'])
        self.assertEqual(plan['validation_status'], 'unvalidated')
        self.assertIsNone(plan['success_probability_pct'])
        self.assertEqual(plan['expires_at'], NOW+5)
        self.assertLessEqual(D(plan['modeled_loss_usd']), D(plan['risk_budget_usd']))
        self.assertLessEqual(D(plan['entry_cost_usd']), D('10000'))
        self.assertGreaterEqual(D(plan['net_reward_risk']), 2)
        self.assertEqual(D(plan['estimated_round_trip_cost_bps']), 170)
        self.assertEqual(self.store.get_state('account'), account)
        self.assertEqual(self.store.list('paper'), [])

    def test_plan_does_not_extend_an_almost_expired_book_observation(self):
        save_profile(self.store, inputs(), NOW)
        # The book is valid at request time, with only ~100ms of freshness left.
        almost_old = book(now=NOW-4.9)
        self.assertTrue(almost_old.fresh(NOW))
        plan = evaluate_real_plan(self.store, almost_old, '98', '110', NOW)
        self.assertEqual(plan['risk_decision'], 'PASS')
        self.assertGreater(plan['expires_at'], NOW)
        self.assertLess(plan['expires_at'], NOW+0.11)
        # A client using expires_at must stop showing PASS as soon as the
        # underlying observation becomes stale, without needing another request.
        self.assertFalse(almost_old.fresh(NOW+0.11))
        self.assertGreaterEqual(NOW+0.11, plan['expires_at'])

    def test_plan_expiry_honors_receipt_age_and_does_not_extend_for_future_source(self):
        save_profile(self.store, inputs(), NOW)
        delayed_receipt = book()
        delayed_receipt.received_at = NOW-4.9
        self.assertTrue(delayed_receipt.fresh(NOW))
        plan = evaluate_real_plan(self.store, delayed_receipt, '98', '110', NOW)
        self.assertEqual(plan['risk_decision'], 'PASS')
        self.assertLess(plan['expires_at'], NOW+0.11)
        clock_skew = book()
        clock_skew.source_at = NOW+0.5
        self.assertTrue(clock_skew.fresh(NOW))
        self.assertEqual(evaluate_real_plan(self.store, clock_skew, '98', '110', NOW)['expires_at'],NOW+5)

    def test_position_cash_and_exposure_caps_bound_sized_quantity(self):
        cases = [inputs(max_position_pct='0.2'), inputs(available_cash_usd='15'),
            inputs(existing_crypto_exposure_usd='2490')]
        for body in cases:
            with self.subTest(body=body):
                save_profile(self.store, body, NOW)
                p = evaluate_real_plan(self.store, book(), '98', '110', NOW)
                self.assertEqual(p['risk_decision'], 'PASS')
                self.assertLessEqual(D(p['notional_usd']), D(p['maximum_position_usd']))
                self.assertLessEqual(D(p['notional_usd']), D(p['remaining_exposure_usd']))
                self.assertLessEqual(D(p['entry_cost_usd']), D(body['available_cash_usd']))

    def test_remaining_daily_loss_budget_limits_each_new_plan(self):
        save_profile(self.store, inputs(daily_realized_pnl_usd='-195'), NOW)
        plan = evaluate_real_plan(self.store, book(), '98', '110', NOW)
        self.assertEqual(plan['risk_decision'], 'PASS')
        self.assertEqual(D(plan['configured_risk_budget_usd']), 50)
        self.assertEqual(D(plan['risk_budget_usd']), 5)
        self.assertLessEqual(D(plan['modeled_loss_usd']), 5)

    def test_exhausted_cash_exposure_daily_loss_and_emergency_stop_fail_closed(self):
        for body,fragment in [(inputs(available_cash_usd='0'), 'cash'),
                              (inputs(existing_crypto_exposure_usd='2500'), 'exposure'),
                              (inputs(daily_realized_pnl_usd='-200'), 'daily')]:
            save_profile(self.store, body, NOW)
            p = evaluate_real_plan(self.store, book(), '98', '110', NOW)
            self.assertEqual(p['risk_decision'], 'FAIL')
            self.assertIsNone(p['quantity'])
            self.assertTrue(any(fragment in r for r in p['reasons']))
        save_profile(self.store, inputs(), NOW)
        self.store.set_state('control', {'stopped':True})
        self.assertEqual(evaluate_real_plan(self.store, book(), '98', '110', NOW)['risk_decision'], 'FAIL')

    def test_no_profile_old_profile_stale_book_or_incompatible_quote_never_sizes(self):
        self.assertEqual(evaluate_real_plan(self.store, book(), '98', '110', NOW)['risk_decision'], 'FAIL')
        save_profile(self.store, inputs(), NOW)
        self.assertEqual(evaluate_real_plan(self.store, book(), '98', '110', NOW+6)['risk_decision'], 'FAIL')
        self.assertEqual(evaluate_real_plan(self.store, book(now=NOW+86400), '98', '110', NOW+86400)['risk_decision'], 'FAIL')
        for instrument,quote in [('perpetual','USDC'), ('spot','CAD'), ('spot','USDC')]:
            b=book(); b.instrument=instrument; b.quote=quote
            p=evaluate_real_plan(self.store, b, '98', '110', NOW)
            self.assertEqual(p['risk_decision'], 'FAIL')
            self.assertIsNone(p['quantity'])

    def test_quantity_rounding_is_down_and_costs_reduce_raw_reward_risk(self):
        save_profile(self.store, inputs(available_cash_usd='1.23456789'), NOW)
        plan=evaluate_real_plan(self.store, book(), '98', '110', NOW)
        quantity=D(plan['quantity'])
        self.assertEqual(quantity.as_tuple().exponent, -8)
        self.assertLessEqual(D(plan['entry_cost_usd']), D('1.23456789'))
        save_profile(self.store, inputs(), NOW)
        p=evaluate_real_plan(self.store, book(), '99', '102', NOW)
        self.assertEqual(p['risk_decision'], 'FAIL')
        self.assertTrue(any('reward/risk' in r for r in p['reasons']))

    def test_visible_depth_price_impact_cannot_silently_breach_sizing_limits(self):
        save_profile(self.store, inputs(), NOW)
        b=book(asks=[('100','0.01'), ('105','1000')])
        p=evaluate_real_plan(self.store, b, '98', '130', NOW)
        self.assertEqual(p['risk_decision'], 'FAIL')
        self.assertGreater(D(p['entry_depth_slippage_bps']), 0)
        self.assertTrue(any('after visible-depth costs' in r or 'position cap' in r for r in p['reasons']))

    def test_size_never_exceeds_real_visible_liquidity(self):
        save_profile(self.store, inputs(), NOW)
        p=evaluate_real_plan(self.store, book(asks=[('100','0.123456789')]), '98', '110', NOW)
        self.assertEqual(p['risk_decision'], 'PASS')
        self.assertEqual(D(p['quantity']), D('0.12345678'))
        self.assertGreater(D(p['entry_fee_usd']), 0)
        self.assertGreater(D(p['stop_exit_fee_usd']), 0)

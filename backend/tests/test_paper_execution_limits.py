"""Synthetic depth regressions: actual paper exposure, never real exchange orders."""
from copy import deepcopy
from decimal import Decimal as D
import unittest
from sentinel.engine import FEES,POLICY,evaluate_paper_plan,paper_open
from sentinel.models import Book
from sentinel.storage import Store

NOW = 1800000000


def book(asks=None):
    result = Book('kraken','SYNTHETIC-USD')
    result.update([('99','100')],asks or [('100','100')],NOW,NOW,snapshot=True)
    return result


class PaperExecutionLimitTests(unittest.TestCase):
    def setUp(self):self.store=Store('sqlite:///:memory:')
    def tearDown(self):self.store.close()

    def test_thin_depth_cannot_turn_500_requested_into_4993_actual_position(self):
        before=deepcopy(self.store.get_state('account'))
        with self.assertRaisesRegex(ValueError,'position limit'):
            paper_open(self.store,book([('100','.01'),('1000','10')]),'500','SYNTHETIC_THIN',NOW)
        self.assertEqual(self.store.get_state('account'),before)
        self.assertEqual(self.store.list('paper'),[])
        self.assertEqual(self.store.list('audit'),[])

    def test_actual_depth_exposure_cannot_breach_aggregate_limit(self):
        for i in range(5):
            self.store.put('paper',{'status':'open','entry_notional':'444'},id='SYNTHETIC_EXISTING_'+str(i))
        before=deepcopy(self.store.get_state('account'))
        initial_positions=deepcopy(self.store.list('paper'))
        # The requested $250 passes the old lower-bound check against $2,220
        # existing exposure. Its actual depth cost is about $299.95, over cap.
        self.assertLess(D(2220)+D(250)*(1+POLICY.latency_bps/10000),POLICY.max_total_exposure)
        with self.assertRaisesRegex(ValueError,'exposure'):
            paper_open(self.store,book([('100','.01'),('120','10')]),'250','SYNTHETIC_EXPOSURE',NOW)
        self.assertEqual(self.store.get_state('account'),before)
        self.assertEqual(self.store.list('paper'),initial_positions)
        self.assertEqual(self.store.list('audit'),[])

    def test_latency_alone_cannot_push_a_boundary_request_over_position_cap(self):
        with self.assertRaisesRegex(ValueError,'position limit'):
            paper_open(self.store,book(),'500','SYNTHETIC_BOUNDARY',NOW)
        self.assertEqual(self.store.get_state('account')['cash'],'10000')
        self.assertEqual(self.store.list('paper'),[])

    def test_risk_plan_cannot_show_go_for_a_fill_the_position_cap_rejects(self):
        result=evaluate_paper_plan(book(),'500','98','110',now=NOW)
        self.assertEqual(result['decision'],'NO-GO')
        self.assertTrue(any('position limit' in reason for reason in result['stages']['skeptic']['objections']))

    def test_normal_fill_preserves_units_and_deducts_actual_notional_plus_fees(self):
        result=paper_open(self.store,book(),'499','SYNTHETIC_NORMAL',NOW)
        cost=D(result['entry_notional'])
        fee=D(result['entry_fee'])
        self.assertEqual(D(result['quantity']),D('4.99'))
        self.assertEqual(cost,D('499.2495'))
        self.assertLessEqual(cost,POLICY.max_position)
        self.assertEqual(fee,cost*FEES['kraken']/10000)
        self.assertEqual(D(self.store.get_state('account')['cash']),D(10000)-cost-fee)

    def test_cash_check_includes_fees_before_persisting(self):
        account=self.store.get_state('account');account['cash']='100.50'
        self.store.set_state('account',account)
        with self.assertRaisesRegex(ValueError,'cash'):
            paper_open(self.store,book(),'100','SYNTHETIC_FEES',NOW)
        self.assertEqual(self.store.get_state('account')['cash'],'100.50')
        self.assertEqual(self.store.list('paper'),[])

    def test_idempotent_retry_does_not_execute_again_against_changed_depth(self):
        result=paper_open(self.store,book(),'250','SYNTHETIC_RETRY',NOW)
        cash=self.store.get_state('account')['cash']
        unsafe_book=book([('100','.01'),('1000','10')])
        self.assertEqual(paper_open(self.store,unsafe_book,'250','SYNTHETIC_RETRY',NOW),result)
        self.assertEqual(self.store.get_state('account')['cash'],cash)
        self.assertEqual(len(self.store.list('paper')),1)
        with self.assertRaisesRegex(ValueError,'position limit'):
            paper_open(self.store,unsafe_book,'250','SYNTHETIC_NEW_REQUEST',NOW)
        self.assertEqual(self.store.get_state('account')['cash'],cash)
        self.assertEqual(len(self.store.list('paper')),1)

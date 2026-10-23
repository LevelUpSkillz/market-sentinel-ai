"""User-declared real-capital planning, isolated from paper cash and execution.

These calculations do not verify balances, establish a trading edge, reserve funds
or submit an order. USD spot is the only supported reference instrument here.
"""
from decimal import Decimal as D, ROUND_DOWN
from math import isfinite
import time
from .engine import FEES, POLICY
from .models import decimal

VERSION = 'real-capital-v1'
SOURCE = 'USER_DECLARED_UNVERIFIED'
STATE_KEY = 'real_capital_profile'
FIELDS = (
    'capital_usd', 'available_cash_usd', 'existing_crypto_exposure_usd',
    'daily_realized_pnl_usd', 'risk_per_trade_pct', 'max_position_pct',
    'max_crypto_exposure_pct', 'daily_loss_limit_pct',
)
MAX_CAPITAL = D('10000000')
QUANTITY_INCREMENT = D('0.00000001')  # Display-sizing precision, not a verified exchange lot size.
LIMITATIONS = [
    'Capital, available cash, existing exposure and daily P&L are user-declared; no exchange balance is verified or reserved.',
    'A risk PASS does not establish a validated trading edge or approve a real-money order.',
    'Fees are conservative model assumptions, not a verified personal fee tier. Adverse latency is modeled on both legs.',
    'A stop is not a guaranteed exit price. Gaps, outages and future exit liquidity can cause losses beyond the modeled amount.',
    'Future exit spread/depth, minimum order size, exchange lot increments and trading eligibility are unverified.',
    'Quantity is rounded down for display precision; no exchange order, withdrawal or fund transfer is available from this planner.',
]


def _now(value):
    value = time.time() if value is None else float(value)
    if not isfinite(value) or value <= 0:raise ValueError('Invalid confirmation timestamp')
    return value


def _string(value):
    return format(value, 'f')


def _bounded_decimal(value, label):
    out = decimal(value)
    # Scientific notation must not expand a tiny JSON input into megabytes of
    # fixed-point output. Eighteen fractional places exceed this planner's
    # displayed quantity precision without accepting unbounded exponents.
    if not -18 <= out.as_tuple().exponent <= 12 or abs(out) > D('1000000000000'):
        raise ValueError(label+' exceeds the supported numeric precision or range')
    return out


def _profile_values(body):
    if not isinstance(body, dict):raise ValueError('A complete real-capital profile is required')
    unknown = set(body)-set(FIELDS)-{'currency'}
    if unknown:raise ValueError('Unknown real-capital profile fields')
    if body.get('currency', 'USD') != 'USD':
        raise ValueError('This planner requires a USD-denominated budget; currency conversion is not assumed')
    values = {}
    for key in FIELDS:
        value = body.get(key)
        if not isinstance(value, str) or not value or len(value) > 80:
            raise ValueError(key+' must be a finite decimal string')
        values[key] = _bounded_decimal(value, key)
    capital = values['capital_usd']
    if not D(0) < capital <= MAX_CAPITAL:
        raise ValueError('Real-capital budget must be positive and at most 10,000,000 USD')
    if not D(0) <= values['available_cash_usd'] <= capital:
        raise ValueError('Declared available USD cash must be between zero and the capital budget')
    if not D(0) <= values['existing_crypto_exposure_usd'] <= MAX_CAPITAL:
        raise ValueError('Declared crypto exposure must be nonnegative and at most 10,000,000 USD')
    if abs(values['daily_realized_pnl_usd']) > MAX_CAPITAL:
        raise ValueError('Declared daily realized P&L exceeds the supported planning range')
    for key, maximum in (('risk_per_trade_pct', D(2)), ('max_position_pct', D(25)),
                         ('max_crypto_exposure_pct', D(100)), ('daily_loss_limit_pct', D(10))):
        if not D(0) < values[key] <= maximum:
            raise ValueError(key+' must be greater than zero and at most '+str(maximum))
    return values


def save_profile(store, body, now=None):
    """Persist only explicit owner inputs; never touch the simulated account."""
    now = _now(now)
    values = _profile_values(body)
    profile = {key:_string(value) for key,value in values.items()}
    profile.update(version=VERSION, currency='USD', source=SOURCE,
        confirmed_at=now, execution_enabled=False,
        confirmation_note='Owner declaration only; actual exchange balances and permissions remain unverified.')
    with store.transaction():
        store.set_state(STATE_KEY, profile)
        store.put('audit', {'action':'real_capital.update', 'actor':'owner',
            'profile_version':VERSION, 'currency':'USD', 'confirmed_at':now,
            'execution_enabled':False}, at=now)
    return get_profile(store, now)


def get_profile(store, now=None):
    now = _now(now)
    profile = store.get_state(STATE_KEY)
    if not profile:return None
    reasons = []
    confirmed = profile.get('confirmed_at')
    if not isinstance(confirmed, (int, float)) or not isfinite(confirmed):
        reasons.append('The owner confirmation timestamp is unavailable.')
    elif confirmed > now+1:
        reasons.append('The owner confirmation timestamp is in the future.')
    else:
        if now-confirmed >= 86400:
            reasons.append('The declared capital profile is at least 24 hours old.')
        if int(now//86400) != int(confirmed//86400):
            reasons.append('The UTC day changed; daily realized P&L must be confirmed again.')
    return dict(profile, stale=bool(reasons), stale_reasons=reasons,
        source=SOURCE, execution_enabled=False)


def evaluate_real_plan(store, book, stop, target, now=None):
    """Size a manual long spot hypothesis; PASS is arithmetic, never trade approval."""
    now = _now(now)
    stop, target = _bounded_decimal(stop, 'stop'), _bounded_decimal(target, 'target')
    profile = get_profile(store, now)
    reasons = []
    result = {
        'version':VERSION, 'strategy_version':VERSION,
        'mode':'REAL_CAPITAL_MANUAL_PLAN', 'currency':'USD', 'source':SOURCE,
        'execution_enabled':False, 'trade_decision':'WAIT', 'risk_decision':'FAIL',
        'validation_status':'unvalidated', 'success_probability_pct':None,
        'as_of':now, 'expires_at':now+5,
        'provider':getattr(book, 'provider', None), 'symbol':getattr(book, 'symbol', None),
        'profile_confirmed_at':profile.get('confirmed_at') if profile else None,
        'stop':_string(stop), 'target':_string(target), 'quantity':None,
        'entry_vwap':None, 'notional_usd':None, 'entry_cost_usd':None,
        'modeled_loss_usd':None, 'net_target_profit_usd':None, 'net_reward_risk':None,
        'risk_budget_usd':None, 'configured_risk_budget_usd':None,
        'remaining_daily_loss_budget_usd':None, 'maximum_position_usd':None,
        'remaining_exposure_usd':None, 'entry_fee_usd':None,
        'stop_exit_fee_usd':None, 'target_exit_fee_usd':None,
        'fee_bps_per_leg':None, 'latency_bps_per_leg':_string(POLICY.latency_bps),
        'estimated_round_trip_cost_bps':None, 'entry_depth_slippage_bps':None,
        'snapshot':book.view(now) if book is not None else None,
        'reasons':reasons, 'limitations':list(LIMITATIONS),
    }
    if not profile:
        reasons.append('Configure and confirm a real-capital budget before sizing a manual plan.')
    elif profile['stale']:
        reasons.extend(profile['stale_reasons'])
    if store.get_state('control', {}).get('stopped'):
        reasons.append('Emergency stop is active.')
    if book is None or not book.fresh(now):
        reasons.append('A fresh, timestamp-verified detailed order book is required.')
    if book is not None and (book.instrument != 'spot' or book.quote != 'USD' or not book.symbol.endswith('-USD')):
        reasons.append('Only long USD spot plans are supported; no USD/USDC or currency conversion is assumed.')
    if book is not None and book.provider not in FEES:
        reasons.append('A reviewed fee model is unavailable for this provider.')
    if stop <= 0 or target <= 0:
        reasons.append('Stop and target prices must be positive.')
    if reasons:return _aliases(result)
    try:
        # Revalidate stored inputs rather than relying only on a profile version tag.
        values = _profile_values({key:profile[key] for key in FIELDS} | {'currency':profile['currency']})
        capital = values['capital_usd']
        configured_risk = capital*values['risk_per_trade_pct']/100
        daily_limit = capital*values['daily_loss_limit_pct']/100
        remaining_daily = max(D(0), daily_limit-max(D(0), -values['daily_realized_pnl_usd']))
        risk_budget = min(configured_risk, remaining_daily)
        max_position = capital*values['max_position_pct']/100
        remaining_exposure = max(D(0), capital*values['max_crypto_exposure_pct']/100-values['existing_crypto_exposure_usd'])
        cash = values['available_cash_usd']
        result.update(configured_risk_budget_usd=_string(configured_risk), risk_budget_usd=_string(risk_budget),
            remaining_daily_loss_budget_usd=_string(remaining_daily), maximum_position_usd=_string(max_position),
            remaining_exposure_usd=_string(remaining_exposure))
        if remaining_daily <= 0:reasons.append('The declared daily realized loss limit has been reached.')
        if cash <= 0:reasons.append('No available USD cash was declared.')
        if remaining_exposure <= 0:reasons.append('The declared correlated crypto exposure limit has been reached.')
        if reasons:return _aliases(result)
        fee, latency = FEES[book.provider]/10000, POLICY.latency_bps/10000
        ask = min(book.asks)
        entry_reference = ask*(1+latency)
        entry_unit_cost = entry_reference*(1+fee)
        stop_unit_proceeds = stop*(1-latency)*(1-fee)
        if not stop < entry_reference < target:
            reasons.append('A long plan requires a positive stop below entry and a target above entry.')
            return _aliases(result)
        loss_per_unit = entry_unit_cost-stop_unit_proceeds
        visible_quantity = sum(book.asks.values(), D(0))
        quantity = min(risk_budget/loss_per_unit, max_position/entry_reference,
            remaining_exposure/entry_reference, cash/entry_unit_cost, visible_quantity)
        quantity = quantity.quantize(QUANTITY_INCREMENT, rounding=ROUND_DOWN)
        if quantity <= 0:
            reasons.append('The available budgets or visible liquidity cannot support a positive displayed quantity.')
            return _aliases(result)
        raw_entry = book.fill('buy', quantity)
        entry = raw_entry*(1+latency)
        notional = entry*quantity
        entry_fee = notional*fee
        entry_cost = notional+entry_fee
        stop_exit_gross = stop*quantity*(1-latency)
        target_exit_gross = target*quantity*(1-latency)
        stop_exit_fee, target_exit_fee = stop_exit_gross*fee, target_exit_gross*fee
        loss = entry_cost-(stop_exit_gross-stop_exit_fee)
        reward = target_exit_gross-target_exit_fee-entry_cost
        ratio = reward/loss if loss > 0 else None
        depth_bps = (raw_entry/ask-1)*10000
        result.update(quantity=_string(quantity), entry_vwap=_string(entry), notional_usd=_string(notional),
            entry_cost_usd=_string(entry_cost), entry_fee_usd=_string(entry_fee),
            stop_exit_fee_usd=_string(stop_exit_fee), target_exit_fee_usd=_string(target_exit_fee),
            modeled_loss_usd=_string(loss), net_target_profit_usd=_string(reward),
            net_reward_risk=_string(ratio) if ratio is not None else None,
            fee_bps_per_leg=_string(FEES[book.provider]), entry_depth_slippage_bps=_string(depth_bps),
            estimated_round_trip_cost_bps=_string(2*FEES[book.provider]+2*POLICY.latency_bps+depth_bps))
        # Price impact can increase costs relative to the top-of-book sizing
        # estimate. Reject a violation; never silently resize upward or fabricate liquidity.
        if not stop < entry < target:reasons.append('The visible-depth entry invalidates the stop/entry/target ordering.')
        if not D(0) < loss <= risk_budget:
            reasons.append('Modeled loss exceeds the configured per-trade or remaining daily loss budget after visible-depth costs.')
        if entry_cost > cash:reasons.append('Available declared cash cannot fund the visible-depth entry including fees.')
        if notional > max_position:reasons.append('The visible-depth entry exceeds the configured position cap.')
        if notional > remaining_exposure:reasons.append('The visible-depth entry exceeds the remaining correlated exposure budget.')
        if ratio is None or ratio < 2:reasons.append('Net modeled reward/risk must be at least 2 after both-leg costs.')
        if not reasons:result['risk_decision'] = 'PASS'
    except (ValueError, ArithmeticError, KeyError) as error:
        reasons.append('This plan cannot be sized safely: '+str(error))
    return _aliases(result)


def _aliases(result):
    # Consistent names with existing paper-risk cards without changing their account.
    result['entry_cost'] = result['entry_cost_usd']
    result['modeled_loss'] = result['modeled_loss_usd']
    result['maximum_modeled_loss'] = result['modeled_loss_usd']
    result['net_target_profit'] = result['net_target_profit_usd']
    result['risk_reward'] = result['net_reward_risk']
    return result

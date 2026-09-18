from collections import namedtuple

import pytest

from python_service.app.local_copy_trading import volume_planner
from python_service.app.local_copy_trading.models import CopyRelationship


SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step', 'volume_max', 'trade_contract_size'])


def _symbol(**overrides):
    fields = {
        'volume_min': 0.01,
        'volume_step': 0.01,
        'volume_max': 100.0,
        'trade_contract_size': 100.0,
    }
    fields.update(overrides)
    return SymbolInfo(**fields)


def _relationship(**overrides):
    fields = {
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
    }
    fields.update(overrides)
    return CopyRelationship(**fields)


def test_multiplier_mode_scales_the_source_volume():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=2),
        {'volume': 0.1},
        symbol_info=_symbol(),
    )

    assert volume == 0.2


def test_fixed_mode_ignores_the_source_volume():
    volume = volume_planner.plan_volume(
        _relationship(volume_mode='fixed', lot_multiplier=0.5),
        {'volume': 3.0},
        symbol_info=_symbol(),
    )

    assert volume == 0.5


def test_equity_ratio_mode_scales_with_the_account_ratio():
    volume = volume_planner.plan_volume(
        _relationship(volume_mode='equity_ratio'),
        {'volume': 0.4},
        symbol_info=_symbol(),
        source_equity=10000.0,
        follower_equity=2500.0,
    )

    assert volume == 0.1


def test_equity_ratio_mode_requires_both_equities():
    with pytest.raises(ValueError, match='equity_ratio sizing requires both account equities'):
        volume_planner.plan_volume(
            _relationship(volume_mode='equity_ratio'),
            {'volume': 0.4},
            symbol_info=_symbol(),
            source_equity=10000.0,
        )


def test_risk_percent_mode_sizes_from_the_stop_distance():
    volume = volume_planner.plan_volume(
        _relationship(volume_mode='risk_percent', risk_percent=1),
        {'volume': 0.1, 'price_open': 2300.0, 'sl': 2280.0},
        symbol_info=_symbol(),
        source_equity=10000.0,
    )

    assert volume == 0.05


def test_risk_percent_mode_requires_a_stop_loss():
    with pytest.raises(ValueError, match='requires a source position with a stop loss'):
        volume_planner.plan_volume(
            _relationship(volume_mode='risk_percent'),
            {'volume': 0.1, 'price_open': 2300.0, 'sl': 0.0},
            symbol_info=_symbol(),
            source_equity=10000.0,
        )


def test_risk_percent_mode_requires_a_contract_size():
    with pytest.raises(ValueError, match='requires a known contract size'):
        volume_planner.plan_volume(
            _relationship(volume_mode='risk_percent'),
            {'volume': 0.1, 'price_open': 2300.0, 'sl': 2280.0},
            symbol_info=_symbol(trade_contract_size=0.0),
            source_equity=10000.0,
        )


def test_max_lot_caps_the_result():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=100, max_lot=0.5),
        {'volume': 1.0},
        symbol_info=_symbol(),
    )

    assert volume == 0.5


def test_a_zero_max_lot_means_no_cap():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=3, max_lot=0),
        {'volume': 1.0},
        symbol_info=_symbol(),
    )

    assert volume == 3.0


def test_result_is_snapped_to_the_volume_step():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=1),
        {'volume': 0.107},
        symbol_info=_symbol(),
    )

    assert volume == 0.1


def test_result_is_lifted_to_the_symbol_minimum():
    volume = volume_planner.plan_volume(
        _relationship(lot_multiplier=1),
        {'volume': 0.001},
        symbol_info=_symbol(),
    )

    assert volume == 0.01


def test_result_is_capped_by_the_symbol_maximum():
    volume = volume_planner.plan_volume(
        _relationship(volume_mode='fixed', lot_multiplier=50.0),
        {'volume': 0.1},
        symbol_info=_symbol(volume_max=10.0),
    )

    assert volume == 10.0


def test_multiplier_mode_rejects_a_zero_source_volume():
    with pytest.raises(ValueError, match='copy volume must be greater than 0'):
        volume_planner.plan_volume(
            _relationship(),
            {'volume': 0.0},
            symbol_info=_symbol(),
        )


def test_unknown_volume_mode_is_rejected():
    relationship = _relationship()
    object.__setattr__(relationship, 'volume_mode', 'martingale')

    with pytest.raises(ValueError, match='Unsupported volume mode'):
        volume_planner.plan_volume(relationship, {'volume': 0.1}, symbol_info=_symbol())

from collections import namedtuple

from python_service.app.local_copy_trading import price_mapping


SymbolInfo = namedtuple('SymbolInfo', ['digits'])


def test_a_long_position_keeps_stop_below_and_target_above():
    source = {'price_open': 2300.0, 'sl': 2280.0, 'tp': 2340.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2301.5)

    assert stop_loss == 2281.5
    assert take_profit == 2341.5


def test_a_short_position_keeps_stop_above_and_target_below():
    source = {'price_open': 2300.0, 'sl': 2320.0, 'tp': 2260.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2299.5)

    assert stop_loss == 2319.5
    assert take_profit == 2259.5


def test_a_missing_source_stop_stays_missing():
    source = {'price_open': 2300.0, 'sl': 0.0, 'tp': 2340.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2300.0)

    assert stop_loss == 0.0
    assert take_profit == 2340.0


def test_a_missing_source_entry_yields_no_levels():
    source = {'price_open': 0.0, 'sl': 2280.0, 'tp': 2340.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2300.0)

    assert (stop_loss, take_profit) == (0.0, 0.0)


def test_the_ratio_scales_the_distance_for_a_differently_quoted_symbol():
    source = {'price_open': 2300.0, 'sl': 2280.0, 'tp': 0.0}

    stop_loss, _ = price_mapping.translate_protective_levels(
        source, follower_entry=2300.0, ratio=10.0
    )

    assert stop_loss == 2100.0


def test_the_levels_follow_a_follower_entry_that_differs_from_the_source():
    source = {'price_open': 2300.0, 'sl': 2280.0, 'tp': 2340.0}

    stop_loss, take_profit = price_mapping.translate_protective_levels(source, follower_entry=2295.0)

    assert stop_loss == 2275.0
    assert take_profit == 2335.0


def test_normalize_price_rounds_to_the_symbol_digits():
    assert price_mapping.normalize_price(2301.5678, SymbolInfo(digits=2)) == 2301.57
    assert price_mapping.normalize_price(1.23456789, SymbolInfo(digits=5)) == 1.23457


def test_normalize_price_keeps_zero_as_zero():
    assert price_mapping.normalize_price(0.0, SymbolInfo(digits=2)) == 0.0

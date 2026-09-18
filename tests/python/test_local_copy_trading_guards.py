from python_service.app.local_copy_trading import guards
from python_service.app.local_copy_trading.models import CopyRelationship, CopyTradingRiskSettings


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


def _evaluate(**overrides):
    fields = {
        'planned_volume': 0.1,
        'follower_account_info': None,
        'follower_positions': [],
        'settings': CopyTradingRiskSettings(),
    }
    fields.update(overrides)
    relationship = fields.pop('relationship', _relationship())
    return guards.evaluate_open_guard(relationship, **fields)


def test_default_settings_allow_everything():
    decision = _evaluate()

    assert decision.allowed is True
    assert decision.rule == ''


def test_position_count_limit_blocks_a_new_position():
    settings = CopyTradingRiskSettings(max_positions_per_symbol=2)
    held = [{'symbol': 'XAUUSD.m', 'volume': 0.1}, {'symbol': 'XAUUSD.m', 'volume': 0.1}]

    decision = _evaluate(settings=settings, follower_positions=held)

    assert decision.allowed is False
    assert decision.rule == 'max_positions_per_symbol'


def test_position_count_ignores_other_symbols():
    settings = CopyTradingRiskSettings(max_positions_per_symbol=1)
    held = [{'symbol': 'EURUSD.m', 'volume': 0.1}]

    decision = _evaluate(settings=settings, follower_positions=held)

    assert decision.allowed is True


def test_volume_limit_counts_what_is_already_held():
    settings = CopyTradingRiskSettings(max_volume_per_symbol=0.5)
    held = [{'symbol': 'XAUUSD.m', 'volume': 0.3}, {'symbol': 'XAUUSD.m', 'volume': 0.1}]

    decision = _evaluate(settings=settings, follower_positions=held, planned_volume=0.2)

    assert decision.allowed is False
    assert decision.rule == 'max_volume_per_symbol'


def test_volume_limit_allows_an_order_that_fits():
    settings = CopyTradingRiskSettings(max_volume_per_symbol=0.5)
    held = [{'symbol': 'XAUUSD.m', 'volume': 0.1}]

    decision = _evaluate(settings=settings, follower_positions=held, planned_volume=0.2)

    assert decision.allowed is True


def test_daily_open_count_limit_blocks_further_orders():
    settings = CopyTradingRiskSettings(max_daily_open_count=5)

    decision = _evaluate(settings=settings, daily_open_count=5)

    assert decision.allowed is False
    assert decision.rule == 'daily_open_count'


def test_daily_loss_limit_blocks_further_orders():
    settings = CopyTradingRiskSettings(max_daily_loss=200)

    decision = _evaluate(settings=settings, daily_realized_profit=-200.0)

    assert decision.allowed is False
    assert decision.rule == 'daily_loss'


def test_daily_loss_limit_allows_a_profitable_day():
    settings = CopyTradingRiskSettings(max_daily_loss=200)

    decision = _evaluate(settings=settings, daily_realized_profit=150.0)

    assert decision.allowed is True


def test_margin_level_limit_blocks_a_stretched_account():
    settings = CopyTradingRiskSettings(min_margin_level=150)

    decision = _evaluate(settings=settings, follower_account_info={'margin_level': 120.0})

    assert decision.allowed is False
    assert decision.rule == 'margin_level'


def test_margin_level_limit_allows_a_healthy_account():
    settings = CopyTradingRiskSettings(min_margin_level=150)

    decision = _evaluate(settings=settings, follower_account_info={'margin_level': 480.0})

    assert decision.allowed is True


def test_margin_level_rule_is_skipped_when_the_terminal_reports_none():
    settings = CopyTradingRiskSettings(min_margin_level=150)

    decision = _evaluate(settings=settings, follower_account_info={'margin_level': None})

    assert decision.allowed is True


def test_consecutive_failure_limit_blocks_a_stuck_relationship():
    settings = CopyTradingRiskSettings(max_consecutive_failures=3)

    decision = _evaluate(settings=settings, consecutive_failures=3)

    assert decision.allowed is False
    assert decision.rule == 'consecutive_failures'


def test_consecutive_failure_limit_allows_a_recovering_relationship():
    settings = CopyTradingRiskSettings(max_consecutive_failures=3)

    decision = _evaluate(settings=settings, consecutive_failures=2)

    assert decision.allowed is True


def test_the_account_level_rule_wins_over_the_order_level_rule():
    settings = CopyTradingRiskSettings(min_margin_level=150, max_positions_per_symbol=1)

    decision = _evaluate(
        settings=settings,
        follower_account_info={'margin_level': 100.0},
        follower_positions=[{'symbol': 'XAUUSD.m', 'volume': 0.1}],
    )

    assert decision.rule == 'margin_level'


def test_settings_round_trip_through_disk(tmp_path):
    path = tmp_path / 'copy-trading-risk.json'
    settings = CopyTradingRiskSettings(max_volume_per_symbol=1.5, max_daily_loss=300)

    guards.save_risk_settings(settings, path)
    loaded = guards.load_risk_settings(path)

    assert loaded.max_volume_per_symbol == 1.5
    assert loaded.max_daily_loss == 300


def test_missing_settings_file_yields_defaults(tmp_path):
    loaded = guards.load_risk_settings(tmp_path / 'absent.json')

    assert loaded == CopyTradingRiskSettings()

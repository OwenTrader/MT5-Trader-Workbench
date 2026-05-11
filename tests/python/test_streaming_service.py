import asyncio
import json
from types import SimpleNamespace

from python_service.app.routes import alerts
from python_service.app.models.alerts import OrderBroadcastRule
from python_service.app.services import streaming_service


def test_should_poll_mt5_returns_false_when_auto_connect_disabled(monkeypatch):
    streaming_service.manager.active_connections = []
    monkeypatch.setattr(
        streaming_service,
        'get_settings',
        lambda: SimpleNamespace(auto_connect=False),
        raising=False,
    )

    assert streaming_service.should_poll_mt5() is False


def test_should_poll_mt5_returns_true_when_overlay_is_connected(monkeypatch):
    streaming_service.manager.active_connections = [object()]
    monkeypatch.setattr(
        streaming_service,
        'get_settings',
        lambda: SimpleNamespace(auto_connect=False),
        raising=False,
    )

    try:
        assert streaming_service.should_poll_mt5() is True
    finally:
        streaming_service.manager.active_connections = []


def test_should_poll_mt5_returns_true_when_auto_connect_enabled(monkeypatch):
    monkeypatch.setattr(
        streaming_service,
        'get_settings',
        lambda: SimpleNamespace(auto_connect=True),
        raising=False,
    )

    assert streaming_service.should_poll_mt5() is True


def test_should_poll_mt5_returns_true_when_order_broadcast_rule_is_active(monkeypatch):
    streaming_service.manager.active_connections = []
    alerts.active_alerts = [OrderBroadcastRule(id='rule-1', symbol='XAUUSD', is_active=True)]
    monkeypatch.setattr(
        streaming_service,
        'get_settings',
        lambda: SimpleNamespace(auto_connect=False),
        raising=False,
    )

    try:
        assert streaming_service.should_poll_mt5() is True
    finally:
        alerts.active_alerts = []


def test_streaming_loop_does_not_initialize_mt5_when_auto_connect_disabled(monkeypatch):
    calls = {'get_mt5_client': 0}
    streaming_service.manager.active_connections = []

    monkeypatch.setattr(streaming_service, 'should_poll_mt5', lambda: False)

    def fake_get_mt5_client(*, allow_launch=True):
        calls['get_mt5_client'] += 1
        return None

    async def fake_sleep(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(streaming_service, 'get_mt5_client', fake_get_mt5_client)
    monkeypatch.setattr(streaming_service.asyncio, 'sleep', fake_sleep)

    try:
        asyncio.run(streaming_service.streaming_loop())
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError('streaming_loop did not propagate cancellation')

    assert calls['get_mt5_client'] == 0


def test_get_symbol_quote_selects_symbol_before_reading_tick(monkeypatch):
    calls = []

    monkeypatch.setattr(streaming_service.mt5, 'symbol_select', lambda symbol, enable: calls.append((symbol, enable)) or True)
    monkeypatch.setattr(streaming_service.mt5, 'symbol_info', lambda symbol: type('Info', (), {'digits': 2})())
    monkeypatch.setattr(streaming_service.mt5, 'symbol_info_tick', lambda symbol: type('Tick', (), {'bid': 3300.5, 'ask': 3301.0, 'time': 123})())
    monkeypatch.setattr(streaming_service.mt5, 'copy_rates_from_pos', lambda *args: [{'open': 3300.0}])

    quote = streaming_service.get_symbol_quote('XAUUSD')

    assert calls == [('XAUUSD', True)]
    assert quote['bid'] == 3300.5


def test_get_symbol_quote_uses_matching_symbol_when_base_symbol_has_no_tick(monkeypatch):
    selected = []

    monkeypatch.setattr(streaming_service.mt5, 'symbols_get', lambda pattern: [type('Symbol', (), {'name': 'XAUUSD.r'})()])
    monkeypatch.setattr(streaming_service.mt5, 'symbol_select', lambda symbol, enable: selected.append((symbol, enable)) or True)
    monkeypatch.setattr(streaming_service.mt5, 'symbol_info', lambda symbol: type('Info', (), {'digits': 2})() if symbol == 'XAUUSD.r' else None)
    monkeypatch.setattr(streaming_service.mt5, 'symbol_info_tick', lambda symbol: type('Tick', (), {'bid': 3300.5, 'ask': 3301.0, 'time': 123})() if symbol == 'XAUUSD.r' else None)
    monkeypatch.setattr(streaming_service.mt5, 'copy_rates_from_pos', lambda *args: [{'open': 3300.0}])

    quote = streaming_service.get_symbol_quote('XAUUSD')

    assert selected == [('XAUUSD', True), ('XAUUSD.r', True)]
    assert quote['bid'] == 3300.5


def test_load_alerts_preserves_order_broadcast_active_state(tmp_path, monkeypatch):
    alerts_file = tmp_path / 'alerts.json'
    alerts_file.write_text(json.dumps([
        {
            'id': 'rule-1',
            'symbol': 'XAUUSD',
            'is_active': True,
            'type': 'order-broadcast',
        }
    ]), encoding='utf-8')

    monkeypatch.setattr(alerts, 'ALERTS_FILE', str(alerts_file))
    alerts.active_alerts = []

    alerts.load_alerts()

    assert alerts.active_alerts[0].is_active is True


def test_collect_order_broadcast_messages_handles_new_modified_and_cancelled_orders():
    streaming_service.order_broadcast_snapshots = {}

    messages = streaming_service.collect_order_broadcast_messages([
        {
            'source': 'position',
            'ticket': 1,
            'symbol': 'XAUUSD',
            'type': streaming_service.mt5.POSITION_TYPE_BUY,
            'volume': 0.01,
            'price_open': 3300.0,
            'tp': 3310.0,
            'sl': 3290.0,
        }
    ], {'XAUUSD'})

    assert messages == ['XAUUSD buy 0.01 at 3300,tp:3310,sl:3290']

    messages = streaming_service.collect_order_broadcast_messages([
        {
            'source': 'position',
            'ticket': 1,
            'symbol': 'XAUUSD',
            'type': streaming_service.mt5.POSITION_TYPE_BUY,
            'volume': 0.01,
            'price_open': 3300.0,
            'tp': 3320.0,
            'sl': 3290.0,
        }
    ], {'XAUUSD'})

    assert messages == ['XAUUSD buy 0.01 at 3300,tp:3320,sl:3290. modify tp to 3320']

    messages = streaming_service.collect_order_broadcast_messages([], {'XAUUSD'})

    assert messages == ['XAUUSD buy 0.01 at 3300,tp:3320,sl:3290. canceled']


def test_collect_order_broadcast_messages_includes_pending_orders():
    streaming_service.order_broadcast_snapshots = {}

    messages = streaming_service.collect_order_broadcast_messages([
        {
            'source': 'order',
            'ticket': 2,
            'symbol': 'XAUUSD',
            'type': streaming_service.mt5.ORDER_TYPE_BUY_LIMIT,
            'volume_current': 0.02,
            'price_open': 3295.0,
            'tp': 3310.0,
            'sl': 3280.0,
        }
    ], {'XAUUSD'})

    assert messages == ['XAUUSD buy limit 0.02 at 3295,tp:3310,sl:3280']


def test_get_current_order_broadcast_items_returns_none_when_mt5_data_missing(monkeypatch):
    monkeypatch.setattr(streaming_service.mt5, 'positions_get', lambda: None)
    monkeypatch.setattr(streaming_service.mt5, 'orders_get', lambda: [])
    monkeypatch.setattr(streaming_service.mt5, 'last_error', lambda: (1, 'temporary failure'))

    assert streaming_service.get_current_order_broadcast_items() is None

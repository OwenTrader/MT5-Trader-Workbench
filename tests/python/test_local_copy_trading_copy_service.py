import contextlib
from collections import namedtuple

import pytest

from python_service.app.local_copy_trading import copy_service, copy_trading_db, position_ownership
from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    CopyTradingRiskSettings,
    FollowerAccount,
    SyncEvent,
)
from python_service.app.services.mt5_session import Mt5SessionError


Tick = namedtuple('Tick', ['ask', 'bid'])
SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step', 'volume_max', 'digits', 'trade_contract_size'])
OrderResult = namedtuple('OrderResult', ['retcode', 'order', 'deal', 'comment'])
AccountInfo = namedtuple('AccountInfo', ['equity', 'margin_level'])
Position = namedtuple('Position', ['ticket', 'identifier', 'symbol', 'type', 'volume', 'magic', 'comment'])
Deal = namedtuple('Deal', ['entry', 'profit', 'commission', 'swap'])


class FakeClient:
    """Minimal MetaTrader5 stand-in covering what the copy path touches."""

    POSITION_TYPE_BUY = 0
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    def __init__(self, positions=None, margin_level=None):
        self.sent_requests = []
        self.positions = list(positions or [])
        self.margin_level = margin_level
        self.retcode = 10009
        self.deals = []

    def symbol_select(self, symbol, enabled):
        return enabled is True

    def symbol_info(self, symbol):
        return SymbolInfo(
            volume_min=0.01,
            volume_step=0.01,
            volume_max=100.0,
            digits=2,
            trade_contract_size=100.0,
        )

    def symbol_info_tick(self, symbol):
        return Tick(ask=2301.5, bid=2301.3)

    def account_info(self):
        return AccountInfo(equity=10000.0, margin_level=self.margin_level)

    def order_send(self, request):
        self.sent_requests.append(request)
        return OrderResult(retcode=self.retcode, order=456, deal=0, comment='done')

    def positions_get(self, symbol=None):
        return self.positions

    def history_deals_get(self, date_from, date_to):
        return self.deals

    def last_error(self):
        return (0, 'ok')


def _follower(**overrides):
    fields = {
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'D:/MT5/follower/terminal64.exe',
        'login': '2001',
        'password': 'secret',
        'server': 'Demo',
    }
    fields.update(overrides)
    return FollowerAccount(**fields)


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


def _copied_event(**overrides):
    fields = {
        'relationship_id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'position_id': 'pos-1',
        'follower_position_id': '789',
        'follower_order_id': '456',
        'symbol': 'XAUUSD.m',
        'status': 'copied',
        'created_at': '2026-09-18T00:00:00+00:00',
    }
    fields.update(overrides)
    return SyncEvent(**fields)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'copy.db'
    copy_trading_db.init_db(path)
    return path


@pytest.fixture
def session(monkeypatch):
    client = FakeClient()

    @contextlib.contextmanager
    def fake_use_account(*args, **kwargs):
        yield client

    monkeypatch.setattr(copy_service, 'use_account', fake_use_account)
    return client


def _seed_confirmed(db, client_key='rel-1:pos-1', ticket='789'):
    copy_trading_db.insert_pending(
        client_key=client_key,
        relationship_id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        source_position_id='pos-1',
        created_at='2026-09-18T00:00:00+00:00',
        db_path=db,
    )
    copy_trading_db.confirm_order(
        client_key,
        follower_position_ticket=ticket,
        follower_order_id='456',
        message='Copied',
        updated_at='2026-09-18T00:00:01+00:00',
        db_path=db,
    )


def test_execute_copy_records_a_confirmed_order(db, session, monkeypatch):
    monkeypatch.setattr(
        copy_service.follower_executor,
        'copy_position_to_follower',
        lambda client, follower, relationship, position: (True, 'Copied', '789', '456'),
    )

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.success is True
    assert result.status == 'copied'
    assert result.follower_position_id == '789'
    assert result.follower_order_id == '456'
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['follower_position_ticket'] == '789'


def test_execute_copy_does_not_send_a_second_order_for_the_same_position(db, session, monkeypatch):
    sent = []

    def fake_copy(client, follower, relationship, position):
        sent.append(position['position_id'])
        return True, 'Copied', '789', '456'

    monkeypatch.setattr(copy_service.follower_executor, 'copy_position_to_follower', fake_copy)

    copy_service.execute_copy(_follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db)
    second = copy_service.execute_copy(_follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db)

    assert sent == ['pos-1']
    assert second.success is True
    assert 'Already copied' in second.message


def test_execute_copy_skips_a_position_confirmed_before_a_crash(db, session, monkeypatch):
    """A row written before the crash must suppress the order, not repeat it."""
    _seed_confirmed(db)

    def exploding_copy(*args, **kwargs):
        raise AssertionError('a second order must not be sent')

    monkeypatch.setattr(copy_service.follower_executor, 'copy_position_to_follower', exploding_copy)

    result = copy_service.execute_copy(_follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db)

    assert result.success is True
    assert result.follower_position_id == '789'
    assert 'Already copied' in result.message


def test_execute_copy_marks_the_row_failed_when_the_order_is_rejected(db, session, monkeypatch):
    monkeypatch.setattr(
        copy_service.follower_executor,
        'copy_position_to_follower',
        lambda *args: (False, 'Retcode: 10004', '', ''),
    )

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.success is False
    assert result.status == 'failed'
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'
    assert record['message'] == 'Retcode: 10004'


def test_execute_copy_marks_the_row_failed_when_the_session_fails(db, monkeypatch):
    def failing_use_account(*args, **kwargs):
        raise Mt5SessionError('login failed')

    monkeypatch.setattr(copy_service, 'use_account', failing_use_account)

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.success is False
    assert 'login failed' in result.message
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'


def test_execute_copy_rejects_a_position_without_an_identifier(db, session):
    result = copy_service.execute_copy(_follower(), _relationship(), {}, db_path=db)

    assert result.success is False
    assert 'no identifier' in result.message


def test_execute_close_settles_the_order_map_row(db, session, monkeypatch):
    _seed_confirmed(db)
    monkeypatch.setattr(
        copy_service.follower_executor,
        'close_copied_position_on_follower',
        lambda *args: (True, 'Closed follower position 789, order 999'),
    )

    success, message = copy_service.execute_close(_follower(), _relationship(), _copied_event(), db_path=db)

    assert success is True
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'closed'


def test_execute_close_leaves_the_row_open_when_the_close_fails(db, session, monkeypatch):
    _seed_confirmed(db)
    monkeypatch.setattr(
        copy_service.follower_executor,
        'close_copied_position_on_follower',
        lambda *args: (False, 'Retcode: 10006'),
    )

    success, message = copy_service.execute_close(_follower(), _relationship(), _copied_event(), db_path=db)

    assert success is False
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'


# --- pre-trade guards -------------------------------------------------------


def _owned(ticket=789, position_id='pos-1', volume=0.2, relationship_id='rel-1'):
    return Position(
        ticket=ticket,
        identifier=ticket,
        symbol='XAUUSD.m',
        type=0,
        volume=volume,
        magic=position_ownership.COPY_TRADING_MAGIC,
        comment=position_ownership.build_comment(relationship_id, position_id),
    )


def test_execute_copy_skips_the_order_when_a_guard_blocks_it(db, session):
    session.positions.append(Position(111, 111, 'XAUUSD.m', 0, 0.1, 0, ''))
    settings = CopyTradingRiskSettings(max_positions_per_symbol=1)

    result = copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    assert result.status == 'skipped'
    assert result.success is False
    assert session.sent_requests == []
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'skipped'


def test_execute_copy_places_the_order_when_the_guard_allows_it(db, session):
    settings = CopyTradingRiskSettings(max_positions_per_symbol=2)
    session.positions.append(_owned(volume=0.1))

    result = copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    assert result.status == 'copied'
    assert result.follower_position_id == '789'
    assert len(session.sent_requests) == 1


def test_execute_copy_reports_the_guard_that_fired_in_the_event_message(db, session):
    settings = CopyTradingRiskSettings(min_margin_level=150)
    session.margin_level = 120.0

    result = copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    assert result.status == 'skipped'
    assert 'margin level' in result.message
    assert session.sent_requests == []


def test_a_guarded_copy_does_not_count_as_a_failure(db, session):
    """A blocked copy must not feed the consecutive-failure breaker."""
    settings = CopyTradingRiskSettings(max_positions_per_symbol=1)
    session.positions.append(Position(111, 111, 'XAUUSD.m', 0, 0.1, 0, ''))

    copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'skipped'
    assert record['status'] != 'failed'


def test_a_guarded_copy_is_retried_once_the_limit_no_longer_applies(db, session):
    """The skipped row must not permanently suppress the position."""
    settings = CopyTradingRiskSettings(max_positions_per_symbol=1)
    session.positions.append(Position(111, 111, 'XAUUSD.m', 0, 0.1, 0, ''))
    payload = {'position_id': 'pos-1', 'volume': 0.1}

    first = copy_service.execute_copy(_follower(), _relationship(), payload, db_path=db, risk_settings=settings)
    session.positions.clear()
    second = copy_service.execute_copy(_follower(), _relationship(), payload, db_path=db, risk_settings=settings)

    assert first.status == 'skipped'
    assert second.status == 'copied'


# --- volume reconciliation --------------------------------------------------


def test_execute_copy_partially_closes_when_the_source_shrinks(db, session):
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.3, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.3))

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.status == 'copied'
    assert len(session.sent_requests) == 1
    request = session.sent_requests[0]
    assert request['position'] == 789
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_SELL
    assert 'Partially closed' in result.message


def test_execute_copy_scales_in_when_the_source_grows(db, session):
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.1, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.1))

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.2}, db_path=db
    )

    assert result.status == 'copied'
    request = session.sent_requests[0]
    assert 'position' not in request
    assert request['volume'] == 0.1
    assert request['type'] == FakeClient.ORDER_TYPE_BUY
    assert 'Scaled in' in result.message


def test_execute_copy_sends_nothing_when_the_source_size_is_unchanged(db, session):
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.1, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.1))

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result.success is True
    assert session.sent_requests == []


def test_execute_copy_remembers_the_source_size_it_acted_on(db, session):
    copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.4}, db_path=db
    )

    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.4


def test_execute_copy_reports_a_sizing_failure_on_an_existing_position(db, session):
    """A drift that cannot be sized is reported, and the open position stays recorded.

    The follower position is still open and still ours, so invalidating the row
    would only make reconciliation mistake it for an orphan.
    """
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.3, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.3))

    result = copy_service.execute_copy(
        _follower(),
        _relationship(volume_mode='risk_percent'),
        {'position_id': 'pos-1', 'volume': 0.1, 'price_open': 2300.0, 'sl': 0.0, 'source_equity': 10000.0},
        db_path=db,
    )

    assert result.status == 'failed'
    assert 'requires a source position with a stop loss' in result.message
    assert session.sent_requests == []
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'


def test_execute_copy_marks_drift_when_the_owned_position_is_gone_during_sync(db, session):
    """Ownership resolving to nothing must settle as drift, not retry forever."""
    _seed_confirmed(db)
    session.positions.append(Position(111, 111, 'XAUUSD.m', 0, 0.9, 0, ''))

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.5}, db_path=db
    )

    assert result.status == 'failed'
    assert session.sent_requests == []
    assert 'Drift' in result.message
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'drifted'
    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) is None


def test_a_failed_volume_sync_is_retried_as_an_adjustment_not_a_new_order(db, session):
    """A rejected partial close must be retried, never answered with a second position."""
    _seed_confirmed(db)
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.3, updated_at='2026-09-18T00:00:02+00:00', db_path=db
    )
    session.positions.append(_owned(volume=0.3))
    payload = {'position_id': 'pos-1', 'volume': 0.1}

    session.retcode = 10004
    first = copy_service.execute_copy(_follower(), _relationship(), payload, db_path=db)

    assert first.status == 'failed'
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'
    assert record['follower_position_ticket'] == '789'
    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.3

    session.retcode = 10009
    second = copy_service.execute_copy(_follower(), _relationship(), payload, db_path=db)

    assert second.status == 'copied'
    request = session.sent_requests[-1]
    assert request['position'] == 789
    assert request['volume'] == 0.2
    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.1


def test_a_guarded_copy_reads_the_daily_loss_from_deal_history(db, session):
    session.deals = [Deal(entry=1, profit=-250.0, commission=0.0, swap=0.0)]
    settings = CopyTradingRiskSettings(max_daily_loss=200)

    result = copy_service.execute_copy(
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'volume': 0.1},
        db_path=db,
        risk_settings=settings,
    )

    assert result.status == 'skipped'
    assert 'loss limit' in result.message
    assert session.sent_requests == []


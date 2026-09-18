import pytest

from python_service.app.local_copy_trading import copy_trading_db, position_ownership, reconcile
from python_service.app.local_copy_trading.models import Account, CopyRelationship, LocalCopyTradingState


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
    return Account(**fields)


def _state(**overrides):
    fields = {
        'enabled': True,
        'accounts': [_follower()],
        'relationships': [
            CopyRelationship(
                id='rel-1',
                source_account_id='src-1',
                follower_account_id='fol-1',
                symbol='XAUUSD',
            )
        ],
    }
    fields.update(overrides)
    return LocalCopyTradingState(**fields)


def _positions_for(position_id='pos-1', ticket=789, relationship_id='rel-1'):
    return [
        {
            'ticket': ticket,
            'symbol': 'XAUUSD.m',
            'magic': position_ownership.COPY_TRADING_MAGIC,
            'comment': position_ownership.build_comment(relationship_id, position_id),
        }
    ]


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'copy.db'
    copy_trading_db.init_db(path)
    return path


def _seed(db, status='pending', client_key='rel-1:pos-1'):
    copy_trading_db.insert_pending(
        client_key=client_key,
        relationship_id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        source_position_id='pos-1',
        created_at='2026-09-18T00:00:00+00:00',
        db_path=db,
    )
    if status == 'confirmed':
        copy_trading_db.confirm_order(
            client_key,
            follower_position_ticket='789',
            follower_order_id='456',
            updated_at='2026-09-18T00:00:01+00:00',
            db_path=db,
        )


def test_pending_record_is_confirmed_when_the_position_exists(db):
    _seed(db, status='pending')
    state = _state()

    events = reconcile.reconcile(state, db_path=db, positions_reader=lambda follower: _positions_for())

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['follower_position_ticket'] == '789'
    assert [event.status for event in events] == ['copied']


def test_confirmed_record_is_marked_drifted_when_the_position_is_gone(db):
    _seed(db, status='confirmed')
    state = _state()

    events = reconcile.reconcile(state, db_path=db, positions_reader=lambda follower: [])

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'drifted'
    assert [event.status for event in events] == ['failed']
    assert 'Drift' in events[0].message


def test_confirmed_record_with_its_position_produces_no_events(db):
    _seed(db, status='confirmed')
    state = _state()

    events = reconcile.reconcile(state, db_path=db, positions_reader=lambda follower: _positions_for())

    assert events == []
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'


def test_unclaimed_copy_position_is_reported_as_orphan(db):
    state = _state()

    events = reconcile.reconcile(
        state,
        db_path=db,
        positions_reader=lambda follower: _positions_for(position_id='pos-unknown', ticket=555),
        include_orphans=True,
    )

    assert [event.status for event in events] == ['skipped']
    assert 'Orphan' in events[0].message
    assert events[0].follower_position_id == '555'


def test_positions_from_other_software_are_not_reported_as_orphans(db):
    state = _state()

    events = reconcile.reconcile(
        state,
        db_path=db,
        positions_reader=lambda follower: [
            {'ticket': 111, 'symbol': 'XAUUSD.m', 'magic': 0, 'comment': ''},
            {'ticket': 222, 'symbol': 'XAUUSD.m', 'magic': 88888, 'comment': 'other-ea'},
        ],
        include_orphans=True,
    )

    assert events == []


def test_orphan_sweep_is_opt_in(db):
    state = _state()
    calls = []

    def reader(follower):
        calls.append(follower.id)
        return _positions_for(position_id='pos-unknown', ticket=555)

    events = reconcile.reconcile(state, db_path=db, positions_reader=reader)

    assert events == []
    assert calls == []


def test_reader_failure_is_reported_without_raising(db):
    _seed(db, status='confirmed')
    state = _state()

    def failing_reader(follower):
        raise RuntimeError('terminal not reachable')

    events = reconcile.reconcile(state, db_path=db, positions_reader=failing_reader)

    assert len(events) == 1
    assert 'terminal not reachable' in events[0].message
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'

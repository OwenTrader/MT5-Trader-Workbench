from python_service.app.local_copy_trading.engine import has_pending_work, process_tick
from python_service.app.local_copy_trading.models import Account, CopyRelationship, LocalCopyTradingState


def test_engine_fans_out_one_source_position_to_multiple_followers():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[
            Account(id='src-1', name='Main A'),
            Account(id='fol-1', name='Follower A'),
            Account(id='fol-2', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
            CopyRelationship(id='rel-2', source_account_id='src-1', follower_account_id='fol-2', symbol='XAUUSD'),
        ],
    )

    events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert len(events) == 2
    assert len(state.events) == 2


def test_engine_filters_by_source_account_and_symbol():
    state = LocalCopyTradingState(
        accounts=[Account(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )

    events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-2', 'symbol': 'XAUUSD'}])

    assert events == []


def test_engine_skips_inactive_relationships_and_followers():
    state = LocalCopyTradingState(
        accounts=[Account(id='fol-1', name='Follower A', is_active=False), Account(id='src-1', name='Main A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD', is_active=False)],
    )

    events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert events == []


def test_engine_deduplicates_already_copied_positions():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )

    first_events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])
    second_events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert len(first_events) == 1
    assert second_events == []


def test_engine_maps_source_symbol_to_follower_symbol():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[
            CopyRelationship(
                id='rel-1',
                source_account_id='src-1',
                follower_account_id='fol-1',
                symbol='XAUUSD',
                follower_symbol='XAUUSD.m',
            ),
        ],
    )

    events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert len(events) == 1
    assert events[0].symbol == 'XAUUSD.m'
    assert events[0].message == 'Mapped XAUUSD to XAUUSD.m'


def test_engine_records_follower_position_details_from_copy_executor():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}],
        execute_copy=lambda follower, relationship, position: (True, 'copied', 'fol-pos-1', 'fol-order-1'),
    )

    assert events[0].follower_position_id == 'fol-pos-1'
    assert events[0].follower_order_id == 'fol-order-1'


def test_engine_closes_copied_position_when_source_position_disappears():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )
    process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}],
        execute_copy=lambda follower, relationship, position: (True, 'copied', 'fol-pos-1', 'fol-order-1'),
    )

    events = process_tick(
        state,
        source_positions=[],
        execute_close=lambda follower, relationship, copied_event: (True, f'closed {copied_event.follower_position_id}'),
    )

    assert len(events) == 1
    assert events[0].status == 'closed'
    assert events[0].position_id == 'pos-1'
    assert events[0].follower_position_id == 'fol-pos-1'
    assert events[0].message == 'closed fol-pos-1'


def test_engine_does_not_close_same_copied_position_twice():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )
    process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])
    first_close = process_tick(state, source_positions=[])
    second_close = process_tick(state, source_positions=[])

    assert len(first_close) == 1
    assert first_close[0].status == 'closed'
    assert second_close == []


def test_engine_groups_copy_actions_by_follower_account():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[
            Account(id='src-1', name='Main'),
            Account(id='fol-a', name='Follower A'),
            Account(id='fol-b', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-a1', source_account_id='src-1', follower_account_id='fol-a', symbol='XAUUSD'),
            CopyRelationship(id='rel-b1', source_account_id='src-1', follower_account_id='fol-b', symbol='EURUSD'),
            CopyRelationship(id='rel-a2', source_account_id='src-1', follower_account_id='fol-a', symbol='GBPUSD'),
        ],
    )
    source_positions = [
        {'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'},
        {'position_id': 'pos-2', 'source_account_id': 'src-1', 'symbol': 'EURUSD'},
        {'position_id': 'pos-3', 'source_account_id': 'src-1', 'symbol': 'GBPUSD'},
    ]
    visited = []

    def fake_copy(follower, relationship, position):
        visited.append(follower.id)
        return True, 'ok', f"fp-{position['position_id']}", ''

    process_tick(state, source_positions, execute_copy=fake_copy)

    assert visited == ['fol-a', 'fol-a', 'fol-b']


def test_engine_groups_close_actions_by_follower_account():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[
            Account(id='src-1', name='Main'),
            Account(id='fol-a', name='Follower A'),
            Account(id='fol-b', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-a1', source_account_id='src-1', follower_account_id='fol-a', symbol='XAUUSD'),
            CopyRelationship(id='rel-b1', source_account_id='src-1', follower_account_id='fol-b', symbol='EURUSD'),
            CopyRelationship(id='rel-a2', source_account_id='src-1', follower_account_id='fol-a', symbol='GBPUSD'),
        ],
    )

    def fake_copy(follower, relationship, position):
        return True, 'ok', f"fp-{position['position_id']}", ''

    source_positions = [
        {'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'},
        {'position_id': 'pos-2', 'source_account_id': 'src-1', 'symbol': 'EURUSD'},
        {'position_id': 'pos-3', 'source_account_id': 'src-1', 'symbol': 'GBPUSD'},
    ]
    process_tick(state, source_positions, execute_copy=fake_copy)

    closed = []

    def fake_close(follower, relationship, copied_event):
        closed.append(follower.id)
        return True, 'closed'

    process_tick(state, [], execute_close=fake_close)

    assert closed == ['fol-a', 'fol-a', 'fol-b']


def _copied_state() -> LocalCopyTradingState:
    """A state that has already copied pos-1 once."""
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')
        ],
    )
    process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.1}],
    )
    return state


def test_engine_leaves_a_copied_position_alone_without_a_volume_reader():
    """Without a reader the engine cannot prove drift, so it must not guess."""
    state = _copied_state()

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.5}],
    )

    assert events == []


def test_engine_leaves_a_copied_position_alone_when_the_source_size_is_unchanged():
    state = _copied_state()

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.1}],
        recorded_volume=lambda relationship_id, position_id: 0.1,
    )

    assert events == []


def test_engine_resends_a_copied_position_when_the_source_size_moves():
    state = _copied_state()
    seen = []

    def fake_copy(follower, relationship, position):
        seen.append(position['volume'])
        return True, 'Resized', '789', '456'

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.4}],
        execute_copy=fake_copy,
        recorded_volume=lambda relationship_id, position_id: 0.1,
    )

    assert seen == [0.4]
    assert len(events) == 1


def test_engine_ignores_a_copied_position_with_no_recorded_volume():
    state = _copied_state()

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.4}],
        recorded_volume=lambda relationship_id, position_id: None,
    )

    assert events == []


def test_engine_records_a_guard_skip_as_its_own_status():
    from python_service.app.local_copy_trading.models import CopyResult

    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='Main A'), Account(id='fol-1', name='Follower A')],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')
        ],
    )

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.1}],
        execute_copy=lambda follower, relationship, position: CopyResult(False, 'skipped', 'limit reached'),
    )

    assert len(events) == 1
    assert events[0].status == 'skipped'
    assert events[0].message == 'limit reached'


# --- outstanding-work detection ---------------------------------------------


def test_has_pending_work_detects_a_close_still_owing():
    state = _copied_state()

    assert has_pending_work(state, []) is True


def test_has_pending_work_is_false_once_the_close_settled():
    state = _copied_state()
    process_tick(state, [], execute_close=lambda follower, relationship, copied_event: (True, 'closed'))

    assert has_pending_work(state, []) is False


def test_has_pending_work_is_false_when_the_source_size_matches():
    state = _copied_state()

    assert (
        has_pending_work(
            state,
            [{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.1}],
            recorded_volume=lambda relationship_id, position_id: 0.1,
        )
        is False
    )


def test_has_pending_work_is_true_when_the_source_size_moved():
    state = _copied_state()

    assert (
        has_pending_work(
            state,
            [{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.4}],
            recorded_volume=lambda relationship_id, position_id: 0.1,
        )
        is True
    )

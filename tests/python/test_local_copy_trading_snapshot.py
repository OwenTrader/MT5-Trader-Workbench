from python_service.app.local_copy_trading import source_adapter


def _position(**overrides):
    fields = {
        'position_id': 'pos-1',
        'source_account_id': 'src-1',
        'symbol': 'XAUUSD',
        'type': 0,
        'volume': 0.1,
        'sl': 0.0,
        'tp': 0.0,
    }
    fields.update(overrides)
    return fields


def test_signature_is_stable_for_the_same_positions():
    positions = [_position()]

    assert source_adapter.positions_signature(positions) == source_adapter.positions_signature(list(positions))


def test_signature_ignores_position_order():
    first = [_position(position_id='pos-1'), _position(position_id='pos-2')]
    second = [_position(position_id='pos-2'), _position(position_id='pos-1')]

    assert source_adapter.positions_signature(first) == source_adapter.positions_signature(second)


def test_signature_ignores_fields_that_do_not_affect_copying():
    without_extras = [_position()]
    with_extras = [_position(profit=12.5, price_open=2300.0, time=1700000000)]

    assert source_adapter.positions_signature(without_extras) == source_adapter.positions_signature(with_extras)


def test_signature_changes_when_a_position_is_opened():
    before = [_position()]
    after = [_position(), _position(position_id='pos-2')]

    assert source_adapter.positions_signature(before) != source_adapter.positions_signature(after)


def test_signature_changes_when_volume_changes():
    before = [_position(volume=0.1)]
    after = [_position(volume=0.2)]

    assert source_adapter.positions_signature(before) != source_adapter.positions_signature(after)


def test_signature_changes_when_a_protective_level_changes():
    before = [_position(sl=2290.0)]
    after = [_position(sl=2285.0)]

    assert source_adapter.positions_signature(before) != source_adapter.positions_signature(after)


def test_first_tick_always_processes():
    should_process, signature = source_adapter.should_process_tick(None, [_position()])

    assert should_process is True
    assert signature == source_adapter.positions_signature([_position()])


def test_unchanged_snapshot_skips_the_tick():
    _, signature = source_adapter.should_process_tick(None, [_position()])

    should_process, next_signature = source_adapter.should_process_tick(signature, [_position()])

    assert should_process is False
    assert next_signature == signature


def test_changed_snapshot_processes_the_tick():
    _, signature = source_adapter.should_process_tick(None, [_position()])

    should_process, _ = source_adapter.should_process_tick(signature, [_position(), _position(position_id='pos-2')])

    assert should_process is True


def test_an_empty_snapshot_after_a_position_closed_processes_the_tick():
    _, signature = source_adapter.should_process_tick(None, [_position()])

    should_process, next_signature = source_adapter.should_process_tick(signature, [])

    assert should_process is True
    assert next_signature == source_adapter.positions_signature([])

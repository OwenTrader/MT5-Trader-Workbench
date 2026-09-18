from python_service.app.local_copy_trading import position_ownership


def test_short_token_is_stable_and_eight_characters():
    first = position_ownership.short_token('relationship-1')
    second = position_ownership.short_token('relationship-1')

    assert first == second
    assert len(first) == 8


def test_short_token_distinguishes_inputs():
    assert position_ownership.short_token('pos-1') != position_ownership.short_token('pos-2')


def test_build_comment_stays_within_the_mt5_comment_limit():
    comment = position_ownership.build_comment('rel-1', 'pos-1')

    assert comment.startswith('lc:')
    assert len(comment) <= position_ownership.MAX_COMMENT_LENGTH
    assert len(comment) == 20


def test_build_comment_is_deterministic():
    assert position_ownership.build_comment('rel-1', 'pos-1') == position_ownership.build_comment('rel-1', 'pos-1')


def test_is_owned_position_matches_the_exact_position():
    payload = {
        'ticket': 789,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment('rel-1', 'pos-1'),
    }

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is True


def test_is_owned_position_rejects_a_manual_position():
    payload = {'ticket': 111, 'magic': 0, 'comment': position_ownership.build_comment('rel-1', 'pos-1')}

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is False


def test_is_owned_position_rejects_a_position_from_another_source_position():
    payload = {
        'ticket': 789,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment('rel-1', 'pos-2'),
    }

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is False


def test_is_owned_position_rejects_a_position_from_another_relationship():
    payload = {
        'ticket': 789,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment('rel-2', 'pos-1'),
    }

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is False


def test_is_owned_position_rejects_a_position_without_a_comment():
    payload = {'ticket': 789, 'magic': position_ownership.COPY_TRADING_MAGIC, 'comment': None}

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is False


def test_select_owned_position_ignores_other_positions_in_the_same_symbol():
    positions = [
        {'ticket': 111, 'symbol': 'XAUUSD', 'magic': 0, 'comment': ''},
        {'ticket': 222, 'symbol': 'XAUUSD', 'magic': 88888, 'comment': 'other-ea'},
        {
            'ticket': 789,
            'symbol': 'XAUUSD',
            'magic': position_ownership.COPY_TRADING_MAGIC,
            'comment': position_ownership.build_comment('rel-1', 'pos-1'),
        },
    ]

    owned = position_ownership.select_owned_position(positions, relationship_id='rel-1', position_id='pos-1')

    assert owned is not None
    assert owned['ticket'] == 789


def test_select_owned_position_returns_none_when_nothing_matches():
    positions = [
        {'ticket': 111, 'symbol': 'XAUUSD', 'magic': 0, 'comment': ''},
        {'ticket': 222, 'symbol': 'XAUUSD', 'magic': 88888, 'comment': 'other-ea'},
    ]

    assert position_ownership.select_owned_position(positions, relationship_id='rel-1', position_id='pos-1') is None

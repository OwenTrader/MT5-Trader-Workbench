from python_service.app.local_copy_trading import copy_trading_db


def _insert(db_path, client_key='rel-1:pos-1', **overrides):
    fields = {
        'client_key': client_key,
        'relationship_id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'source_position_id': 'pos-1',
        'created_at': '2026-09-18T00:00:00+00:00',
        'db_path': db_path,
    }
    fields.update(overrides)
    return copy_trading_db.insert_pending(**fields)


def test_insert_pending_records_an_intended_order(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)

    inserted = _insert(db)

    assert inserted is True
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'pending'
    assert record['follower_position_ticket'] == ''


def test_insert_pending_is_idempotent_for_the_same_client_key(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)

    first = _insert(db)
    second = _insert(db)

    assert first is True
    assert second is False


def test_confirm_order_records_the_follower_position(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    copy_trading_db.confirm_order(
        'rel-1:pos-1',
        follower_position_ticket='789',
        follower_order_id='456',
        message='Copied XAUUSD',
        updated_at='2026-09-18T00:00:01+00:00',
        db_path=db,
    )

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['follower_position_ticket'] == '789'
    assert record['follower_order_id'] == '456'


def test_confirm_order_keeps_existing_tickets_when_none_supplied(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)
    copy_trading_db.confirm_order(
        'rel-1:pos-1',
        follower_position_ticket='789',
        follower_order_id='456',
        updated_at='2026-09-18T00:00:01+00:00',
        db_path=db,
    )

    copy_trading_db.confirm_order('rel-1:pos-1', updated_at='2026-09-18T00:00:02+00:00', db_path=db)

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['follower_position_ticket'] == '789'
    assert record['follower_order_id'] == '456'


def test_mark_failed_records_the_reason(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    copy_trading_db.mark_failed(
        'rel-1:pos-1',
        message='Retcode: 10004',
        updated_at='2026-09-18T00:00:02+00:00',
        db_path=db,
    )

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'
    assert record['message'] == 'Retcode: 10004'


def test_list_open_records_excludes_settled_statuses(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db, client_key='rel-1:pos-1')
    _insert(db, client_key='rel-1:pos-2')
    _insert(db, client_key='rel-1:pos-3')
    copy_trading_db.mark_failed(
        'rel-1:pos-3', message='nope', updated_at='2026-09-18T00:00:03+00:00', db_path=db
    )

    open_keys = [record['client_key'] for record in copy_trading_db.list_open_records(db_path=db)]

    assert open_keys == ['rel-1:pos-1', 'rel-1:pos-2']


def test_delete_by_relationship_removes_only_that_relationship(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db, client_key='rel-1:pos-1', relationship_id='rel-1')
    _insert(db, client_key='rel-2:pos-1', relationship_id='rel-2')

    copy_trading_db.delete_by_relationship('rel-1', db_path=db)

    assert copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db) is None
    assert copy_trading_db.find_by_client_key('rel-2:pos-1', db_path=db) is not None


def test_a_new_record_starts_with_no_recorded_source_volume(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.0


def test_record_source_volume_round_trips(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.35, updated_at='2026-09-18T00:00:05+00:00', db_path=db
    )

    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.35


def test_recorded_volume_is_unknown_for_an_absent_pair(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)

    assert copy_trading_db.get_recorded_volume('rel-9', 'pos-9', db_path=db) is None


def test_a_marked_skip_is_not_an_open_record(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)
    copy_trading_db.mark_skipped(
        'rel-1:pos-1', message='limit reached', updated_at='2026-09-18T00:00:06+00:00', db_path=db
    )

    assert copy_trading_db.list_open_records(db_path=db) == []
    assert copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)['status'] == 'skipped'


def test_init_db_upgrades_a_database_written_before_source_volume_existed(tmp_path):
    """An install upgrading in place must not lose its existing order map."""
    db = tmp_path / 'legacy.db'
    copy_trading_db.connect(db).close()
    import sqlite3

    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE copy_order_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_key TEXT NOT NULL UNIQUE,
            relationship_id TEXT NOT NULL,
            source_account_id TEXT NOT NULL,
            follower_account_id TEXT NOT NULL,
            source_position_id TEXT NOT NULL,
            status TEXT NOT NULL,
            follower_position_ticket TEXT NOT NULL DEFAULT '',
            follower_order_id TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO copy_order_map (
            client_key, relationship_id, source_account_id, follower_account_id,
            source_position_id, status, created_at, updated_at
        ) VALUES ('rel-1:pos-1', 'rel-1', 'src-1', 'fol-1', 'pos-1', 'confirmed',
                  '2026-09-18T00:00:00+00:00', '2026-09-18T00:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    copy_trading_db.init_db(db)

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['source_volume'] == 0
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.2, updated_at='2026-09-18T00:00:07+00:00', db_path=db
    )
    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.2


def test_a_new_record_starts_with_no_recorded_source_volume(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.0


def test_record_source_volume_round_trips(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.35, updated_at='2026-09-18T00:00:05+00:00', db_path=db
    )

    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.35


def test_recorded_volume_is_unknown_for_an_absent_pair(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)

    assert copy_trading_db.get_recorded_volume('rel-9', 'pos-9', db_path=db) is None


def test_a_marked_skip_is_not_an_open_record(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)
    copy_trading_db.mark_skipped(
        'rel-1:pos-1', message='limit reached', updated_at='2026-09-18T00:00:06+00:00', db_path=db
    )

    assert copy_trading_db.list_open_records(db_path=db) == []
    assert copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)['status'] == 'skipped'


def test_init_db_upgrades_a_database_written_before_source_volume_existed(tmp_path):
    """An install upgrading in place must not lose its existing order map."""
    db = tmp_path / 'legacy.db'
    copy_trading_db.connect(db).close()
    import sqlite3

    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE copy_order_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_key TEXT NOT NULL UNIQUE,
            relationship_id TEXT NOT NULL,
            source_account_id TEXT NOT NULL,
            follower_account_id TEXT NOT NULL,
            source_position_id TEXT NOT NULL,
            status TEXT NOT NULL,
            follower_position_ticket TEXT NOT NULL DEFAULT '',
            follower_order_id TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO copy_order_map (
            client_key, relationship_id, source_account_id, follower_account_id,
            source_position_id, status, created_at, updated_at
        ) VALUES ('rel-1:pos-1', 'rel-1', 'src-1', 'fol-1', 'pos-1', 'confirmed',
                  '2026-09-18T00:00:00+00:00', '2026-09-18T00:00:00+00:00');
        """
    )
    connection.commit()
    connection.close()

    copy_trading_db.init_db(db)

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['source_volume'] == 0
    copy_trading_db.record_source_volume(
        'rel-1:pos-1', source_volume=0.2, updated_at='2026-09-18T00:00:07+00:00', db_path=db
    )
    assert copy_trading_db.get_recorded_volume('rel-1', 'pos-1', db_path=db) == 0.2

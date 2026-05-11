from python_service.app.services.quote_snapshot_service import append_quote_to_history, trim_price_history


def test_append_quote_to_history_adds_entry_for_symbol():
    history = {}

    append_quote_to_history(history, 'XAUUSD', 3300.5, 100.0)

    assert history == {'XAUUSD': [{'price': 3300.5, 'timestamp': 100.0}]}


def test_trim_price_history_keeps_only_recent_entries():
    history = {'XAUUSD': [{'price': 1, 'timestamp': 10}, {'price': 2, 'timestamp': 5000}]}

    trim_price_history(history, now_ts=5001, max_history_seconds=3600)

    assert history == {'XAUUSD': [{'price': 2, 'timestamp': 5000}]}

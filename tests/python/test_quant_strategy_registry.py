from python_service.app.quant.strategy_registry import get_strategy_module, list_strategies


def test_list_strategies_includes_builtin_strategy():
    strategies = list_strategies()

    assert any(item.id == 'sma_cross' for item in strategies)


def test_list_strategies_reads_user_strategy_directory(tmp_path, monkeypatch):
    strategies_dir = tmp_path / 'strategies'
    strategies_dir.mkdir()
    (strategies_dir / 'custom_breakout.py').write_text(
        """
STRATEGY_ID = 'custom_breakout'
STRATEGY_NAME = 'Custom Breakout'
STRATEGY_DESCRIPTION = 'User strategy.'
SUPPORTED_TIMEFRAMES = ['M5']
class Strategy: pass
""".strip(),
        encoding='utf-8',
    )
    monkeypatch.setenv('PYTHON_QUANT_STRATEGIES_DIR', str(strategies_dir))

    strategies = list_strategies()
    module = get_strategy_module('custom_breakout')

    assert any(item.id == 'custom_breakout' for item in strategies)
    assert module.STRATEGY_NAME == 'Custom Breakout'


def test_list_strategies_skips_invalid_user_strategy_file(tmp_path, monkeypatch):
    strategies_dir = tmp_path / 'strategies'
    strategies_dir.mkdir()
    (strategies_dir / 'broken_strategy.py').write_text(
        """
STRATEGY_ID = 'broken_strategy'
STRATEGY_NAME = 'Broken Strategy'
""".strip(),
        encoding='utf-8',
    )
    monkeypatch.setenv('PYTHON_QUANT_STRATEGIES_DIR', str(strategies_dir))

    strategies = list_strategies()

    assert all(item.id != 'broken_strategy' for item in strategies)

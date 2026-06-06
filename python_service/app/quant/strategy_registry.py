from dataclasses import dataclass
import importlib
import importlib.util
from pathlib import Path
import pkgutil
from types import ModuleType

from python_service.app.quant import strategies as builtin_strategies
from python_service.app.quant.paths import get_user_strategies_dir


@dataclass(frozen=True)
class StrategyDescriptor:
    id: str
    name: str
    description: str
    timeframes: list[str]
    module_path: str


def list_strategies() -> list[StrategyDescriptor]:
    items = [*load_builtin_strategies(), *load_user_strategies(get_user_strategies_dir())]
    return sorted(items, key=lambda item: item.id)


def load_builtin_strategies() -> list[StrategyDescriptor]:
    items: list[StrategyDescriptor] = []

    for module in pkgutil.iter_modules(builtin_strategies.__path__):
        imported = importlib.import_module(f'{builtin_strategies.__name__}.{module.name}')
        items.append(_build_descriptor(imported, imported.__name__))

    return items


def load_user_strategies(strategies_dir: Path) -> list[StrategyDescriptor]:
    if not strategies_dir.exists():
        return []

    items: list[StrategyDescriptor] = []
    for strategy_path in sorted(strategies_dir.glob('*.py')):
        if strategy_path.name.startswith('_'):
            continue
        try:
            imported = _load_module_from_path(strategy_path)
            items.append(_build_descriptor(imported, str(strategy_path.resolve())))
        except Exception as error:
            # Invalid user strategies should be skipped rather than breaking all quant menus.
            print(f'Skipping invalid user strategy {strategy_path}: {error}')

    return items


def get_strategy_module(strategy_id: str) -> ModuleType:
    for descriptor in list_strategies():
        if descriptor.id == strategy_id:
            if descriptor.module_path.endswith('.py'):
                return _load_module_from_path(Path(descriptor.module_path))
            return importlib.import_module(descriptor.module_path)

    raise ValueError(f'Unknown strategy: {strategy_id}')


def _build_descriptor(module: ModuleType, module_path: str) -> StrategyDescriptor:
    return StrategyDescriptor(
        id=module.STRATEGY_ID,
        name=module.STRATEGY_NAME,
        description=module.STRATEGY_DESCRIPTION,
        timeframes=list(module.SUPPORTED_TIMEFRAMES),
        module_path=module_path,
    )


def _load_module_from_path(module_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f'python_quant_user_strategy_{module_path.stem}', module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Unable to load strategy module: {module_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

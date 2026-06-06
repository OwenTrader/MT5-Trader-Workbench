from dataclasses import dataclass
import importlib
import pkgutil
from types import ModuleType

from python_service.app.quant import strategies as builtin_strategies


@dataclass(frozen=True)
class StrategyDescriptor:
    id: str
    name: str
    description: str
    timeframes: list[str]
    module_path: str


def list_strategies() -> list[StrategyDescriptor]:
    items: list[StrategyDescriptor] = []

    for module in pkgutil.iter_modules(builtin_strategies.__path__):
        imported = importlib.import_module(f'{builtin_strategies.__name__}.{module.name}')
        items.append(
            StrategyDescriptor(
                id=imported.STRATEGY_ID,
                name=imported.STRATEGY_NAME,
                description=imported.STRATEGY_DESCRIPTION,
                timeframes=list(imported.SUPPORTED_TIMEFRAMES),
                module_path=imported.__name__,
            )
        )

    return items


def get_strategy_module(strategy_id: str) -> ModuleType:
    for descriptor in list_strategies():
        if descriptor.id == strategy_id:
            return importlib.import_module(descriptor.module_path)

    raise ValueError(f'Unknown strategy: {strategy_id}')

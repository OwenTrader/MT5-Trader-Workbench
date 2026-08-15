# Python Quant Menu Split Spec

## Request

Split the current `Python Quant` area into two menus:

1. A menu focused on assigning MT5 accounts to strategies and showing the runtime status of each account/strategy assignment.
2. A menu focused on backtesting.

The user also asked:

- how the current strategy list is calculated
- how users can add new strategies

## Current Reality

- Strategy discovery is currently computed in `python_service/app/quant/strategy_registry.py` by scanning built-in modules under `python_service.app.quant.strategies`.
- `Python Quant` currently reuses the unified `LocalCopyTradingState.accounts` pool that is maintained through the `Account List` UI and `/local-copy-trading/accounts` backend routes.
- The current `Python Quant` page mixes live job assignment, runtime control, status display, and manual data backfill in one screen.
- There is no dedicated backtest menu or backtest API/UI yet.
- Users currently cannot add strategies from the UI; they would need code changes. This plan should make the strategy-addition path explicit and user-serviceable.

## Scope Decision

This plan covers one cohesive quant UX split with a minimal backtest feature:

- keep `Python Quant` as the live account/strategy assignment and runtime-status module
- add a new `Quant Backtest` module for historical testing against local cached MT5 data
- add a user strategy directory so non-core strategies can be dropped in without editing built-in package files

This plan does **not** include:

- parameter optimization grids
- advanced PnL visualization dashboards
- multi-account portfolio backtests
- strategy editor UI
- remote strategy marketplace or cloud sync

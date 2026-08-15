# MT5 Python Quant Module Spec

## Request

Consider integrating a quant module, preferably a mature open-source project on GitHub, and add a new Python quant menu.

The feature must let the user:

- choose an existing MT5 account
- choose a specific Python quant strategy
- run that strategy against the selected MT5 account
- handle how local market data is obtained and reused

## Constraints From Current Codebase

- The desktop app is Electron + React + FastAPI.
- MT5 account credentials already exist in `local-copy-trading` account storage.
- Python backend packaging uses `python_service/mt5_service.spec` with PyInstaller.
- Python tests run with `pytest tests/python`.
- Frontend tests run with `npm run test:frontend`.

## Scope Decision

This plan covers one cohesive subsystem: Python quant strategy orchestration for MT5 accounts, including local market-data caching and a renderer page to control jobs.

This plan intentionally does not include:

- a full research notebook workflow
- a browser-based backtest analytics UI
- cloud data-vendor integrations beyond local MT5 data
- generic plugin marketplace/distribution

Those should be follow-up plans if needed.

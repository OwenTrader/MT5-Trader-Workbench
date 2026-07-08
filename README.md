# MT5 Trader Workbench

[中文说明](./README.zh-CN.md)

MT5 Trader Workbench is a Windows-focused desktop trading assistant built with Electron, React, and a local FastAPI service. It connects to MetaTrader 5, provides real-time monitoring tools, and combines alerts, overlay display, order statistics, and technical analysis into a single workspace.

## Features

- Dashboard overview for MT5 connection status, balance, equity, profit, and margin level
- One-click actions to launch or reconnect MT5 and toggle the desktop quote overlay
- Real-time overlay window with live symbol quotes streamed over WebSocket
- Overlay customization for symbol list, font size, font color, pinning, and visibility
- Price alert management with create, edit, pause, resume, reset, and delete actions
- Common price alert templates that prefill the form without creating rules automatically
- Backend-side alert validation against current MT5 market price before saving price rules
- Volatility monitoring with configurable symbol, threshold, and time window
- Indicator alerts for technical conditions, including RSI-based rules
- Desktop notification and alert sound support for triggered monitoring events
- Order center with today, week, month, and daily review metrics
- Historical daily order statistics with selectable date ranges
- Lightweight Event Log that aggregates currently available local copy trading and order sync events
- Order Broadcast, Order Sync, and Local Copy Trading screens with explicit safety boundaries before enabling high-risk workflows
- Python Quant module for live MT5 account-strategy assignments, runtime status, manual market-data backfill, and shared strategy discovery
- Quant Backtest module for historical backtesting with the same MT5 account pool, shared strategy registry, and local cached market data
- Data Management module to sync and store historical MT5 K-line data locally
- Trading Review module for manual historical paper-trading with playback controls
- Technical analysis entry that generates a report and opens it in the default browser
- Full i18n support with seamless switching between English and Chinese
- Settings management for MT5 path, theme, interface language, auto-connect, refresh interval, overlay options, sound options, DingTalk, WeCom, and Feishu bot credentials
- Configuration migration guidance and sensitive-information handling notes for local settings, API keys, and webhook tokens
- System tray integration with quick actions for showing the main window, toggling the overlay, and quitting the app
- Single-instance desktop behavior with hide-to-tray window lifecycle
- Local FastAPI backend for health checks, settings persistence, MT5 integration, alerts, notifications, history, overlay state, and streaming
- Frontend unit tests with Vitest and Electron smoke testing with Playwright

## Modules

- `Dashboard`: workspace summary and quick controls
- `Price Alerts`: threshold-based market alerts
- `Volatility`: rapid-move monitoring rules
- `Indicator Alerts`: technical indicator conditions
- `Risk Control`: account and threshold form area
- `Order Center`: performance overview and daily statistics
- `Technical Analysis`: one-click report generation flow
- `Order Broadcast`: notification-only order broadcast rules
- `Order Sync`: MT5 to TopStep synchronization configuration and sync records
- `Account List`: shared MT5 account registry used by independent-account workflows
- `Local Copy Trading`: source/follower account relationships and recent copy events
- `Data Management`: local MT5 history data synchronization and storage
- `Trading Review`: historical manual paper-trading environment with playback
- `Python Quant`: live Python strategy assignments with runtime controls, manual backfill, local SQLite market-data cache, and a user strategy directory
- `Quant Backtest`: historical backtests that reuse the same account pool, strategy list, and cached market data
- `Event Log`: currently available recent event context from sync-related modules
- `Settings`: connection, display, notifications, and product information

## Tech Stack

- Electron
- React
- TypeScript
- Vite
- Tailwind CSS
- Zustand
- FastAPI
- Uvicorn
- Pydantic
- MetaTrader5 Python SDK
- Vitest
- Playwright

## Project Structure

```text
.
|-- src/
|   |-- main/                # Electron main process
|   |-- preload/             # Electron preload bridge
|   `-- renderer/src/        # React renderer UI
|-- python_service/
|   `-- app/                 # FastAPI routes, models, and services
|-- resources/               # Icons and audio assets
|-- tests/                   # Electron tests
`-- docs/                    # Internal planning and notes
```

## Development

Install Node.js dependencies:

```bash
npm install
```

Install Python backend dependencies, including `PyInstaller` for Windows packaging:

```bash
python -m pip install -r python_service/requirements.txt
```

Start the desktop app in development mode:

```bash
npm run dev
```

The project also includes a Python backend in `python_service/`. The Electron main process starts the local backend service and waits for it to become healthy on port `8765`.

## Scripts

- `npm run dev`: start the Electron + Vite development workflow
- `npm run build`: build the application
- `npm run build:python`: rebuild `python_service/dist/mt5_service/mt5_service.exe` with `python -m PyInstaller`
- `npm run verify:packaging`: verify the backend directory, `mt5_service.exe`, bundled `_internal` runtime files, and the Electron resource path before Windows packaging
- `npm run package:win`: rebuild Electron, rebuild the Python backend, verify packaging inputs, auto-increment the local build number, then create a Windows installer like `MT5 Trader Workbench Setup 1.0.0.1.exe`. The packaging script uses a repo-local `electron-builder` cache under `.cache/electron-builder`, and pre-seeds `winCodeSign` and `nsis` from `C:\Users\Administrator\AppData\Local\electron-builder\Cache` when available so packaging tools are reused locally instead of being downloaded again.
- `npm run test:frontend`: run frontend tests
- `npm run test:electron`: run Electron smoke tests
- `npm run test`: run all configured tests

Run Python backend tests directly with:

```bash
pytest tests/python
```

Use only `python_service/mt5_service.spec` for backend packaging. Do not build from the deprecated root `mt5_service.spec`.
The local packaging counter is stored in `.build-version.json` and is ignored by git.

## Backend Endpoints

The bundled local backend currently exposes routes for:

- health checks
- settings load and save
- MT5 status, launch, account, positions, and path verification
- price, volatility, and indicator alert CRUD
- notification test endpoints
- historical overview and daily statistics
- overlay status and import/export
- technical analysis report generation
- overlay quote streaming over WebSocket
- order sync configuration and runtime records
- local copy trading configuration and recent events
- local database management for historical K-line data and trading review sessions
- python quant overview, live job lifecycle control, and local market-data backfill
- quant backtest strategy listing and backtest execution

## Python Quant And Backtest Notes

- `Account List` is the shared source of MT5 accounts for both `Python Quant` live assignments and `Quant Backtest` runs.
- `Python Quant` is limited to live assignment management, runtime status, start/stop controls, and manual market-data backfill.
- `Quant Backtest` is the historical-testing entry and does not mutate live quant jobs.
- Local market data is cached in `storage/python_quant/market_data.sqlite3`.
- Quant jobs are persisted in `storage/python_quant/jobs.json`.
- Built-in strategies are loaded from `python_service/app/quant/strategies/`.
- User-added strategies are discovered from `storage/python_quant/strategies/` in development and from the packaged app's user data `storage/python_quant/strategies/` directory after installation.
- `Python Quant` and `Quant Backtest` use the same merged strategy list from the built-in and user strategy directories.
- Each user strategy file must define `STRATEGY_ID`, `STRATEGY_NAME`, `STRATEGY_DESCRIPTION`, `SUPPORTED_TIMEFRAMES`, and `Strategy`.
- The first built-in strategy is `sma_cross`, and the packaged backend includes the built-in strategy module.
- Python tests remain `pytest tests/python` even after adding the quant module.

## Notes

- The application is designed around a local MT5 environment and Windows desktop usage.
- Trading-related automation screens include safety notices because notification and sync behavior can be misunderstood as execution guarantees.
- `Event Log` is a lightweight view of currently available renderer/backend data, not a complete persisted audit log.
- Settings import/export for full application configuration is not implemented yet; the Settings page documents manual migration paths instead of exposing inactive behavior.

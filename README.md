# MT5 Trader Workbench

[中文说明](./README.zh-CN.md)

MT5 Trader Workbench is a Windows-focused desktop trading assistant built with Electron, React, and a local FastAPI service. It connects to MetaTrader 5, provides real-time monitoring tools, and combines alerts, overlay display, order statistics, and technical analysis into a single workspace.

## Features

- Dashboard overview for MT5 connection status, balance, equity, profit, and margin level
- One-click actions to launch or reconnect MT5 and toggle the desktop quote overlay
- Real-time overlay window with live symbol quotes streamed over WebSocket
- Overlay customization for symbol list, font size, font color, pinning, and visibility
- Price alert management with create, edit, pause, resume, reset, and delete actions
- Backend-side alert validation against current MT5 market price before saving price rules
- Volatility monitoring with configurable symbol, threshold, and time window
- Indicator alerts for technical conditions, including RSI-based rules
- Desktop notification and alert sound support for triggered monitoring events
- Order center with today, week, and month P&L summaries
- Historical daily order statistics with selectable date ranges
- Technical analysis entry that generates a report and opens it in the default browser
- Settings management for MT5 path, theme, interface language, auto-connect, refresh interval, overlay options, sound options, and DingTalk bot credentials
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
- `Settings`: application, overlay, sound, and bot configuration
- `Order Broadcast`: reserved in the UI and currently marked as in progress

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

## Notes

- The application is designed around a local MT5 environment and Windows desktop usage.
- Some sections in the UI are intentionally lightweight at this stage, such as `Risk Control`.
- `Order Broadcast` is visible in the navigation but is not finished yet.

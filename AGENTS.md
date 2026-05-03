# AGENTS.md

## Use These Commands

- `npm run dev` is the real full-app dev entrypoint. It runs the Electron app through `electron-vite` and is the command to use for normal development.
- `npm run build` is the real app build. It produces `out/main`, `out/preload`, and `out/renderer` via `electron-vite`.
- `npm run test:frontend` runs all Vitest tests matched under `src/**/*.{test,spec}.*`. This includes renderer tests and Node-environment tests in `src/main`.
- `npm run test:electron` only runs `tests/e2e/app-launch.spec.ts`, and that spec launches `out/main/index.js`. Build first with `npm run build` or the smoke test will not have the compiled Electron app.
- Python tests are present under `tests/python`, but they are not wired into `npm test`. Run them directly with `pytest tests/python` when changing `python_service` code.
- There are no repo scripts for linting or TypeScript typechecking. Do not invent `npm run lint` or `npm run typecheck` steps in this repo.

## Architecture

- The app is a Windows-focused Electron desktop app with a local FastAPI backend.
- Electron main entrypoint: `src/main/index.ts`.
- Preload bridge: `src/preload/index.ts`.
- React renderer root: `src/renderer/src/main.tsx`.
- FastAPI app entrypoint: `python_service/app/main.py`.
- In development, Electron starts the backend with `python -m python_service.app.main` and waits for `http://127.0.0.1:8765/health`.
- The renderer talks to the backend directly on `http://127.0.0.1:8765`; many stores hardcode that base URL.
- Renderer routing uses `HashRouter`. The overlay window is the `#/overlay-display` route, not a separate renderer app.

## Paths And Config Quirks

- Treat `@` as the renderer alias for `src/renderer/src`. That mapping is defined in `electron.vite.config.ts`, `vitest.config.ts`, and `tsconfig.json`.
- `vite.config.ts` at the repo root does not match the Electron renderer layout (`@` points at `./src`). Prefer the `electron-vite` flow unless you are intentionally working on the standalone Vite commands.
- Renderer tests use `jsdom` with setup file `src/renderer/src/test/setup.ts`.
- Node-side Vitest files in `src/main` opt into the Node environment with `// @vitest-environment node`.
- For page UI work, use `shadcn/ui` components by default. Avoid raw HTML elements or hand-rolled base UI components unless there is a concrete reason an existing `shadcn/ui` component cannot cover the need.

## Settings And Storage

- In development, settings come from `storage/settings.local.json` if it exists; otherwise the app falls back to `storage/settings.default.json`.
- In packaged builds, Electron copies `storage/settings.default.json` into the user data directory as `storage/settings.json` on first run.
- The backend receives settings paths through `SETTINGS_FILE` and `DEFAULT_SETTINGS_FILE` environment variables from `src/main/python-service.ts`. Keep Electron and backend settings-path behavior aligned when changing config loading.
- `storage/alerts.json` and `storage/overlay_config.json` are runtime data/config files used by backend features. Treat edits to these files as app-state changes unless the task explicitly targets seeded storage data.

## Packaging

- Use only `python_service/mt5_service.spec` for backend packaging. `README.md` explicitly marks the root-level spec as deprecated.
- `npm run package:win` already enforces the required order: `build` -> `build:python` -> `verify:packaging` -> `scripts/package-win.cjs`.
- `npm run verify:packaging` is not optional busywork: it verifies the packaged backend directory, `mt5_service.exe`, bundled `_internal` runtime files, required awakening scripts, help files, and `package.json` `extraResources` paths.
- Windows packaging uses a repo-local `electron-builder` cache under `.cache/electron-builder` and may reuse local `winCodeSign`/`nsis` tools from `C:\Users\Administrator\AppData\Local\electron-builder\Cache`.
- Windows installer build numbers are tracked in `.build-version.json`, which is generated locally and ignored by git.

## Existing Test Coverage Gaps

- `npm test` does not cover the Python test suite. If you touch `python_service/app/**`, run `pytest tests/python` in addition to the npm tests you need.

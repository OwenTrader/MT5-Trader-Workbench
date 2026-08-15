# Encrypted Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real "encrypt before packaging" flow for the Electron desktop app so the packaged installer no longer ships the renderer bundle and Python backend in directly readable form.

**Architecture:** Adjust the existing Windows packaging pipeline from `build` -> `build:python` -> `verify:packaging` -> `scripts/package-win.cjs` to a secure pipeline of `build` -> `build:python` -> `prepare-secure-package` -> `verify:packaging` -> `scripts/package-win.cjs`. The secure staging step must run before verification so verification can inspect the encrypted payloads that will actually be packaged. Use a staged secure input tree that contains an encrypted full renderer payload and an encrypted Python backend payload, plus a small runtime bootstrap in Electron main that extracts/decrypts both into a controlled runtime directory before any packaged windows or backend process are started.

**Tech Stack:** Electron, electron-vite, electron-builder, Node.js crypto, PowerShell verification scripts, PyInstaller, Windows installer packaging.

---

## File Map

- Modify: `package.json`
  Purpose: add secure packaging scripts and any builder config needed for encrypted resources.
- Modify: `scripts/package-win.cjs`
  Purpose: switch packaging input to the encrypted staging directory and preserve build-number/output behavior.
- Modify: `scripts/verify-packaging.ps1`
  Purpose: verify the secure staged backend payload instead of only the plain `python_service/dist/mt5_service` layout.
- Create: `scripts/prepare-secure-package.cjs`
  Purpose: orchestrate secure staging, call encryption helpers, and assemble the files that `electron-builder` will package.
- Create: `scripts/encrypt-renderer-assets.cjs`
  Purpose: archive and encrypt the entire renderer output tree and emit a manifest describing how the app should load/decrypt it.
- Create: `scripts/encrypt-python-backend.cjs`
  Purpose: transform the PyInstaller output into an encrypted payload plus manifest for packaged runtime extraction.
- Create: `scripts/shared/secure-package-constants.cjs`
  Purpose: hold shared directory names, manifest filenames, and environment-variable names used by packaging scripts.
- Modify: `src/main/index.ts`
  Purpose: register secure protocol or bootstrap logic so packaged builds can load encrypted renderer assets.
- Modify: `src/main/overlay-window.ts`
  Purpose: load the secure extracted renderer entry for the overlay window too.
- Modify: `src/main/python-service.ts`
  Purpose: decrypt/extract the packaged backend payload before spawning the backend executable.
- Modify: `src/main/packaging-paths.ts`
  Purpose: resolve packaged secure backend staging/extraction paths.
- Modify: `src/main/packaging-paths.test.ts`
  Purpose: cover new secure packaged paths.
- Modify: `src/main/python-service.test.ts`
  Purpose: cover runtime extraction/decryption startup behavior.
- Create: `src/main/secure-packaging.ts`
  Purpose: runtime helpers for reading the packaged manifest, deriving the key, decrypting payloads, and extracting files.
- Create: `src/main/secure-packaging.test.ts`
  Purpose: test manifest parsing, path handling, and failure cases.
- Modify: `README.md`
  Purpose: document secure packaging commands, required secrets, and output expectations.
- Modify: `README.zh-CN.md`
  Purpose: document the same secure packaging flow in Chinese.

## Key Design Decisions

1. **Define “encrypted” precisely**

This repo does not currently have a real encryption layer. `asar` is packaging/archival, not security. The implementation must encrypt payload bytes before they are handed to `electron-builder`.

2. **Use a staged secure build, not in-place mutation**

Do not overwrite `out/` or `python_service/dist/mt5_service/`. Generate a separate staging tree so existing dev/test/build flows remain stable.

3. **Protect both payload classes**

- Renderer protection: the full `out/renderer/**` tree, including `index.html`, JS, CSS, and static assets.
- Backend protection: `python_service/dist/mt5_service/**`.

If only one side is protected, the app is only partially encrypted.

4. **Accept the real threat model**

Because the desktop app must run locally, any shipped key material can be extracted by a determined reverse engineer. This plan improves casual/source-level extraction resistance; it does not claim DRM-grade protection.

5. **Start with a pragmatic v1**

Use AES-256-GCM with a build-time secret provided externally. During secure staging, derive one runtime decryption key from that build-time secret, store only the obfuscated runtime-key descriptor, and encrypt all packaged payloads with that derived runtime key. Do not add a remote license server in v1.

## Required Secret Contract

- Build-time secret env var: `APP_PACKAGE_ENCRYPTION_KEY`
- Format: base64 or hex, normalized to 32 bytes inside the script
- Packaging commands must fail hard if the key is missing in secure mode
- The secret must not be committed to the repo or written to generated docs/logs

## Runtime Key Contract

The packaged app must also be able to decrypt at runtime. For this repo, v1 must make that explicit instead of leaving decryption undefined.

Recommended v1 contract:

- Build derives the single runtime decryption key from `APP_PACKAGE_ENCRYPTION_KEY` and then encrypts all staged packaged payloads with that derived runtime key.
- Build injects an obfuscated runtime key descriptor into packaged metadata.
- Runtime reconstructs the AES key from:
  - one packaged descriptor fragment,
  - one hardcoded fragment in main-process code,
  - one deterministic salt persisted into the packaged manifest.
- The packaged descriptor lives in a staged manifest file such as `resources/secure/runtime-key.json` inside the packaged app resources.
- The hardcoded fragment lives in `src/main/secure-packaging.ts` and is split across constants rather than stored as one literal.
- The deterministic salt is written during secure staging into `resources/secure/runtime-key.json` as `buildVersion` and `buildNumber` so the packaged app can read it at runtime.
- Reconstruction order for v1 is fixed and documented: decode packaged fragment -> concatenate hardcoded fragment -> append hash of `buildVersion:buildNumber` -> derive final 32-byte runtime key via SHA-256.

This is not DRM-grade protection, but it is executable for an offline desktop app and materially stronger than shipping plain files.

Alternative stronger options for later:

- fetch runtime key from an operator-controlled service after auth/license validation
- derive from Windows DPAPI-protected material stored at install or first run

## Runtime Loading Strategy

### Renderer

- Do not encrypt only selected JS files in v1.
- Encrypt and package the entire `out/renderer` tree as one archive payload.
- On packaged startup, decrypt/extract that archive into the runtime directory before any call to `loadFile(...)`.
- Update both `src/main/index.ts` and `src/main/overlay-window.ts` to load the extracted renderer `index.html` in packaged secure mode.

Recommended v1: full renderer tree extraction, because it matches the current `electron-vite` output and avoids partially rewriting HTML/asset references.

### Python backend

- Package an encrypted archive of `python_service/dist/mt5_service`.
- On packaged startup, decrypt it into a versioned runtime directory under `app.getPath('userData')` or a temp subdirectory.
- Update `getPackagedBackendWorkingDirectory()` and `getPackagedBackendExecutablePath()` to point to the extracted runtime directory, not `process.resourcesPath/mt5_service`.
- Keep settings/help/tray icon paths unchanged unless they are explicitly brought into the secure flow.

### Startup sequencing

- Add one explicit async packaged-startup preparation step before:
  - `mainWindow.loadFile(...)`
  - overlay packaged `loadFile(...)`
  - `startPythonService()` in packaged mode

- That preparation step must:
  - resolve runtime key material
  - verify secure manifests
  - extract/decrypt renderer payload if missing or stale
  - extract/decrypt backend payload if missing or stale
  - return extracted renderer root and backend root paths

This is not just a path-helper change; startup flow becomes explicitly async.

## Secure Builder Config Strategy

`electron-builder` currently reads `build.files` and `build.extraResources` from `package.json`, while `scripts/package-win.cjs` only overrides `directories.output`. Secure mode therefore needs a deliberate config override.

Recommended v1:

- Generate a temporary builder config JSON inside the secure staging directory.
- Base it on `package.json.build`, but override:
  - `files` to point at the secure Electron app input
  - `extraResources` to point at encrypted backend payloads/manifests and any still-plain resources
- Pass that config to `electron-builder` from `scripts/package-win.cjs` only in secure mode.

Do not rely on mutating only `directories.output`; that is insufficient.

## Secure Packaging Order

The secure flow must change script order, not just add files.

Required v1 script order:

- `npm run build`
- `npm run build:python`
- `node scripts/prepare-secure-package.cjs`
- `npm run verify:packaging`
- `node scripts/package-win.cjs --secure`

Implementation requirement:

- `verify:packaging` must detect secure mode and validate the staged encrypted inputs rather than only the plain `python_service/dist/mt5_service` layout.
- `package:win:secure` must call `prepare-secure-package` before `verify:packaging`.

## Task 1: Add secure packaging design primitives

**Files:**
- Create: `scripts/shared/secure-package-constants.cjs`
- Create: `src/main/secure-packaging.ts`
- Create: `src/main/secure-packaging.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- manifest parsing rejects missing or malformed fields
- key normalization accepts only valid 32-byte secrets
- extraction target paths stay inside the intended runtime directory

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/main/secure-packaging.test.ts`
Expected: FAIL because the module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement:
- constants for secure staging directory names and manifest filenames
- manifest TypeScript types and validators
- key normalization helper using Node crypto-safe parsing
- safe path join/extraction guard helpers

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- src/main/secure-packaging.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/shared/secure-package-constants.cjs src/main/secure-packaging.ts src/main/secure-packaging.test.ts
git commit -m "feat: add secure packaging primitives"
```

## Task 2: Build encrypted staging for renderer and backend

**Files:**
- Create: `scripts/prepare-secure-package.cjs`
- Create: `scripts/encrypt-renderer-assets.cjs`
- Create: `scripts/encrypt-python-backend.cjs`
- Modify: `package.json`
- Modify: `scripts/verify-packaging.ps1`

- [ ] **Step 1: Write the failing verification cases**

Define checks for:
- missing `APP_PACKAGE_ENCRYPTION_KEY` fails secure packaging
- secure staging directory is created with encrypted manifests/blobs
- plain backend directory is not used directly by secure packaging verification

- [ ] **Step 2: Create the secure prepare script skeleton and run it to verify key enforcement fails**

Run: `node scripts/prepare-secure-package.cjs`
Expected: FAIL with a clear missing-key error after the script exists but before full staging is implemented.

- [ ] **Step 3: Write minimal implementation**

Implement:
- a secure staging root such as `.secure-package/`
- full renderer tree archiving/encryption into payload plus manifest
- backend directory archiving/encryption into blob file plus manifest
- package scripts such as `package:win:secure`
- verification updates that assert secure payload presence and reject misaligned source paths
- secure-mode ordering so staging runs before verification

- [ ] **Step 4: Run secure staging with a test key**

Run: `pwsh -NoProfile -Command "$env:APP_PACKAGE_ENCRYPTION_KEY='REPLACE_WITH_32_BYTE_TEST_KEY_BASE64'; node scripts/prepare-secure-package.cjs"`
Expected: PASS and emits the secure staging tree without leaking plain payload copies beyond the controlled staging inputs.

- [ ] **Step 5: Commit**

```bash
git add package.json scripts/prepare-secure-package.cjs scripts/encrypt-renderer-assets.cjs scripts/encrypt-python-backend.cjs scripts/verify-packaging.ps1
git commit -m "feat: stage encrypted packaging payloads"
```

## Task 3: Load encrypted payloads at packaged runtime

**Files:**
- Modify: `src/main/index.ts`
- Modify: `src/main/overlay-window.ts`
- Modify: `src/main/python-service.ts`
- Modify: `src/main/packaging-paths.ts`
- Modify: `src/main/packaging-paths.test.ts`
- Modify: `src/main/python-service.test.ts`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- packaged backend path resolution points to extracted runtime directory in secure mode
- startup fails with actionable diagnostics when encrypted backend payload is missing or key derivation fails
- packaged renderer startup chooses decrypted/extracted full renderer tree instead of raw `process.resourcesPath` assets
- overlay window packaged startup also uses the extracted renderer entry

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/main/packaging-paths.test.ts src/main/python-service.test.ts`
Expected: FAIL because secure-mode behavior is not implemented.

- [ ] **Step 3: Write minimal implementation**

Implement:
- packaged runtime extraction directory management
- idempotent decrypt/extract on app startup
- startup diagnostics for secure payload failures
- main-process loading of extracted renderer directory for both main and overlay windows
- async startup preparation before window creation and backend spawn

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- src/main/packaging-paths.test.ts src/main/python-service.test.ts src/main/secure-packaging.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/main/index.ts src/main/overlay-window.ts src/main/python-service.ts src/main/packaging-paths.ts src/main/packaging-paths.test.ts src/main/python-service.test.ts
git commit -m "feat: load encrypted packaged payloads"
```

## Task 4: Wire secure installer packaging end-to-end

**Files:**
- Modify: `scripts/package-win.cjs`
- Modify: `package.json`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Add failing dry-run expectation**

Define a dry-run path that prints:
- secure mode enabled
- secure staging directory
- output installer directory
- whether encryption key was supplied

- [ ] **Step 2: Run the dry-run secure package command**

Run: `pwsh -NoProfile -Command "$env:APP_PACKAGE_ENCRYPTION_KEY='REPLACE_WITH_32_BYTE_TEST_KEY_BASE64'; npm run package:win:secure -- --dry-run"`
Expected: FAIL or incomplete output before the secure wiring is added.

- [ ] **Step 3: Write minimal implementation**

Implement:
- `package:win:secure` and optional `package:win:secure:debug`
- secure-mode generation and handoff of temporary builder config to `electron-builder`
- `package:win:secure` script order of `build` -> `build:python` -> `prepare-secure-package` -> `verify:packaging` -> package
- clear README instructions for secret handling and artifact locations

- [ ] **Step 4: Run the end-to-end secure package flow**

Run: `pwsh -NoProfile -Command "$env:APP_PACKAGE_ENCRYPTION_KEY='REPLACE_WITH_32_BYTE_TEST_KEY_BASE64'; npm run package:win:secure"`
Expected: PASS and produces a Windows installer under `dist/<buildVersion>/` using encrypted packaged payloads.

- [ ] **Step 5: Smoke-test secure package outputs correctly**

Run:
1. `npm run build`
2. `pwsh -NoProfile -Command "$env:APP_PACKAGE_ENCRYPTION_KEY='REPLACE_WITH_32_BYTE_TEST_KEY_BASE64'; npm run package:win:secure"`
3. Manually launch `dist/<buildVersion>/win-unpacked/*.exe`
4. Optionally run the installed app from the generated installer

Verify:
- main window loads successfully
- overlay window opens successfully
- backend starts and `/health` returns 200
- runtime extraction directory contains decrypted renderer/backend payloads
- packaged app no longer depends on plain `process.resourcesPath/mt5_service` payloads

Note: `npm run test:electron` in this repo only smoke-tests the built Electron app from `out/main/index.js`; it does not validate the packaged installer.

- [ ] **Step 6: Commit**

```bash
git add scripts/package-win.cjs package.json README.md README.zh-CN.md
git commit -m "feat: add secure windows packaging flow"
```

## Verification Checklist

- `npm run build`
- `npm run build:python`
- `pwsh -NoProfile -Command "$env:APP_PACKAGE_ENCRYPTION_KEY='REPLACE_WITH_32_BYTE_TEST_KEY_BASE64'; node scripts/prepare-secure-package.cjs"`
- `npm run test:frontend -- src/main/secure-packaging.test.ts src/main/packaging-paths.test.ts src/main/python-service.test.ts`
- `pwsh -NoProfile -Command "$env:APP_PACKAGE_ENCRYPTION_KEY='REPLACE_WITH_32_BYTE_TEST_KEY_BASE64'; npm run package:win:secure -- --dry-run"`
- `pwsh -NoProfile -Command "$env:APP_PACKAGE_ENCRYPTION_KEY='REPLACE_WITH_32_BYTE_TEST_KEY_BASE64'; npm run package:win:secure"`
- manual launch of `dist/<buildVersion>/win-unpacked/*.exe`

## Locked V1 Decisions

1. **Secret source**

- CI/operator manually injects `APP_PACKAGE_ENCRYPTION_KEY` at build time.
- The packaged app ships an obfuscated runtime derivative sufficient for offline decryption.
- The clear build-time secret is never written into the repo.

2. **Renderer protection scope**

- Encrypt the entire `out/renderer` tree as one archive payload.

3. **Runtime decryption location**

- Extract to `app.getPath('userData')/runtime-secure`.

4. **Backend payload format**

- Encrypt one archive of `mt5_service/`, not file-by-file.

Recommended v1 choices already locked by this plan:
- external env var secret plus shipped obfuscated runtime derivative
- encrypt the entire renderer tree + backend payload, leave help/settings/icon plain
- extract to `app.getPath('userData')/runtime-secure`
- encrypt one backend archive rather than file-by-file

## Risks

- Shipping a local decryptable desktop app cannot prevent determined reverse engineering.
- Renderer extraction to disk leaves decrypted bytes on the client machine during runtime.
- PyInstaller output is large; extraction time may slow first launch.
- Antivirus software may react to runtime self-extraction if paths and signing are not handled carefully.

## Out Of Scope For V1

- Remote license server or online key escrow
- Kernel/driver-level anti-debugging
- Code virtualization/packer products
- Full DRM guarantees

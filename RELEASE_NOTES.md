# Release Notes

## Product Optimization Branch

Branch: `product-optimization-p0`

This branch focuses on product trust, workflow clarity, and release readiness for MT5 Trader Workbench. It does not introduce new backend APIs or new dependencies.

## User-Facing Changes

- Added stronger safety boundaries for high-risk trading workflows, including order sync, order broadcast, local copy trading, and risk control flows.
- Added confirmation before enabling order sync and before deleting price alerts.
- Added a Dashboard running status center that summarizes MT5, overlay, alert, notification, sound, and order sync state.
- Improved Risk Control loading, validation, save-state, and error feedback.
- Improved Price Alerts so new rules start with an empty target price, require valid symbol and price input, and keep backend validation before save.
- Added common price-alert templates that fill the form but never create rules automatically.
- Added Order Center review metrics based on daily statistics.
- Reworked Settings labels into Connection, Display, Notifications, and About.
- Added notification-channel status for DingTalk, WeCom, and Feishu.
- Added configuration migration guidance and sensitive-information handling notes in Settings.
- Grouped sidebar navigation into monitoring, review, automation, and system areas.
- Added Event Log for currently available recent events from local copy trading and order sync.
- Updated built-in user guides and README files to reflect the optimized product flows.

## Important Boundaries

- Event Log is a lightweight recent-event view. It is not a complete persisted audit log.
- Order Broadcast sends notifications only. It does not create, modify, or close trades.
- Order Sync and Local Copy Trading must be treated as high-risk workflows. Users should verify account credentials, symbols, contract mappings, and lot multipliers before enabling them.
- Full application settings import/export is not available yet. The Settings page exposes guidance and disabled actions instead of pretending the feature exists.
- Sensitive values such as MT5 credentials, TopStep API keys, and bot webhook/token values should be protected in screenshots, logs, and shared configuration files.

## Validation Checklist

- `npm run test:frontend`
- `npm run build`
- `npm run dev` manual smoke check:
  - Dashboard status center loads and still handles backend unavailable states.
  - Sidebar groups and routes work, including Event Log.
  - Price alert templates fill the form but do not save until the user clicks Add Alert.
  - Order Center review metrics display from daily history data.
  - Settings tabs show Connection, Display, Notifications, and About.
  - About tab shows configuration migration and sensitive-information notes.
  - Order Sync and Local Copy Trading safety confirmations remain visible before enable actions.

## Recommended Next Step

Run a real Electron manual smoke test with `npm run dev`. If the manual check passes, open a pull request or merge this branch into the release branch.

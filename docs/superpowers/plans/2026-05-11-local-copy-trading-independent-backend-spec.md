# Local Copy Trading Independent Backend In-App Module Spec

## Summary

Implement a new left-sidebar menu item named `本地跟单` / `Local Copy Trading` that opens an in-app page inside the existing Electron workbench. This feature must use a brand-new backend package and must not reuse the existing MT5 backend or the existing order-sync backend.

## Required Behavior

1. Clicking the new sidebar item must navigate to an in-app module route inside the existing Electron `HashRouter` workbench view.
2. The route must resolve through the existing module-routing convention as `#/local-copy-trading`.
3. The page UI must use existing `shadcn/ui` components already present in this repo wherever possible.
4. Non-essential custom styles and custom base UI components are not allowed.
5. The feature must introduce a new backend package at `python_service/app/local_copy_trading/` that owns its own models, routes, services, storage file, and background loop.
6. The new backend package must support multiple source accounts and multiple follower accounts.
7. The new backend package must allow users to define copy relationships between source and follower accounts.
8. The in-app page must surface configuration, runtime status, source/follower account information, relationship status, and recent synchronization activity.
9. The new backend package must not import, call, subclass, or otherwise reuse any legacy `python_service.app.routes.mt5`, `python_service.app.services.mt5*`, `python_service.app.routes.order_sync`, `python_service.app.services.order_sync*`, or `python_service.app.models.order_sync*` modules.

## Constraints From Current Codebase

1. Renderer navigation currently lives in `src/renderer/src/components/module-nav.tsx` and `src/renderer/src/App.tsx`.
2. Existing backend startup wiring lives in `python_service/app/main.py` and already supports background loops via lifespan tasks.
3. Existing `order_sync` code is single-source oriented and must not be extended for this new feature.
4. Existing renderer page `src/renderer/src/pages/OrderSyncPage.tsx` can inform composition patterns only; it must not be treated as the backend or domain foundation for the new module.

## Implementation Direction

1. Add one new sidebar item and one new in-app route.
2. Create a separate backend package namespace at `python_service/app/local_copy_trading/`.
3. Give the package its own persisted storage file under `storage/`, independent of `storage/order_sync.json`.
4. Give the package its own background loop registered in FastAPI lifespan.
5. Build the renderer page against only the new `local-copy-trading` API surface.

## Out Of Scope For First Delivery

1. Replacing the legacy order-sync module.
2. Shared abstraction work between old and new sync engines.
3. Advanced analytics, charts, or audit export.

# Shadcn Sidebar Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current hand-rolled left icon menu with shadcn/ui Sidebar while preserving collapsible navigation and keeping menu icons large enough for this Electron desktop app.

**Architecture:** Install and use shadcn/ui's `Sidebar` primitives as the shell navigation foundation. Keep app module state in `App.tsx` unchanged, move navigation composition into `ModuleNav`, and let `WorkbenchShell` own the `SidebarProvider`, main content layout, and collapse trigger. Preserve existing i18n labels and current `activeModule`/`onModuleChange` contract.

**Tech Stack:** Electron + electron-vite, React 18, TypeScript, Tailwind CSS v3, shadcn/ui Radix components, lucide-react, Vitest + Testing Library.

---

## Scope Check

This plan covers one subsystem: replacing the renderer navigation shell. It should not change routing, page content, backend APIs, Electron main/preload behavior, settings storage, or menu item ordering.

## Current State

- Current shell file: `src/renderer/src/layouts/workbench-shell.tsx`.
- Current menu file: `src/renderer/src/components/module-nav.tsx`.
- App module state lives in `src/renderer/src/App.tsx` as `activeModule` and `setActiveModule`.
- Existing menu is a fixed-width custom `<nav className="w-16 ...">` with icon-only buttons and `title` tooltips.
- Existing collapse behavior is effectively the icon-only rail; the replacement must keep a collapsible sidebar, not switch to an always-expanded web-style sidebar.
- Current shadcn setup has `components.json`, but `src/renderer/src/components/ui/sidebar.tsx` does not exist.
- `components.json` currently points Tailwind CSS at `src/styles/globals.css`, but the real renderer stylesheet is `src/renderer/src/styles/globals.css`. Fix this before running the shadcn install so generated Sidebar CSS variables land in the app's actual CSS file.
- `npx shadcn@latest add sidebar --dry-run` reports it will create sidebar dependencies and may overwrite `src/renderer/src/components/ui/button.tsx` and `src/renderer/src/components/ui/input.tsx`. Treat these overwrites as risky and review `git diff` after install before accepting them.
- shadcn docs checked: `npx shadcn@latest docs sidebar`, docs URL `https://ui.shadcn.com/docs/components/radix/sidebar`.

## File Structure

Files to create:

- `src/renderer/src/components/ui/sidebar.tsx`: shadcn Sidebar primitives. Source should come from `npx shadcn@latest add sidebar`, then be reviewed for this repo's Tailwind v3 syntax and Electron desktop behavior.
- `src/renderer/src/components/ui/sheet.tsx`: shadcn Sheet dependency used by Sidebar mobile behavior.
- `src/renderer/src/components/ui/tooltip.tsx`: shadcn Tooltip dependency used by collapsed sidebar menu buttons.
- `src/renderer/src/components/ui/separator.tsx`: shadcn Separator dependency.
- `src/renderer/src/components/ui/skeleton.tsx`: shadcn Skeleton dependency.
- `src/renderer/src/hooks/use-mobile.tsx`: shadcn hook used by Sidebar for mobile behavior.

Files to modify:

- `src/renderer/src/styles/globals.css`: add shadcn sidebar CSS variables under both `:root` and `.dark` in the existing `@layer base` block.
- `tailwind.config.ts`: ensure `theme.extend.colors.sidebar` exists so classes such as `bg-sidebar`, `text-sidebar-foreground`, and `border-sidebar-border` compile to the sidebar CSS variables.
- `src/renderer/src/layouts/workbench-shell.tsx`: replace outer custom flex sidebar layout with `SidebarProvider`, `ModuleNav`, and `SidebarInset`; move the collapse trigger into the existing header.
- `src/renderer/src/components/module-nav.tsx`: replace custom `<nav>` and raw `<button>`s with shadcn `Sidebar`, `SidebarContent`, `SidebarGroup`, `SidebarMenu`, `SidebarMenuItem`, and `SidebarMenuButton`.
- `src/renderer/src/test/dashboard-page.test.tsx`: extend shell/navigation tests to assert expanded labels, collapse trigger behavior, and large icon class/attribute policy.
- `src/renderer/src/test/settings-page-language.test.tsx`: run existing language test to confirm nav labels still update through i18n.

Files that may be modified by shadcn CLI and must be diff-reviewed before accepting:

- `src/renderer/src/components/ui/button.tsx`: current local component is small and may differ from upstream generated output.
- `src/renderer/src/components/ui/input.tsx`: current local component is small and may differ from upstream generated output.
- `package.json` and `package-lock.json`: shadcn may add `@radix-ui/react-separator` and `@radix-ui/react-tooltip`; keep these if the generated components import them.

Do not modify:

- `src/renderer/src/App.tsx` unless a test proves the shell contract must change.
- `src/renderer/src/i18n/messages.ts` unless a test proves a missing nav label. Existing `nav.*` strings are sufficient.
- Backend or Electron main/preload files.

## Design Decisions

- Use `SidebarProvider defaultOpen={false}` so the default desktop state resembles the current icon rail and preserves the existing compact app chrome.
- Use controlled `SidebarProvider open={sidebarOpen} onOpenChange={setSidebarOpen}` state initialized to `false`. Do not rely only on `defaultOpen={false}`, because generated shadcn Sidebar versions may persist state and reopen expanded on the next Electron launch.
- Use `<Sidebar collapsible="icon">` so collapse is shadcn-native and can expand via `SidebarTrigger`.
- Use `<SidebarInset>` for the main app panel because shadcn docs specify this composition for sidebar layouts.
- Use the existing app header for the collapse trigger and help button. Do not add a second header inside the sidebar.
- Keep icons visibly larger than shadcn web sidebar defaults. The current app uses `w-5 h-5`. Target icon size should be `size-5` or equivalent final rendered class, and menu button height should be at least `h-11` or `size-11` in icon-only collapsed mode.
- Preserve `title={item.label}` on menu buttons for native tooltip/accessibility in collapsed mode, even if shadcn `Tooltip` also exists.
- Add `aria-label="Main navigation"` to the `Sidebar` so tests and assistive technologies can target the navigation region reliably.
- Preserve menu order exactly: dashboard, price-alerts, volatility, indicator-alerts, risk-control, order-center, tech-analysis, order-broadcast, settings.

## Task 1: Add Regression Tests for Sidebar Behavior

**Files:**
- Modify: `src/renderer/src/test/dashboard-page.test.tsx`
- Reference: `src/renderer/src/components/module-nav.tsx`
- Reference: `src/renderer/src/layouts/workbench-shell.tsx`

- [ ] **Step 1: Write the failing test for expanded sidebar labels**

Add `userEvent` and `within` imports at the top of `src/renderer/src/test/dashboard-page.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
```

Then add this test inside `describe('Dashboard Page', () => { ... })`:

```tsx
it('renders shadcn sidebar navigation labels after expanding the menu', async () => {
  const user = userEvent.setup()
  render(<TestRoot />)

  const trigger = await screen.findByRole('button', { name: /toggle sidebar/i })
  await user.click(trigger)

  const nav = screen.getByLabelText('Main navigation')
  expect(await within(nav).findByRole('button', { name: 'Dashboard' })).toBeInTheDocument()
  expect(await within(nav).findByRole('button', { name: 'Technical Analysis' })).toBeInTheDocument()
  expect(await within(nav).findByRole('button', { name: 'Settings' })).toBeInTheDocument()
})
```

- [ ] **Step 2: Write the failing test for module switching through sidebar buttons**

Add this test in the same file:

```tsx
it('switches modules from the shadcn sidebar menu', async () => {
  const user = userEvent.setup()
  render(<TestRoot />)

  const trigger = await screen.findByRole('button', { name: /toggle sidebar/i })
  await user.click(trigger)

  const nav = screen.getByLabelText('Main navigation')
  await user.click(await within(nav).findByRole('button', { name: 'Technical Analysis' }))

  expect(await screen.findByText('Generate Technical Analysis')).toBeInTheDocument()
})
```

- [ ] **Step 3: Write the failing test for larger Electron menu icons**

Use a test ID rather than computed CSS; jsdom cannot verify actual rendered pixel size reliably. Add this test:

```tsx
it('uses desktop-sized sidebar icons rather than tiny web sidebar icons', async () => {
  render(<TestRoot />)

  const dashboardIcon = await screen.findByTestId('sidebar-icon-dashboard')
  expect(dashboardIcon).toHaveClass('size-5')
})
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `npm run test:frontend -- dashboard`

Expected: FAIL because there is no `Toggle Sidebar` button, no expanded labels in a shadcn sidebar, and no `data-testid="sidebar-icon-dashboard"`.

- [ ] **Step 5: Commit failing tests**

Run:

```bash
git add src/renderer/src/test/dashboard-page.test.tsx
git commit -m "test: cover shadcn sidebar navigation"
```

Expected: commit succeeds. Do not skip hooks.

## Task 2: Install shadcn Sidebar Primitives Safely

**Files:**
- Create: `src/renderer/src/components/ui/sidebar.tsx`
- Create: `src/renderer/src/components/ui/sheet.tsx`
- Create: `src/renderer/src/components/ui/tooltip.tsx`
- Create: `src/renderer/src/components/ui/separator.tsx`
- Create: `src/renderer/src/components/ui/skeleton.tsx`
- Create: `src/renderer/src/hooks/use-mobile.tsx`
- Modify: `src/renderer/src/styles/globals.css`
- Maybe modify: `src/renderer/src/components/ui/button.tsx`
- Maybe modify: `src/renderer/src/components/ui/input.tsx`
- Maybe modify: `package.json`
- Maybe modify: `package-lock.json`
- Maybe modify: `tailwind.config.ts`

- [ ] **Step 1: Fix shadcn CSS output path before install**

Modify `components.json` so the Tailwind CSS path points to the real renderer stylesheet:

```json
{
  "tailwind": {
    "css": "src/renderer/src/styles/globals.css"
  }
}
```

Only change the existing `tailwind.css` value; do not rewrite the whole file.

Run: `git diff -- components.json`

Expected: only this line changes:

```diff
-    "css": "src/styles/globals.css",
+    "css": "src/renderer/src/styles/globals.css",
```

- [ ] **Step 2: Preview shadcn sidebar install**

Run: `npx shadcn@latest add sidebar --dry-run`

Expected: output lists `sidebar.tsx`, `sheet.tsx`, `tooltip.tsx`, `separator.tsx`, `skeleton.tsx`, `use-mobile.tsx`, warns that `button.tsx` and `input.tsx` may be overwritten, and CSS output targets `src\renderer\src\styles\globals.css`.

- [ ] **Step 3: Snapshot local button/input before install**

Run CLI diffs for the existing local components if supported by the installed shadcn CLI:

```bash
npx shadcn@latest add sidebar --diff src/renderer/src/components/ui/button.tsx
npx shadcn@latest add sidebar --diff src/renderer/src/components/ui/input.tsx
```

Expected: if the CLI prints a diff, inspect it before installing. If the CLI rejects the command for this version, continue to the temp snapshot and post-install `git diff` steps below; do not treat CLI diff failure as a blocker by itself.

- [ ] **Step 4: Snapshot local button/input before install**

Run these PowerShell commands from the repo root:

```powershell
Copy-Item "src/renderer/src/components/ui/button.tsx" "C:/Users/ADMINI~1/AppData/Local/Temp/opencode/button.before-sidebar.tsx"
Copy-Item "src/renderer/src/components/ui/input.tsx" "C:/Users/ADMINI~1/AppData/Local/Temp/opencode/input.before-sidebar.tsx"
```

Expected: both temporary snapshots exist. These are only for comparison/restoration if shadcn overwrites local components.

- [ ] **Step 5: Install sidebar primitives**

Run: `npx shadcn@latest add sidebar`

Expected: component files are created and missing Radix dependencies are added to `package.json`/`package-lock.json`.

- [ ] **Step 6: Review generated diffs for overwritten local components**

Run:

```bash
git diff -- src/renderer/src/components/ui/button.tsx src/renderer/src/components/ui/input.tsx
```

Expected: inspect the actual local diff. If shadcn overwrote them but the generated sidebar does not require new APIs, restore local behavior from the temporary snapshots while keeping any required API additions.

Expected final `button.tsx` exports `Button` and `buttonVariants`; final `input.tsx` exports `Input`.

- [ ] **Step 7: Remove accidental wrong CSS output if created**

Check whether `src/styles/globals.css` was created despite Step 1.

Run: `git status --short`

Expected: there is no `src/styles/globals.css`. If it exists, move any sidebar variables from that file into `src/renderer/src/styles/globals.css`, then delete `src/styles/globals.css`. Do not keep duplicate renderer CSS files.

- [ ] **Step 8: Fix generated sidebar for Tailwind v3 compatibility if necessary**

Open `src/renderer/src/components/ui/sidebar.tsx`. Search for Tailwind v4-only syntax such as `w-(--sidebar-width)` or `bg-sidebar`. For this repo's Tailwind v3, replace arbitrary CSS variable utilities with bracket syntax where needed.

Use examples like:

```tsx
// Tailwind v4 style that may not compile in this repo:
"w-(--sidebar-width)"

// Tailwind v3-compatible style:
"w-[var(--sidebar-width)]"
```

Expected: `npm run build` later compiles without Tailwind class parse errors.

- [ ] **Step 9: Confirm sidebar CSS variables are in the actual renderer CSS file**

Open `src/renderer/src/styles/globals.css`, not the stale `components.json` path `src/styles/globals.css`. Ensure `:root` includes:

```css
--sidebar-background: 0 0% 98%;
--sidebar-foreground: 240 5.3% 26.1%;
--sidebar-primary: 240 5.9% 10%;
--sidebar-primary-foreground: 0 0% 98%;
--sidebar-accent: 240 4.8% 95.9%;
--sidebar-accent-foreground: 240 5.9% 10%;
--sidebar-border: 220 13% 91%;
--sidebar-ring: 217.2 91.2% 59.8%;
```

Ensure `.dark` includes:

```css
--sidebar-background: 240 5.9% 10%;
--sidebar-foreground: 240 4.8% 95.9%;
--sidebar-primary: 0 0% 98%;
--sidebar-primary-foreground: 240 5.9% 10%;
--sidebar-accent: 240 3.7% 15.9%;
--sidebar-accent-foreground: 240 4.8% 95.9%;
--sidebar-border: 240 3.7% 15.9%;
--sidebar-ring: 217.2 91.2% 59.8%;
```

Expected: no new CSS file is created under `src/styles`; all CSS changes live in `src/renderer/src/styles/globals.css`.

- [ ] **Step 10: Confirm Tailwind sidebar color mapping exists**

Open `tailwind.config.ts` and ensure `theme.extend.colors` contains this mapping:

```ts
sidebar: {
  DEFAULT: 'hsl(var(--sidebar-background))',
  foreground: 'hsl(var(--sidebar-foreground))',
  primary: 'hsl(var(--sidebar-primary))',
  'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  accent: 'hsl(var(--sidebar-accent))',
  'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  border: 'hsl(var(--sidebar-border))',
  ring: 'hsl(var(--sidebar-ring))',
},
```

Expected: generated shadcn classes like `bg-sidebar`, `text-sidebar-foreground`, `border-sidebar-border`, and `ring-sidebar-ring` are valid in Tailwind v3.

- [ ] **Step 11: Run build to verify generated primitives compile**

Run: `npm run build`

Expected: PASS. If it fails on Tailwind utility syntax, CSS variable path, or missing Radix packages, fix generated primitives/dependencies before continuing.

- [ ] **Step 12: Commit shadcn primitives**

Run:

```bash
git add components.json package.json package-lock.json tailwind.config.ts src/renderer/src/components/ui src/renderer/src/hooks src/renderer/src/styles/globals.css
git commit -m "chore: add shadcn sidebar primitives"
```

Expected: commit succeeds. Do not include unrelated files.

## Task 3: Replace ModuleNav with shadcn Sidebar Composition

**Files:**
- Modify: `src/renderer/src/components/module-nav.tsx`
- Reference: `src/renderer/src/i18n/messages.ts`
- Reference: `src/renderer/src/pages/TechnicalAnalysisPage.tsx`

- [ ] **Step 1: Replace raw nav imports with sidebar imports**

In `src/renderer/src/components/module-nav.tsx`, keep lucide icons and `useI18n`, remove `cn`, and import shadcn sidebar primitives:

```tsx
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'
```

Expected: TypeScript import list is valid after Task 2.

- [ ] **Step 2: Keep nav item data unchanged**

Keep this exact menu order and IDs:

```tsx
const navItems = [
  { id: 'dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
  { id: 'price-alerts', label: t('nav.priceAlerts'), icon: Bell },
  { id: 'volatility', label: t('nav.volatility'), icon: TrendingUp },
  { id: 'indicator-alerts', label: t('nav.indicatorAlerts'), icon: LineChart },
  { id: 'risk-control', label: t('nav.riskControl'), icon: ShieldCheck },
  { id: 'order-center', label: t('nav.orderCenter'), icon: ShoppingBag },
  { id: 'tech-analysis', label: t('nav.technicalAnalysis'), icon: BookOpen },
  { id: 'order-broadcast', label: t('nav.orderBroadcast'), icon: Megaphone },
  { id: 'settings', label: t('nav.settings'), icon: Settings },
]
```

Expected: no page switches break because `App.tsx` still uses the same IDs.

- [ ] **Step 3: Implement Sidebar menu with active state and large icons**

Replace the current return block with:

```tsx
return (
  <Sidebar collapsible="icon" aria-label="Main navigation" className="border-r">
    <SidebarContent>
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            {navItems.map((item) => {
              const Icon = item.icon

              return (
                <SidebarMenuItem key={item.id}>
                  <SidebarMenuButton
                    type="button"
                    tooltip={item.label}
                    title={item.label}
                    isActive={activeModule === item.id}
                    onClick={() => onModuleChange(item.id)}
                    className="h-11 gap-3 [&>svg]:size-5"
                  >
                    <Icon data-testid={`sidebar-icon-${item.id}`} className="size-5 shrink-0" />
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )
            })}
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>
    <SidebarRail />
  </Sidebar>
)
```

Expected: collapsed sidebar still shows icons; expanded sidebar shows labels; the menu button explicitly overrides shadcn's default `[&>svg]:size-4` with `[&>svg]:size-5`, so icons are not tiny web sidebar icons.

- [ ] **Step 4: Run dashboard tests to verify partial progress**

Run: `npm run test:frontend -- dashboard`

Expected: still FAIL if `WorkbenchShell` does not yet provide `SidebarProvider` and `SidebarTrigger`. Do not force tests to pass by weakening assertions.

- [ ] **Step 5: Commit ModuleNav conversion**

Run:

```bash
git add src/renderer/src/components/module-nav.tsx
git commit -m "refactor: render module nav with shadcn sidebar"
```

Expected: commit succeeds.

## Task 4: Wire SidebarProvider and Collapse Trigger into WorkbenchShell

**Files:**
- Modify: `src/renderer/src/layouts/workbench-shell.tsx`
- Reference: `src/renderer/src/components/module-nav.tsx`

- [ ] **Step 1: Import shadcn shell primitives**

Add these imports to `src/renderer/src/layouts/workbench-shell.tsx`:

```tsx
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
```

Expected: imports resolve after Task 2.

- [ ] **Step 2: Add controlled collapsed sidebar state**

Inside `WorkbenchShell`, below `const { t, locale } = useI18n()`, add:

```tsx
const [sidebarOpen, setSidebarOpen] = React.useState(false)
```

Expected: each Electron launch starts collapsed unless this component state is changed by the current session. Do not persist this state to local storage or cookies.

- [ ] **Step 3: Replace the outer layout with SidebarProvider**

Replace the existing return block with this structure:

```tsx
return (
  <SidebarProvider open={sidebarOpen} onOpenChange={setSidebarOpen}>
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <ModuleNav activeModule={activeModule} onModuleChange={onModuleChange} />

      <SidebarInset className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b bg-background/50 px-6 backdrop-blur-md">
          <div className="flex min-w-0 items-center gap-3">
            <SidebarTrigger />
            <h2 className="truncate text-lg font-semibold tracking-tight">{t('app.title')}</h2>
          </div>
          <Button variant="outline" size="sm" onClick={() => void handleOpenUserGuide()} title={t('help.userGuideHint')}>
            <BookOpen className="mr-2 h-4 w-4" />
            {t('help.userGuide')}
          </Button>
        </header>

        <main className="relative flex-1 overflow-y-auto overflow-x-hidden p-6">
          {children}
        </main>
      </SidebarInset>
    </div>
  </SidebarProvider>
)
```

Expected: app still has one header, help button remains available, and `SidebarTrigger` has accessible text from shadcn (`Toggle Sidebar`).

- [ ] **Step 4: Confirm collapsed menu remains compact by default**

Run: `npm run dev`

Expected: Electron opens with an icon rail by default, not a wide web sidebar. Clicking the trigger expands/collapses the sidebar.

- [ ] **Step 5: Confirm icon size manually**

In the running app, verify sidebar menu icons are visually similar to or larger than the old `w-5 h-5` icons. If they look too small, increase the icon class in `ModuleNav` to `size-6` and keep the test aligned.

Expected: icons do not look like tiny web sidebar icons in collapsed mode.

- [ ] **Step 6: Run tests**

Run: `npm run test:frontend -- dashboard`

Expected: PASS.

- [ ] **Step 7: Commit shell wiring**

Run:

```bash
git add src/renderer/src/layouts/workbench-shell.tsx src/renderer/src/components/module-nav.tsx src/renderer/src/test/dashboard-page.test.tsx
git commit -m "feat: wire collapsible shadcn sidebar shell"
```

Expected: commit succeeds.

## Task 5: Verify i18n, Full Frontend Tests, and Electron Build

**Files:**
- Test: `src/renderer/src/test/settings-page-language.test.tsx`
- Test: `src/renderer/src/test/dashboard-page.test.tsx`
- Verify: `src/renderer/src/layouts/workbench-shell.tsx`
- Verify: `src/renderer/src/components/module-nav.tsx`

- [ ] **Step 1: Run settings language test**

Run: `npm run test:frontend -- settings-page-language`

Expected: PASS. This confirms nav text still responds to language changes.

- [ ] **Step 2: Run full frontend test suite**

Run: `npm run test:frontend`

Expected: PASS. Existing React `act(...)` warnings in settings store tests are acceptable if the suite passes and no new warnings are introduced by sidebar tests.

- [ ] **Step 3: Run production build**

Run: `npm run build`

Expected: PASS. This catches shadcn/Tailwind class issues that Vitest may miss.

- [ ] **Step 4: Run manual smoke in dev**

Run: `npm run dev`

Expected: Electron opens without white screen. Verify:

- Sidebar starts collapsed as an icon rail.
- Trigger expands and collapses the sidebar.
- Icons remain visually large enough in collapsed mode.
- Active menu item is visually highlighted.
- Clicking every menu item displays the expected page.
- Help button still opens the user guide or shows the existing error toast if help cannot open.

- [ ] **Step 5: Optional package smoke after build**

Only if changing generated sidebar dependencies caused packaging concern, run: `npm run test:electron`

Expected: PASS, but remember this launches `out/main/index.js`, so `npm run build` must run first.

- [ ] **Step 6: Commit verification fixes if any**

If Step 1-5 required fixes, commit them:

```bash
git add src/renderer/src/components/module-nav.tsx src/renderer/src/layouts/workbench-shell.tsx src/renderer/src/components/ui src/renderer/src/hooks src/renderer/src/styles/globals.css package.json package-lock.json src/renderer/src/test/dashboard-page.test.tsx
git commit -m "fix: stabilize shadcn sidebar navigation"
```

Expected: commit only if there are changes. Do not create an empty commit.

## Rollback Notes

If the shadcn Sidebar introduces instability that cannot be fixed quickly:

- Revert only the commits from this plan in reverse order.
- Do not revert unrelated user changes in the worktree.
- Preserve `package-lock.json` consistency with `package.json`.

## Acceptance Criteria

- The custom `ModuleNav` `<nav className="w-16 ...">` implementation is gone.
- `ModuleNav` renders shadcn Sidebar primitives.
- `WorkbenchShell` uses `SidebarProvider`, `SidebarInset`, and `SidebarTrigger`.
- Sidebar is collapsible and starts in a compact icon-rail state.
- Menu icons use at least `size-5`, and the test verifies this policy.
- Existing menu item order and page switching remain unchanged.
- Existing i18n labels are reused; no duplicate nav label constants are introduced.
- `npm run test:frontend` passes.
- `npm run build` passes.

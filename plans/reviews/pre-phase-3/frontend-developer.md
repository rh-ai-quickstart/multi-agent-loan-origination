# Frontend Review -- Pre-Phase 3

Reviewer: Frontend Developer
Date: 2026-02-26
Scope: All files in `packages/ui/`

---

## FE-01: Hero component still shows template text, not Summit Cap branding
**Severity:** Warning
**Location:** packages/ui/src/components/hero/hero.tsx:12-15
**Description:** The Hero component displays "Welcome to the AI QuickStart Template!" and references "our documentation". This is the original template language and does not reflect the Summit Cap Financial product identity. The project was renamed in PR #1 (`chore/rename-to-summit-cap`), but the Hero copy was never updated.
**Recommendation:** Update the heading and body text to reference Summit Cap Financial and the mortgage lending domain rather than a generic quickstart template.

## FE-02: Hero test asserts on stale template text
**Severity:** Warning
**Location:** packages/ui/src/components/hero/hero.test.tsx:8-13
**Description:** The single test file in the UI package asserts `screen.getByText(/AI QuickStart Template/i)`. This will break when FE-01 is fixed but currently passes only because the copy is stale. The tests are tightly coupled to the exact wording rather than the semantic structure.
**Recommendation:** After updating Hero copy, update assertions to match the new text. Consider asserting on the semantic role (`heading`) rather than exact string content for resilience.

## FE-03: Duplicate `Service` type definition diverges from Zod schema
**Severity:** Warning
**Location:** packages/ui/src/components/status-panel/status-panel.tsx:4-15
**Description:** `StatusPanel` defines its own local `Service` type with fields `id`, `name`, `description`, `icon`, `status`, `region`, `endpoint`, `port`, `lastCheck`, `error`. The canonical `Service` type from `schemas/health.ts` has `name`, `status`, `message`, `version`, `start_time`. These are completely different shapes. The `StatusPanel` accepts the local type but passes data to `ServiceList`, which uses the Zod-derived type internally. The `services` prop received by `StatusPanel` is never actually passed through to `ServiceList` -- `ServiceList` fetches its own data via `useHealth()`.
**Recommendation:** Remove the local `Service` type from `status-panel.tsx`. Either pass services down as a prop (removing the internal fetch from `ServiceList`) or remove the `services` prop from `StatusPanel` entirely since it is not used for rendering the actual service cards.

## FE-04: StatusPanel accepts `services` prop but does not use it for rendering
**Severity:** Warning
**Location:** packages/ui/src/components/status-panel/status-panel.tsx:17,41
**Description:** `StatusPanel` receives `{ services: Service[] }` and uses `services.length` to determine empty state vs. content, but the actual service cards are rendered by `<ServiceList />` which independently calls `useHealth()`. The `services` array built in `index.tsx` (lines 18-46) is constructed with `icon` JSX, `region`, `lastCheck` etc. but none of that data ever reaches the rendered cards. This is dead/disconnected logic.
**Recommendation:** Either thread the `services` prop through to `ServiceList`/`ServiceCard` so the data flows top-down, or remove the prop and have `StatusPanel` derive its empty-state check from the `useHealth` hook directly.

## FE-05: `void Footer` statement in Index route is dead code
**Severity:** Info
**Location:** packages/ui/src/routes/index.tsx:16
**Description:** The line `void Footer;` exists with the comment "Footer is imported for consistency but rendered in root route". This import and void statement serve no purpose -- the Footer is already rendered in `__root.tsx`. The import is unused.
**Recommendation:** Remove the `Footer` import and the `void Footer` line from `index.tsx`.

## FE-06: `@ts-expect-error` suppresses a non-existent error in __root.tsx
**Severity:** Info
**Location:** packages/ui/src/routes/__root.tsx:3-4
**Description:** The comment `// @ts-expect-error - React is used implicitly by JSX transform` suppresses a TypeScript error for the React import. With `"jsx": "react-jsx"` in tsconfig (which is configured), React does not need to be imported for JSX. The `@ts-expect-error` itself may produce a TS error in strict mode if there is no actual error to suppress (TS reports unused `@ts-expect-error` as an error with `noUnusedLocals`).
**Recommendation:** Remove both the `@ts-expect-error` comment and the `import React` line, since the `react-jsx` transform handles it automatically.

## FE-07: Duplicated packages in both `dependencies` and `devDependencies`
**Severity:** Warning
**Location:** packages/ui/package.json:23-94
**Description:** Several packages appear in both `dependencies` and `devDependencies` at the same version: `@tanstack/react-router`, `@tanstack/router-devtools`, `@tanstack/router-vite-plugin`, `@tanstack/react-query`, `@radix-ui/react-avatar`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-separator`, `@radix-ui/react-slot`, `@radix-ui/react-tooltip`, `class-variance-authority`, `clsx`, `lucide-react`, `tailwind-merge`, `tailwindcss-animate`, `zod`. This is confusing and can cause version conflicts. For a Vite-built app that bundles everything, all runtime dependencies should be in `dependencies` only.
**Recommendation:** Remove the duplicated entries from `devDependencies`. Keep runtime packages (`@tanstack/*`, `@radix-ui/*`, `clsx`, `cva`, `lucide-react`, `tailwind-merge`, `zod`) in `dependencies` only. Keep build/dev tools (`vite`, `typescript`, `eslint`, `storybook`, `vitest`, etc.) in `devDependencies` only.

## FE-08: `react` and `react-dom` are in `devDependencies` only
**Severity:** Warning
**Location:** packages/ui/package.json:57-58
**Description:** `react` and `react-dom` are listed only under `devDependencies`. These are core runtime dependencies and should be in `dependencies` (or `peerDependencies` for a library). While Vite will bundle them regardless, this misclassification could cause issues for tooling that respects the dep/devDep distinction (e.g., dependency auditing, tree-shaking analysis, SSR setups).
**Recommendation:** Move `react` and `react-dom` to `dependencies`.

## FE-09: No error boundary wrapping the application
**Severity:** Warning
**Location:** packages/ui/src/main.tsx:18-28
**Description:** The app is rendered with `RouterProvider` inside `QueryClientProvider` but there is no React error boundary. An unhandled render error in any component will crash the entire app with a blank white screen and no user feedback. This is especially important given the app fetches remote health data on the index page.
**Recommendation:** Add a top-level error boundary component (e.g., `react-error-boundary` or a custom one) wrapping `RouterProvider`. Display a user-friendly fallback UI when an unhandled error occurs.

## FE-10: TanStack Router devtools included unconditionally
**Severity:** Warning
**Location:** packages/ui/src/routes/__root.tsx:6,18
**Description:** `<TanStackRouterDevtools />` is rendered in the root route without any environment check. This will be included in production builds, adding bundle size and potentially exposing internal routing state to end users.
**Recommendation:** Conditionally render devtools only in development: `{import.meta.env.DEV && <TanStackRouterDevtools />}` or use React's lazy import with a dev-only check.

## FE-11: `useHealth` hook return type is lying about the shape
**Severity:** Warning
**Location:** packages/ui/src/hooks/health.ts:42
**Description:** The hook uses `Object.assign({}, queryResult, { data: enhancedData }) as UseQueryResult<Health, Error>` to override the `data` field. This shallow clone breaks TanStack Query's internal reference identity -- consumers comparing `queryResult` by reference (as TanStack Query's re-render optimization does) will get unnecessary re-renders on every render cycle since a new object is created each time. The `as` cast also masks the fact that the returned object is no longer a genuine `UseQueryResult`.
**Recommendation:** Instead of cloning and casting, use TanStack Query's `select` option to transform the data directly: `useQuery({ queryKey: ['health'], queryFn: getHealth, select: (data) => addUIService(data) })`. This preserves TanStack Query's memoization and referential stability.

## FE-12: `ServiceList` passes `isLoading` to cards but the flag is misleading after initial load
**Severity:** Info
**Location:** packages/ui/src/components/service-list/service-list.tsx:10
**Description:** `isLoading` from TanStack Query is `true` only on the initial fetch (before any data is cached). On subsequent background refetches, `isLoading` is `false` while `isFetching` is `true`. The service cards show a spinner based on `isLoading`, which means background refetch activity is invisible to the user. This is a common TanStack Query pitfall.
**Recommendation:** Consider passing `isFetching` (or both) to `ServiceCard` and showing a subtler indicator during background refetches (e.g., a pulsing dot) while reserving the full spinner for the initial load.

## FE-13: No loading or error state on the index route
**Severity:** Warning
**Location:** packages/ui/src/routes/index.tsx:14-57
**Description:** The `Index` component destructures only `{ data: healthData }` from `useHealth()`, ignoring `isLoading` and `error`. If the health API is slow or fails, the page renders with `'unknown'` status badges but provides no indication that data is loading or that an error occurred. The user sees three "Unknown" cards with no context.
**Recommendation:** Destructure `isLoading` and `error` from `useHealth()`. Show a skeleton/spinner during loading and an error message on failure. Note: the `services` array in `Index` is not actually used by `ServiceList` (see FE-04), so fixing this may require rethinking the data flow.

## FE-14: Inconsistent indentation in `index.tsx`
**Severity:** Info
**Location:** packages/ui/src/routes/index.tsx:18-46
**Description:** The services array has inconsistent indentation -- the first object (`ui`) uses 4-space indent while `api` and `db` objects use 6-space indent (extra 2 spaces). This makes the code harder to read and would be caught by a formatter.
**Recommendation:** Run `prettier --write` on this file to normalize indentation.

## FE-15: `@ts-ignore`/`any` cast on route definition
**Severity:** Info
**Location:** packages/ui/src/routes/index.tsx:9-10
**Description:** Line 9 has `// eslint-disable-next-line @typescript-eslint/no-explicit-any` and line 10 casts `'/' as any`. This suppresses the type-safe route registration that TanStack Router provides. The cast was likely added to work around a type error from the generated route tree.
**Recommendation:** Investigate the root cause of the type mismatch. With a correctly generated `routeTree.gen.ts`, the `createFileRoute('/')` call should work without an `any` cast. Regenerating the route tree (by restarting the Vite dev server with TanStack Router plugin) may resolve this.

## FE-16: Storybook manager polls localStorage every 500ms
**Severity:** Warning
**Location:** packages/ui/.storybook/manager.ts:79
**Description:** `setInterval(updateTheme, 500)` runs indefinitely with no cleanup, calling `localStorage.getItem`, `JSON.parse`, and `addons.setConfig` every 500ms. This is wasteful and could cause subtle performance issues in Storybook. The comment says "poll for changes as a fallback" but the event listeners above (`storybook-dark-mode/update`, `DARK_MODE`, `UPDATE_DARK_MODE`) plus the `storage` event listener should be sufficient.
**Recommendation:** Remove the `setInterval` polling. If the event-based approach is insufficient, use a longer interval (e.g., 5000ms) or use `MutationObserver` on the `<html>` element's class list instead.

## FE-17: Storybook theme objects duplicated between `manager.ts` and `preview.ts`
**Severity:** Info
**Location:** packages/ui/.storybook/manager.ts:4-38 and packages/ui/.storybook/preview.ts:7-41
**Description:** The `darkTheme` and `lightTheme` objects are copy-pasted identically in both files. If a theme value needs to change, both files must be updated in sync.
**Recommendation:** Extract the shared theme objects into a common file (e.g., `.storybook/theme.ts`) and import from both `manager.ts` and `preview.ts`.

## FE-18: No test coverage beyond one component
**Severity:** Warning
**Location:** packages/ui/src/ (project-wide)
**Description:** The only test file is `hero.test.tsx` with 2 trivial assertions. There are no tests for: `useHealth` hook, `getHealth` service, `ServiceCard`, `ServiceList`, `StatusPanel`, `ModeToggle`, `ThemeProvider`, `Header`, `Footer`, or any of the utility functions (`cn`, `getUptime`, `formatTime`). The `test-utils.tsx` file exists with `renderWithProviders` and `createTestQueryClient` but is never imported by any test.
**Recommendation:** At minimum, add tests for: (1) the `useHealth` hook with mocked fetch, (2) `ServiceCard` rendering in each status state, (3) the `formatTime` and `getUptime` utility functions which have branching logic. The test utilities should be used for components that depend on QueryClient context.

## FE-19: `ThemeProvider` does not react to system theme changes
**Severity:** Info
**Location:** packages/ui/src/components/theme-provider/theme-provider.tsx:33-49
**Description:** When theme is set to "system", the `useEffect` reads the current `prefers-color-scheme` media query value once and applies it, but does not register a `change` event listener on the `MediaQueryList`. If the user changes their OS theme preference while the app is open, the UI will not update until a re-render is triggered by something else.
**Recommendation:** Add a `MediaQueryList.addEventListener('change', ...)` inside the `useEffect` when theme is "system" to reactively update the class when the OS preference changes.

## FE-20: `ThemeProvider` casts `localStorage` value without validation
**Severity:** Info
**Location:** packages/ui/src/components/theme-provider/theme-provider.tsx:30
**Description:** `localStorage.getItem(storageKey) as Theme` performs an unsafe cast. If someone manually sets the storage key to an invalid value (e.g., "purple"), the component will attempt to add "purple" as a class on `<html>`, which will fail to apply any theme. There is no validation or fallback to the default.
**Recommendation:** Validate the localStorage value against the allowed set `["dark", "light", "system"]` before using it. Fall back to `defaultTheme` if the value is not recognized.

## FE-21: WebSocket proxy not configured in Vite
**Severity:** Warning
**Location:** packages/ui/vite.config.ts:17-23
**Description:** The Vite proxy only handles `/api` HTTP requests. The backend exposes WebSocket endpoints at `/ws/` paths (used by the chat feature in Phase 2). There is no `ws: true` proxy configuration. During local development, any frontend WebSocket connection to the backend through the Vite dev server will fail.
**Recommendation:** Add a WebSocket proxy entry: `'/ws': { target: 'http://localhost:8000', ws: true, changeOrigin: true }`.

## FE-22: `ServiceCard` creates a new `Date` on every interval tick
**Severity:** Info
**Location:** packages/ui/src/components/service-card/service-card.tsx:226
**Description:** Inside the `useEffect` interval callback, `new Date(service.start_time)` is called every 1000ms. While not a performance problem at the current scale (3 cards), parsing a date string on every tick for every card is unnecessary.
**Recommendation:** Memoize the parsed start time with `useMemo(() => new Date(service.start_time), [service.start_time])` and reference it in the interval callback.

## FE-23: Vite proxy strips `/api` prefix entirely
**Severity:** Warning
**Location:** packages/ui/vite.config.ts:21
**Description:** The proxy rewrite `path.replace(/^\/api/, '')` strips the `/api` prefix. This means a frontend fetch to `/api/health/` hits the backend at `/health/`. This works only if the backend mounts routes at the root. If a future phase adds an `/api/v1/` prefix on the backend (which is common in production API versioning), this rewrite will break silently.
**Recommendation:** Document that the proxy assumes the backend mounts routes at `/` without an `/api` prefix. If the convention changes, this rewrite must be updated. Consider adding a comment in the config explaining the mapping.

## FE-24: No `aria-label` on Header navigation link
**Severity:** Info
**Location:** packages/ui/src/components/header/header.tsx:9-11
**Description:** The `<Link to="/">` wrapping the logo and text has no `aria-label`. Screen readers will announce the combined text content "Summit Cap Financial" which is acceptable, but since the link contains both an SVG (`aria-hidden="true"`) and a `<span>`, it would be more robust to add an explicit `aria-label="Summit Cap Financial home"` to communicate the link purpose clearly.
**Recommendation:** Add `aria-label="Summit Cap Financial home"` to the `<Link>` element.

## FE-25: Footer GitHub link has no accessible name beyond "GitHub"
**Severity:** Info
**Location:** packages/ui/src/components/footer/footer.tsx:15-17
**Description:** The external link text is just "GitHub" with `target="_blank"`. Screen readers will not convey that this opens in a new window/tab. WCAG 2.1 success criterion 3.2.5 recommends informing users when a link opens a new context.
**Recommendation:** Add visually hidden text or an `aria-label` indicating the link opens externally, e.g., `aria-label="GitHub repository (opens in new tab)"`.

## FE-26: `@radix-ui/react-avatar` is installed but never used
**Severity:** Info
**Location:** packages/ui/package.json:27
**Description:** `@radix-ui/react-avatar` appears in both dependencies and devDependencies but no component imports it. It adds to install size and dependency surface for no benefit.
**Recommendation:** Remove `@radix-ui/react-avatar` from both `dependencies` and `devDependencies` unless it will be needed imminently in Phase 3.

## FE-27: Missing AI assistance comment in most source files
**Severity:** Warning
**Location:** Multiple files (every .tsx/.ts file except `lib/utils.ts`)
**Description:** Per `.claude/rules/ai-compliance.md`, every code file produced or substantially modified with AI assistance must include the comment `// This project was developed with assistance from AI tools.` near the top. Only `lib/utils.ts` has this comment. All other source files (`main.tsx`, `__root.tsx`, `index.tsx`, `header.tsx`, `footer.tsx`, `hero.tsx`, `theme-provider.tsx`, `status-panel.tsx`, `service-card.tsx`, `service-list.tsx`, `stat-card.tsx`, `logo.tsx`, `mode-toggle.tsx`, `button.tsx`, `card.tsx`, `dropdown-menu.tsx`, `badge.tsx`, `separator.tsx`, `tooltip.tsx`, `health.ts` hook, `health.ts` schema, `health.ts` service, test files) are missing it.
**Recommendation:** Add the AI assistance comment to the top of all source files as required by Red Hat policy.

## FE-28: QueryClient created with no default options
**Severity:** Info
**Location:** packages/ui/src/main.tsx:9
**Description:** `new QueryClient()` uses all TanStack Query defaults, including 3 retries with exponential backoff, a 5-minute `gcTime`, and `staleTime` of 0. The health endpoint is polled on every mount with no deduplication window. For the health check use case, adding a `staleTime` (e.g., 30 seconds) would prevent redundant refetches. The 3 retries on the health endpoint could also delay the display of genuine failure states.
**Recommendation:** Configure sensible defaults on the QueryClient, such as `defaultOptions: { queries: { staleTime: 30_000, retry: 1 } }`. Individual hooks can override as needed.

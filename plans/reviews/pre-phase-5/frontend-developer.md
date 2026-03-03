# Frontend Review -- Pre-Phase 5

**Reviewer:** frontend-developer
**Date:** 2026-02-27
**Scope:** `packages/ui/src/` (lighter pass -- frontend is replaceable)

## Summary

The UI package is still largely a scaffold from the quickstart template. It has a single route (index), a health-check integration, and standard shadcn/ui atom components. The codebase is small (~39 source files, most of which are atom wrappers or stories). There are no persona views, no chat UI, no application forms, and no WebSocket integration -- all interaction with the backend's 4 chat endpoints, application CRUD, document upload, and pipeline views happens entirely through direct API/WebSocket calls (e.g., `websocat`, Swagger UI) rather than through this frontend.

Given the frontend is explicitly replaceable, the findings below focus on issues that would affect the demo or break integration with the backend.

## Findings

### [FE-01] Severity: Warning
**File(s):** `packages/ui/src/schemas/health.ts`
**Finding:** The Zod schema defines `start_time: z.string()` as required, but the backend Pydantic schema (`packages/api/src/schemas/health.py`) defines `start_time: str | None = None`, meaning the field can be `null`. If the database health check returns a response where `start_time` is null, the Zod parse will throw at runtime, causing the entire health panel to fail with an unhandled error.
**Recommendation:** Change to `start_time: z.string().nullable()` or `z.string().optional()` to match the backend contract. Update the `Service` type downstream accordingly (e.g., the uptime timer in `ServiceCard` already needs a guard for undefined `start_time`).

### [FE-02] Severity: Warning
**File(s):** `packages/ui/src/components/status-panel/status-panel.tsx`, `packages/ui/src/routes/index.tsx`
**Finding:** The `StatusPanel` component accepts a `services` prop but completely ignores it. Instead, it renders `<ServiceList />` which independently calls `useHealth()` to fetch its own data. Meanwhile, the `Index` route also calls `useHealth()` and manually constructs a `services` array that it passes to `StatusPanel`. This results in: (a) two independent `useHealth()` calls (one in `Index`, one in `ServiceList`) producing duplicate network requests, (b) the carefully constructed `services` array in `Index` being silently discarded, and (c) the `Service` type defined locally in `status-panel.tsx` (with `id`, `icon`, `region`, `lastCheck` fields) diverging from the `Service` type in `schemas/health.ts`.
**Recommendation:** Either remove the `services` prop from `StatusPanel` and delete the dead code in `Index` that constructs the unused array, or refactor `StatusPanel` to actually consume its prop and stop `ServiceList` from fetching independently. The simpler fix is the former -- let `StatusPanel` + `ServiceList` own the data fetching and remove the prop entirely.

### [FE-03] Severity: Warning
**File(s):** `packages/ui/src/routes/index.tsx`
**Finding:** The file imports `Footer` and then discards the reference with `void Footer;` on line 16. The comment says "Footer is imported for consistency but rendered in root route" -- this is dead code that serves no purpose. The `void` expression exists only to suppress the unused-import lint error, which means the import itself should be removed.
**Recommendation:** Remove the `import { Footer }` and the `void Footer;` line.

### [FE-04] Severity: Warning
**File(s):** `packages/ui/src/routes/__root.tsx`
**Finding:** `TanStackRouterDevtools` is imported unconditionally from `@tanstack/router-devtools` and rendered in the root layout. In production builds, this will add the full devtools UI and its dependencies to the bundle. While `@tanstack/router-devtools` is listed in `devDependencies`, the unconditional import means it will still be bundled by Vite in production mode (Vite does not exclude devDependencies from the bundle -- it bundles whatever is imported).
**Recommendation:** Lazy-load devtools only in development:
```tsx
const TanStackRouterDevtools = import.meta.env.DEV
    ? React.lazy(() =>
        import('@tanstack/router-devtools').then((mod) => ({
            default: mod.TanStackRouterDevtools,
        }))
    )
    : () => null;
```

### [FE-05] Severity: Warning
**File(s):** `packages/ui/src/routes/__root.tsx`
**Finding:** The file has `// @ts-expect-error - React is used implicitly by JSX transform` on the `import React from 'react'` line. The tsconfig uses `"jsx": "react-jsx"` (automatic JSX transform), which means React does not need to be imported for JSX. The `@ts-expect-error` suppresses the "unused import" TypeScript error, but the correct fix is to remove the unnecessary import. The comment claims it is an "ESLint requirement," which suggests the ESLint config may not be aware of the automatic JSX runtime.
**Recommendation:** Remove the `import React from 'react'` line and the `@ts-expect-error` comment. If ESLint complains, update the ESLint config to set `react/jsx-uses-react: off` and `react/react-in-jsx-scope: off` (or the equivalent for the flat config being used).

### [FE-06] Severity: Warning
**File(s):** `packages/ui/src/components/hero/hero.tsx`
**Finding:** The hero section still displays the template copy: "Welcome to the AI QuickStart Template!" and "This template has everything you need to develop your own AI QuickStart quickly and easily." This should have been updated to Summit Cap Financial branding as part of the PR 1 rename (`chore/rename-to-summit-cap`). For a demo, this is the first thing a viewer sees.
**Recommendation:** Update the heading and description to reflect Summit Cap Financial. For example: "Summit Cap Financial" as the heading and a brief tagline about the mortgage lending platform.

### [FE-07] Severity: Warning
**File(s):** `packages/ui/src/components/hero/hero.test.tsx`
**Finding:** The existing test asserts against the stale template text (`/Welcome to/i`, `/AI QuickStart Template/i`). When FE-06 is fixed, this test will break. The test also has no coverage for the status panel, service cards, or any loading/error states.
**Recommendation:** Update the test assertions to match the new branding when FE-06 is addressed.

### [FE-08] Severity: Warning
**File(s):** `packages/ui/vite.config.ts`
**Finding:** The Vite dev proxy rewrites `/api` by stripping the prefix: `rewrite: (path) => path.replace(/^\/api/, '')`. This means the frontend must call `/api/health/` to reach the backend's `/health/` endpoint. However, most backend routes are mounted under `/api/` already (e.g., `/api/public/products`, `/api/applications`). To reach those through the proxy, the frontend would need to call `/api/api/public/products` -- the double `/api` prefix is confusing and error-prone. There is also no proxy configuration for WebSocket endpoints (`/api/chat`, `/api/borrower/chat`, `/api/loan-officer/chat`, `/api/underwriter/chat`), which will be needed when the frontend adds chat UIs.
**Recommendation:** Change the proxy to not strip the prefix (remove the `rewrite` function), so `/api/...` proxies directly to `http://localhost:8000/api/...`. This means the health service URL would change from `/api/health/` to `/health/` (called directly without the proxy prefix), or the health router mount point on the backend should be changed to `/api/health` for consistency. The simpler option: keep the proxy for `/api` without rewrite, and add a separate proxy entry for `/health` targeting `http://localhost:8000/health`. Also add WebSocket proxy entries for the chat endpoints with `ws: true`.

### [FE-09] Severity: Warning
**File(s):** `packages/ui/package.json`
**Finding:** Several packages appear in both `dependencies` and `devDependencies`: `@tanstack/react-router`, `@tanstack/router-devtools`, `@tanstack/router-vite-plugin`, `@tanstack/react-query`, all Radix packages (`@radix-ui/react-avatar`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-separator`, `@radix-ui/react-slot`, `@radix-ui/react-tooltip`), `class-variance-authority`, `clsx`, `lucide-react`, `tailwind-merge`, `tailwindcss-animate`, and `zod`. pnpm will resolve them to a single version, but the duplication is misleading and suggests a copy-paste error during setup.
**Recommendation:** Remove the duplicate entries from `devDependencies`. Runtime packages belong in `dependencies`; build/test-only packages belong in `devDependencies`.

### [FE-10] Severity: Suggestion
**File(s):** `packages/ui/src/routes/index.tsx`
**Finding:** The route declaration uses `createFileRoute('/' as any)` with an explicit `eslint-disable-next-line @typescript-eslint/no-explicit-any` comment. The `as any` cast is a workaround for a TanStack Router type inference issue when the route tree has not been generated yet. Since `routeTree.gen.ts` exists and is properly generated, this cast may no longer be necessary.
**Recommendation:** Try removing the `as any` cast and the eslint-disable comment. If the type error reappears, it indicates a version mismatch between TanStack Router and the route generation plugin.

### [FE-11] Severity: Suggestion
**File(s):** `packages/ui/src/routes/index.tsx`
**Finding:** Inconsistent indentation in the `services` array. The `ui` object uses 4-space indentation, while the `api` and `db` objects use 10-space indentation (6 extra spaces). This is a formatting issue that the auto-formatter should have caught.
**Recommendation:** Run Prettier to normalize indentation.

### [FE-12] Severity: Suggestion
**File(s):** `packages/ui/src/components/service-card/service-card.tsx`
**Finding:** The `ServiceCard` creates a `setInterval` that runs every 1 second to update the uptime display. When multiple service cards are rendered (currently 3), this creates 3 independent intervals. While not a performance concern at this scale, the pattern becomes expensive as more services are added. Additionally, if `service.start_time` is the string `"undefined"` or unparseable, `new Date(service.start_time)` returns `Invalid Date` and `getUptime` returns `NaN`, which would display `NaNs` in the UI.
**Recommendation:** Add a guard for invalid dates. Consider a single shared timer (e.g., a context or hook that increments a counter every second) rather than per-card intervals if the service count grows.

### [FE-13] Severity: Suggestion
**File(s):** All source files in `packages/ui/src/` except `lib/utils.ts`
**Finding:** Per Red Hat policy (`.claude/rules/ai-compliance.md` and `code-style.md`), every code file produced or substantially modified with AI assistance must include the comment `// This project was developed with assistance from AI tools.` near the top. Only `lib/utils.ts` has this comment; the remaining ~38 source files do not.
**Recommendation:** Add the disclosure comment to all source files. This can be done in batch as a chore commit.

### [FE-14] Severity: Suggestion
**File(s):** `packages/ui/src/components/header/header.tsx`
**Finding:** The header `<nav>` role is implicit from the `<header>` element, but there is no `<nav>` element wrapping the navigation links. Currently there is only a home link and a theme toggle, so this is minor. When persona navigation is added (Prospect, Borrower, Loan Officer, Underwriter, CEO), a proper `<nav>` element with `aria-label` will be needed.
**Recommendation:** No immediate action needed, but plan for a `<nav aria-label="Main navigation">` wrapper when navigation links are added.

### [FE-15] Severity: Suggestion
**File(s):** `packages/ui/src/hooks/health.ts`
**Finding:** The `useHealth` hook uses `Object.assign({}, queryResult, { data: enhancedData }) as UseQueryResult<Health, Error>` to override the `data` property. This creates a shallow copy of the query result on every render where `enhancedData` changes, and the `as` cast discards type safety. A cleaner pattern would be to use `select` in the `useQuery` options to transform the data, which avoids the need for `useMemo` and the type cast entirely.
**Recommendation:** Use TanStack Query's built-in `select` option:
```ts
export function useHealth() {
    return useQuery({
        queryKey: ['health'],
        queryFn: getHealth,
        select: (data) => {
            if (data.some(s => s.name === 'UI')) return data;
            return [...data, { name: 'UI', status: 'healthy', ... }];
        },
    });
}
```

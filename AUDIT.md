# TrackFlow Frontend Performance Audit

## Scope and Conditions

Baseline captured before the audit fixes, using Lighthouse 13.5.0 and Chrome 141 against production Next.js builds. Mobile emulation used a 412 x 823 viewport, 1.75 device scale factor, 4x CPU slowdown, 150 ms RTT, and approximately 1.6 Mbps download throttling. Desktop and mobile results are reported separately. Each accessible route/profile has three cold-navigation runs; category scores are shown as median and range where they vary. Raw HTML, JSON, traces, and report screenshots are in `audit/before/`.

These localhost runs have no eligible CrUX record. Scores and timings below are lab evidence, not field Core Web Vitals. Lighthouse TBT is a main-thread diagnostic and is not field INP.

## Before Measurements

| Route / page state | Device | Performance | Accessibility | Best Practices | SEO | Median LCP | Median CLS | Median TBT |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `/uis/website` | Mobile | 100 (96-100) | 100 | 96 | 100 | 1.63 s | 0.000 | 10.5 ms |
| `/uis/website` | Desktop | 100 | 100 | 96 | 100 | 0.49 s | 0.000 | 0 ms |
| `/login` on port 3001 | Mobile | 100 | 96 | 96 | 100 | 1.45 s | 0.000 | 70 ms |
| `/login` on port 3001 | Desktop | 100 | 96 | 96 | 100 | 0.46 s | 0.000 | 0 ms |

## After Measurements

Same Lighthouse/Chrome versions, URLs, profiles, and build mode as before. Values below are medians of three cold navigations; ranges are included where runs varied.

| Route / page state | Device | Performance | Accessibility | Best Practices | SEO | Median LCP | Median CLS | Median TBT |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `/uis/website` | Mobile | 99 (96-100) | 100 | 100 | 100 | 1.60 s | 0.000 | 117 ms (37-206) |
| `/uis/website` | Desktop | 100 | 100 | 100 | 100 | 0.49 s | 0.000 | 0 ms (0-18) |
| `/login` on port 3001 | Mobile | 100 (85-100) | 100 | 100 | 100 | 1.34 s | 0.000 | 72 ms (13-581) |
| `/login` on port 3001 | Desktop | 100 | 100 | 100 | 100 | 0.38 s | 0.000 | 0 ms |

The website mobile and login mobile runs each include one elevated-TBT outlier; the median LCP remains below 2.5 s and median TBT below 200 ms. Do not infer field INP from TBT. Re-run under a quieter host if a tighter performance comparison is required.

The protected `/uis/backoffice` route redirected unauthenticated runs to `/login`; those reports are login measurements, not dashboard results. The authenticated dashboard baseline remains pending until the user signs in through the audit browser session. Do not treat the redirect report as dashboard coverage.

## Findings and Root Causes

1. **Best Practices: browser console 404 on both apps.** Lighthouse network logs showed `/favicon.ico` returning 404. Each independent Next app lacked an app icon. Added app-router SVG icons; the after reports no longer log the console error and Best Practices rose from 96 to 100.
2. **Accessibility: login touch target.** On mobile, Lighthouse identified “Forgot your password?” as 157 x 20 px, below its 24 x 24 px minimum. Added a 28 px minimum hit area while preserving the text styling; the after touch-target audit passes and Accessibility rose from 96 to 100.
3. **Website mobile Performance outlier.** One of three runs scored 96 with 212 ms TBT; the other runs scored 100 with 9.5 and 10.5 ms TBT. Median Performance is 100, median TBT is 10.5 ms, and LCP/CLS are within the stated targets. This is not a repeatable root cause, so no speculative performance optimization is justified from this result alone.

## Refactor Candidates

1. **Async resource hook:** `InventoryProducts`, `InventoryOrders`, and `BackofficeHome` repeated fetch, loading, error, stale-response cleanup, and retry state. Extracted `src/hooks/useAsyncResource.ts` and applied it to the inventory product and order lists. Data, error copy, and retry ownership remain per screen; the stock-selection request and mutations remain separate.
2. **Authorization header helper:** candidates, inventory, incident manager, `IncidentAnalyzer`, and `SupplierDirectory` duplicated `trackflow_token` lookup and bearer-header construction. Extracted `src/utils/auth-headers.ts`; existing per-client 401 cleanup/redirect behavior remains intact.

## Applied Fixes and Verification

- Added `app/icon.svg` to each Next app to address the measured missing-favicon request.
- Increased the login forgot-password link hit area to 28 px, above Lighthouse's 24 px minimum.
- Repeat Lighthouse verification is recorded in `REPORT.md` and `audit/after/`.
- Validation passed: root TypeScript check, Jest suite, root Next build, and production builds for both independent Next apps.
- No repeatable evidence justified speculative image/font/preload or JavaScript-splitting changes. Local CrUX and field INP are unavailable.
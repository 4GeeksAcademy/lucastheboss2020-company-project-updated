# Performance Audit Report

## Summary

Audited the production website and the public backoffice login page with Lighthouse 13.5.0 / Chrome 141, three cold navigations per device profile. The measured fixes removed a favicon 404 and corrected a too-small login touch target. Accessibility and Best Practices rose from 96 to 100 on the affected routes. No repeatable Core Web Vitals regression or performance optimization opportunity was established; mobile runs had high TBT variance, so no performance improvement is claimed.

The protected backoffice dashboard was not measured. Unauthenticated navigation redirected to `/login`; no authenticated browser session was available to Lighthouse in this environment. The login measurements must not be represented as dashboard measurements.

## Before / After

Scores are medians; score ranges and metric ranges show observed run-to-run variation. LCP is in seconds, TBT in milliseconds, CLS is unitless. TBT is a lab diagnostic, not field INP.

| Route / state | Device | Performance | Accessibility | Best Practices | SEO | LCP before → after | CLS before → after | TBT before → after |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Website `/uis/website` | Mobile | 100 (96-100) → 99 (96-100) | 100 → 100 | 96 → 100 | 100 → 100 | 1.63 → 1.60 | 0 → 0 | 10.5 (9.5-212) → 117 (37-206) |
| Website `/uis/website` | Desktop | 100 → 100 | 100 → 100 | 96 → 100 | 100 → 100 | 0.49 → 0.49 | 0 → 0 | 0 → 0 (0-18) |
| Backoffice `/login` | Mobile | 100 → 100 (85-100) | 96 → 100 | 96 → 100 | 100 → 100 | 1.45 → 1.34 | 0 → 0 | 70 (49-76) → 72 (13-581) |
| Backoffice `/login` | Desktop | 100 → 100 | 96 → 100 | 96 → 100 | 100 → 100 | 0.46 → 0.38 | 0 → 0 | 0 → 0 |

Lighthouse’s Performance score varies substantially when TBT has a single high outlier. Website mobile’s median score changed by one point while its TBT range remained noisy; login mobile had one 581 ms TBT / Performance 85 run, with the other two runs scoring 100. These local results are insufficient to claim a real-user performance change. All observed median LCP values are under 2.5 s and CLS is 0.

## Corrections

- Added app-router SVG icons in both Next apps. This fixes the measured `/favicon.ico` 404; browser-console audit passes and Best Practices increases from 96 to 100 in all measured route/profile groups.
- Increased the login “Forgot your password?” hit area from 20 px to 28 px. Lighthouse touch-target audit passes; login Accessibility increases from 96 to 100 on mobile and desktop.
- Extracted `src/hooks/useAsyncResource.ts` for duplicated list loading/error/retry/stale-response handling in inventory product and order lists. Form mutation and stock-selection logic remain local.
- Extracted `src/utils/auth-headers.ts` and replaced duplicated bearer-header construction in candidate, inventory, incident-manager, incident-analyzer, and supplier clients. Existing 401 redirect and cleanup behavior remains in each client.

No further performance code change was made: the high mobile TBT values were not repeatable enough to identify a root cause. The site has no hero image/font/network opportunity identified by these Lighthouse runs; avoid speculative preloads or splitting.

## Skill-Guided Review

The Core Web Vitals and performance guidance was applied to both frontends: use field p75 when available, separate field from lab data, and prioritize LCP/INP/CLS evidence over lower-priority score tuning. The web-performance review targeted the public landing page and login entry route first; the protected dashboard still requires an authenticated session. The measured favicon 404 and undersized login touch target were corrected. No image, font, preload, or code-splitting change was recommended because the captured reports did not show a repeatable benefit.

## Conditions and Evidence

- Lighthouse `13.5.0`, Chrome `141`; production Next.js builds, not dev servers.
- Mobile: Lighthouse default 412 x 823 emulation, 1.75 device scale, 4x CPU slowdown, simulated 150 ms RTT / ~1.6 Mbps download.
- Desktop: Lighthouse desktop preset, 1350 x 940, 1x scale, no mobile emulation.
- Three cold navigations per route/profile. Before and after HTML/JSON reports, traces/devtools logs, and report screenshots are under `audit/before/` and `audit/after/`.
- No eligible CrUX data for localhost. Field CWV is unavailable; lab results do not establish field CWV or INP.
- `npm run typecheck`, `npm test` (5 tests), `npm run build`, and both independent UI production builds passed.

## Remaining Verification

Capture an authenticated `/uis/backoffice` Lighthouse baseline and after run once an authorized browser session is available. The current login route is not a substitute for the protected dashboard. Review the occasional mobile TBT outlier on a quieter machine or with additional controlled runs before considering performance tuning.

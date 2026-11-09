# NematAnwar AI web app (React + Vite)
Needs Node 20.19 or newer.
```
cd apps/web
npm install
npm run dev        # http://localhost:5173, proxies /api to http://127.0.0.1:8000
npm test           # 21 tests (mocked API, labelled as such)
npm run build      # production bundle in dist/
```
Start the API first (see `docs/SETUP.md`). The access token is kept in `sessionStorage` (cleared when the tab closes).
Screens: Dashboard, Campaigns, Content Studio, Approvals, Brand Voice, Calendar (Gregorian + Hijri, 570 to 2099), Integrations, Team, Audit log.
End-to-end browser tests: `npx playwright install chromium`, start the API (with `ALLOW_PRIVATE_URLS=true`), run `node e2e/fake-wordpress.mjs`, `npm run build`, `npm run preview`, then `E2E_FAKE_WP=1 npm run e2e`. 12 tests: journeys, accessibility on 11 screens in light and dark, phone width, lost-response recovery.
The preview server sends the same security headers as nginx (`security-headers.json`).
`design-preview/index.html` is the older static preview with sample data. It is not the app.

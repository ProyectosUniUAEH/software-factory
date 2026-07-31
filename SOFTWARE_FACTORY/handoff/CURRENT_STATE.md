# CURRENT STATE - As Of 2026-07-28 (Fase 5 UI live)

## Live
- Console `prod-056dec7` — ExposureManagerModal in Apps
- API endpoints live:
  - `PATCH /api/v1/apps/{name}/exposure`
  - `POST .../environments/{env}/scale|stop|start`
  - `POST .../environments/{env}` (enable)
  - `DELETE .../environments/{env}` (remove)

## How to test (UI)
1. Open https://kaanbal-console.softwarefactory.site → Apps
2. `test-vue` → ⋮ → **Manage exposure** (or Environments → **Manage exposure**)
3. Change mode on an env → **Apply exposure changes**
4. Watch **ops console** for gitops/DNS/TS validation lines
5. Optional: Enable inactive env / Remove env / Start-Stop-Scale

## Next
- Human smoke on `test-vue`
- Fase 4 bindings / polish surfaces panel

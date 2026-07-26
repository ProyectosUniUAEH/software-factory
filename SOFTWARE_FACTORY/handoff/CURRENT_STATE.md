# CURRENT STATE - As Of 2026-05-30

## Root Workspace Cleanup Applied
- Workspace root now contains only:
  - `SOFTWARE_FACTORY/`
  - `SOFTWARE_FACTORY_SECRETS/`
- Temporary duplicate clone `infra-gitops-fix/` was removed.
- Loose root scripts were moved to `SOFTWARE_FACTORY/tools/local-root-scripts/`.
- Root contract file was moved to `SOFTWARE_FACTORY/handoff/FLOW_CONTRACT.md`.

## Platform Fixes Deployed
### kaanbal-api
- Commit deployed for platform generator hardening:
  - `a7e608a`
- `infra-gitops` shows deploy tag commit:
  - `41e1a9e` (`deploy(prod): kaanbal-api to prod-a7e608a`)
- Runtime validation confirmed `kaanbal-api-prod` image includes `prod-a7e608a`.

### fast-api
- Deploy path was fixed and validated previously (health and websocket handshake OK).

### fago-api
- App had same generator failure pattern (`invalid Kustomization: yaml line 5`).
- Immediate app manifests were repaired in infra-gitops with commit:
  - `24a6163`
- Argo validation after fix:
  - `fago-api-dev` -> Synced / Healthy
  - `fago-api-prod` -> Synced / Healthy
- Health endpoint validation:
  - `https://dev-fago-api.futurefarms.mx/health` -> 200
  - `https://fago-api.futurefarms.mx/health` -> 200

## Important Note About WebSocket Validation
- Platform ingress generation issue is fixed.
- If `/ws` returns 404 for a specific app while `/test-ws` exists, check app runtime config/code for websocket enablement and route registration in that app build.

## Continuation Checklist
1. Launch new app from wizard with websocket + selected DB binding.
2. Confirm generated `infra-gitops/apps/<app>/overlays/{dev,prod}` files render with `kubectl kustomize`.
3. Confirm Argo `Synced/Healthy` for both envs.
4. Validate:
   - `/health` returns 200
   - websocket handshake returns 101 on `/ws`
5. Confirm pod has DB env and can reach DB service port.

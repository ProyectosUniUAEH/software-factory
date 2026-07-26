# Current Agent State Snapshot

Date: 2026-05-30

## What Was Solved
- Platform-level manifest generation bug fixed in kaanbal-api deploy generator.
- Invalid overlay kustomization indentation fixed pattern (line 5 parse errors).
- Invalid ingress indentation generation fixed for per-port public ingress.
- Removed disallowed nginx configuration-snippet from generated ingress annotations.
- Avoided forcing GRPC backend-protocol on non-GRPC routes.
- Base deployment generation now injects app secrets via envFrom secretRef (optional).

## High-Value Incidents Resolved In This Cycle
1. FastAPI app generation produced invalid overlays and Argo failed with:
  1. `invalid Kustomization: yaml: line 5: did not find expected key`
2. Generated ingress YAML had malformed indentation and failed kustomize/apply.
3. Cluster admission rejected generated ingress because snippet annotations were disabled.
4. Runtime paths returned 404 until valid ingress objects were created and synced.
5. DB binding existed in overlay secretGenerator but app runtime needed guaranteed secret injection pattern.

## Infra/Runtime Validation Outcomes
- fast-api deploy path validated with health and websocket checks.
- fago-api had same historical generator pattern and was repaired in infra.
- fago-api dev/prod reached Synced and Healthy after infra corrections.

## Connection / Access Model Confirmed
1. SSH access to VPS with PEM is validated.
2. Cluster operations are executed from VPS via `kubectl`.
3. Exposure model:
  1. Public via nginx ingress (`*.futurefarms.mx`)
  2. Private via Tailscale when selected
4. For websocket probes, use HTTP/1.1 upgrade headers and valid websocket key.

## Delivery Contract Enforced
1. Push to correct org repo.
2. CI pipeline success.
3. Infra tag/manifests updated in `infra-gitops`.
4. Argo convergence (`Synced/Healthy`).
5. Runtime evidence:
  1. Health 200
  2. Websocket 101 when enabled
  3. DB binding presence/connectivity

## Workspace Policy
- Keep workspace root clean with only essential folders.
- Keep operational context under:
  - `AGENTS/`
  - `SOFTWARE_FACTORY/handoff/`

## Critical Commits To Remember
1. Platform generator hardening in `kaanbal-api`:
  1. `a7e608a`
2. Infra deploy commit referencing that backend version:
  1. `41e1a9e`
3. fago-api immediate infra repair:
  1. `24a6163`

## Handoff To New Agent (Exact Procedure)
1. Read in order:
  1. `AGENTS/START_HERE.md`
  2. `AGENTS/STATE.md`
  3. `SOFTWARE_FACTORY/handoff/FLOW_CONTRACT.md`
  4. `SOFTWARE_FACTORY/handoff/CURRENT_STATE.md`
2. Re-validate live status on VPS before editing.
3. Continue from latest remote main for each repo.
4. Keep evidence of each release gate before closing.

## Next Steps For Any New Agent
1. Read `SOFTWARE_FACTORY/handoff/CURRENT_STATE.md`.
2. Read the last 2 files in `AGENTS/sessions/` for recent work context.
3. Run live VPS checks for the app currently under development.
4. If generating new apps, confirm manifests are valid before sign-off.

## Workspace Structure (Clean State as of 2026-05-30)
```
AGENTS/
  START_HERE.md       ← first file to read
  STATE.md            ← this file
  sessions/           ← session history, read last 2 only
    TEMPLATE.md
    2026-05-30-1430-platform-fix-ws-deploy-cleanup.md
SOFTWARE_FACTORY/
  kaanbal-api/        ← remote: futurefarms-softwarefactory/kaanbal-api
  kaanbal-console/    ← remote: futurefarms-softwarefactory/kaanbal-console
  infra-gitops/       ← remote: futurefarms-softwarefactory/infra-gitops
  softwarefactory/    ← remote: futurefarms-mx/softwarefactory (installer)
  kaanbal-templates/  ← same remote as softwarefactory (templates catalog)
  handoff/            ← operational context, flow contract, current state
  tools/              ← local scripts and utilities
SOFTWARE_FACTORY_SECRETS/
  dev/keys/vps.pem    ← SSH PEM for VPS access
```

## Session Log Convention
- Each chat session creates one file in `AGENTS/sessions/YYYY-MM-DD-HHMM-topic.md`
- Files sort chronologically by name
- New agents read only the last 2 files — full context is in STATE.md and FLOW_CONTRACT.md
- Use `AGENTS/sessions/TEMPLATE.md` to write the closing session file

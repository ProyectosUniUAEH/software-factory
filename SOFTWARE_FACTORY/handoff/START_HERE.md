# START HERE - Portable Handoff

## Goal
This folder is the minimum context package to continue work on another laptop or in a new chat/agent without losing continuity.

## Read Order For Any New Agent
1. Read `SOFTWARE_FACTORY/handoff/START_HERE.md`
2. Read `SOFTWARE_FACTORY/docs/EXPOSURE_LIFECYCLE_BITACORA.md` ← **plan activo exposición/bindings/instalador**
3. Read `.cursor/skills/exposure-lifecycle/SKILL.md`
4. Read `SOFTWARE_FACTORY/handoff/CURRENT_STATE.md`
5. Read `SOFTWARE_FACTORY/handoff/FLOW_CONTRACT.md`

**Frase para retomar:** `continua bitácora exposición` o slash `/kaanbal-exposure`

## Current Canonical Repos
- `SOFTWARE_FACTORY/kaanbal-api`
- `SOFTWARE_FACTORY/kaanbal-console`
- `SOFTWARE_FACTORY/kaanbal-templates`
- `SOFTWARE_FACTORY/infra-gitops`

## What Was Fixed At Platform Level
- Generator fix in `kaanbal-api` to avoid invalid overlay `kustomization.yaml`.
- Generator fix to produce valid per-port ingress YAML indentation.
- Removed blocked nginx `configuration-snippet` usage from generated ingress annotations.
- Safer ingress annotation handling so GRPC annotation is not forced on non-GRPC ports.
- Base container generation now injects app secret via `envFrom.secretRef` (optional) for DB bindings.

## Portable Strategy (New Laptop)
1. Open workspace root at the parent containing `SOFTWARE_FACTORY` and `SOFTWARE_FACTORY_SECRETS`.
2. Read this handoff folder in the order above.
3. Validate cluster connectivity and Argo status from `FLOW_CONTRACT.md`.
4. Continue work from `CURRENT_STATE.md` pending tasks.

## Packaging Strategy (Zip)
- Preferred package root contents:
  - `SOFTWARE_FACTORY/`
  - `SOFTWARE_FACTORY_SECRETS/` (only if you intentionally need secrets offline)
- Keep root clean and avoid extra duplicates or temporary clones.

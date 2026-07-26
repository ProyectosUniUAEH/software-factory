# SOFTWARE_FACTORY Root Flow Contract

## Single Document Policy

1. This is the only operational flow document at workspace root.
2. Deployment, pipeline, ArgoCD, VPS/SSH, and validation rules are consolidated here.
3. No second contract/runbook should exist at root.

## Canonical Delivery Target

1. GitHub organization: `futurefarms-softwarefactory`.
2. Core repositories:
   1. `kaanbal-api`
   2. `kaanbal-console`
   3. `kaanbal-templates`
   4. `infra-gitops`
3. A change is not delivered until it is visible through this org flow.

## End-To-End Release Flow (Mandatory)

1. Implement locally.
2. Validate locally (lint/build/smoke as applicable).
3. Commit and push to `main` in changed repo(s).
4. Verify GitHub Actions runs are triggered and end as `completed/success`.
5. Verify `infra-gitops` received updated image tag/manifests.
6. Force sync in ArgoCD when needed.
7. Verify runtime behavior on `*.futurefarms.mx`.

## Evidence Required Before Closing Any Change

1. Commit SHA on remote main.
2. Pipeline run URL + status.
3. GitOps evidence (`newTag` or manifest update).
4. ArgoCD status (Synced/Healthy).
5. Runtime proof (working endpoint/UI behavior).

## VPS / SSH / PEM Rules

1. Credentials source: `SOFTWARE_FACTORY_SECRETS/SOFTWARE_FACTORY_SECRETS/dev/.env`.
2. Expected connection vars:
   1. `VPS_HOST`
   2. `VPS_USER`
   3. `VPS_KEY` (PEM/private key path)
3. SSH checks must be non-interactive (key-based) whenever possible.
4. If key path in `.env` does not exist on current machine, fix path first; do not proceed with password-based ad-hoc access.
5. Current workspace PEM for VPS access:
   1. `SOFTWARE_FACTORY_SECRETS/SOFTWARE_FACTORY_SECRETS/dev/keys/vps.pem`
6. Standard SSH validation command (PowerShell):
   1. `ssh -i "SOFTWARE_FACTORY_SECRETS/SOFTWARE_FACTORY_SECRETS/dev/keys/vps.pem" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 root@194.163.191.139 "echo CONNECTED; whoami; hostname"`
7. Expected successful output must include:
   1. `CONNECTED`
   2. remote user (`root`)
   3. remote host name (for example `vmi3317881`)

## Post-Deploy Verification Checklist

1. DNS resolves for target hosts.
2. Public URL does not return generic ingress/nginx 404.
3. K8s objects exist per env:
   1. Deployment
   2. Service
   3. Ingress (or Tailscale service if private)
4. Pods are Running/Ready.
5. App-specific smoke test passes (API/WS/UI/DB binding as applicable).

## FastAPI + WebSocket + Existing DB Binding Rules

1. Template database option must match actual DB engine in use.
2. `enable_websocket=true` when WS route is required.
3. DB binding must be explicit per env (example: `dev->dev`, `prod->prod`).
4. Deployment logs must show successful binding resolution per env.
5. Vault secrets must include generated binding variables (`{ALIAS}_URI`, `{ALIAS}_HOST`, etc.).

## UI Rule For Deploy Logs

1. Deployment terminal logs must remain visible after successful deployment.
2. Success summary can appear, but logs must not be hidden automatically.

## ArgoCD Force Sync Rule

1. After successful pipeline + GitOps update, force sync is allowed and recommended for immediate convergence.
2. If status remains stale, run hard refresh + sync and re-check health.

## Reset / Reinstall Policy

1. Always backup datastore before destructive operations.
2. Reinstall must consume canonical org repos and this contract flow.
3. After reinstall, repeat full verification checklist before sign-off.

## Security Rules

1. Never commit plaintext secrets/tokens/keys.
2. Do not paste sensitive values into docs, commits, or logs.
3. Rotate exposed credentials immediately if leakage is suspected.

## Change Log

1. 2026-05-30: Root-level consolidation completed. This file is now the single root runbook.
2. 2026-05-30: Added explicit VPS PEM path and executable SSH validation command/output criteria.

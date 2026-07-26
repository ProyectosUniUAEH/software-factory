# Kaanbal Engine — Software Factory

Open-source PaaS for deploying applications on any Linux VPS with Kubernetes (K3s), GitOps (ArgoCD), and a web console.

## Quick Start

### Option A — Install from your laptop (Windows)

```powershell
git clone https://github.com/futurefarms-mx/softwarefactory.git
cd softwarefactory
cp tools/env.install.example .env.install
# Edit .env.install with your VPS, GitHub, Docker Hub, Cloudflare, and Tailscale credentials
pwsh -File tools/install-from-env.ps1
```

### Option B — Install directly on the VPS

```bash
git clone https://github.com/futurefarms-mx/softwarefactory.git
cd softwarefactory/softwarefactory
bash install.sh
```

A web dashboard opens at `http://<your-ip>:3000`. Follow the 11 automated steps, then open `https://kaanbal-console.<your-domain>` to create your admin account.

## Repository Layout

```
softwarefactory/          ← you are here (monorepo root)
├── tools/                ← install helpers (install-from-env.ps1, sync scripts)
├── softwarefactory/      ← bash installer + CLI (install.sh)
├── kaanbal-api/          ← FastAPI backend
├── kaanbal-console/      ← Vue 3 web dashboard
├── kaanbal-templates/    ← deployable app templates + catalog
└── infra-gitops/         ← Kubernetes GitOps manifests
```

During installation the installer creates separate GitHub repos under your org (default: `futurefarms-mx`) for each component above.

## Requirements

| Requirement | Minimum |
|-------------|---------|
| OS | Ubuntu 22.04+ |
| RAM | 4 GB |
| Disk | 20 GB free |
| CPU | 2 cores |

You also need: a GitHub PAT with `repo` + `admin:org` scopes, Docker Hub account, Cloudflare account (for TLS/tunnel), and optionally Tailscale for VPN exposure.

## Configuration

Copy `tools/env.install.example` to `.env.install` and fill in:

- `VPS_HOST`, `VPS_USER`, `VPS_KEY` — SSH access to your server
- `KB_GIT_WORKSPACE` — GitHub org or user where app repos will be created
- `KB_GIT_TOKEN` — GitHub PAT
- `KB_DOCKER_USER` / `KB_DOCKER_TOKEN` — Docker Hub credentials
- `KB_CLOUDFLARE_TOKEN` / `KB_CLOUDFLARE_ACCOUNT_ID` — Cloudflare API
- `KB_TAILSCALE_*` — Tailscale OAuth credentials (optional)

See [softwarefactory/GUIDE.md](softwarefactory/GUIDE.md) for a full step-by-step walkthrough.

## License

Apache 2.0 — see [softwarefactory/LICENSE](softwarefactory/LICENSE).

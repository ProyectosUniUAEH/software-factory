# Kaanbal Engine - Project Context

## Project Overview
Kaanbal Engine is a Kubernetes-native PaaS that lets developers deploy applications (frontend + backend + database) in minutes without deep K8s knowledge.

## Architecture
```
kaanbal-console (Vue 3) --> kaanbal-api (FastAPI) --> MongoDB
                                  |
                            GitHub API + ArgoCD
                                  |
                    K3s Cluster (VPS Contabo)
                    - ArgoCD (GitOps), Traefik (Ingress), Vault (Secrets), Tailscale (VPN)
```

## Workspace Structure
```
SOFTWARE FACTORY/
├── softwarefactory/        ← Bash installer + Python wizard (git repo)
├── kaanbal-api/            ← FastAPI + MongoDB
├── kaanbal-console/        ← Vue 3 + Vite + Tailwind
├── kaanbal-templates/      ← JSON catalog of deployable templates
├── infra-gitops/           ← K8s manifests + Kustomize + ArgoCD + Terraform
├── .agent/                 ← Agent knowledge base (see .agent/README.md)
├── _private/               ← Credentials - DEV and PROD (never commit)
├── _old/                   ← Archived files (chat replays, deprecated tools)
└── .old_agents/            ← Archived agent lab/scripts/sessions
```

## Key Files for Context
- `.agent/README.md` - Agent quick start guide
- `.agent/context/PROJECT.md` - Full project description
- `.agent/context/ARCHITECTURE.md` - Technical architecture details
- `.agent/LESSONS.md` - Solved problems & reusable patterns
- `.agent/ROADMAP.md` - Current priorities
- `.agent/teams/roles.md` - 5-role Jira agent system
- `kaanbal-templates/catalog.json` - Template catalog

## Configuration System
- Backend: `kaanbal-api/app/defaults.py` → `app/config.py` → MongoDB `system_config`
- Frontend: `kaanbal-console/src/config.js` → `.env.*` → API runtime settings
- Infra: `infra-gitops/terraform/terraform.tfvars`

## Credentials
Unified credential store with identical DEV/PROD structure:
- DEV: `_private/dev/CREDENTIALS.txt` (VPS 161.97.112.80, 12GB)
- PROD: `_private/prod/CREDENTIALS.txt` (VPS 167.86.69.250, 24GB)
- SSH keys: `_private/{dev,prod}/keys/`
- Full guide: `_private/README.md`

## Infrastructure Access
```bash
# DEV VPS
ssh -i "_private/dev/keys/vps.pem" root@161.97.112.80

# PROD VPS
ssh -i "_private/prod/keys/vps.pem" root@167.86.69.250

# MongoDB tunnel (DEV)
ssh -i "_private/dev/keys/vps.pem" -N -L 27017:datastore.prod.svc.cluster.local:27017 root@161.97.112.80
```

## Git Workflow
- Branch: `<ISSUE-KEY>-<slug>` (e.g., `SOF-3-jira-settings`)
- Commit: `<ISSUE-KEY> <type>: <summary>` (e.g., `SOF-3 feat: add settings page`)
- Git accounts: `github-work` (dev), `github-andres` (personal) - see `~/.ssh/config`
- Push to main, verify pipeline passes before proceeding

## Rules for All Agents
1. **Never hardcode values** - use the config system
2. **Never commit credentials** - read from `_private/`
3. **One teammate per repo** - avoid file conflicts
4. **Report findings** - post evidence of what was done
5. **Read LESSONS.md** before starting infrastructure work
6. **Read `.agent/teams/roles.md`** for Jira role assignments

## Collaboration Protocol (MANDATORY)

### Three-Tier Model
1. **Copilot (VS Code) = Orchestrator** - refines ideas, creates Jira tickets, launches teams, validates
2. **Claude CLI Teams = Executors** - work autonomously using versioned prompts in `.agent/teams/prompts/`
3. **Jira = Single Source of Truth** - Project SOF, every change needs a ticket, evidence on every transition

### Team Execution
```powershell
powershell -ExecutionPolicy Bypass -File .agent/teams/scripts/run-team-prompt.ps1 `
  -PromptFile .agent/teams/prompts/<prompt>.md -Interactive
```

### Jira Config
- Site: futurefarms.atlassian.net | Project: SOF | Cloud ID: 537b033e-4b1a-4cd4-843f-61057f49a3a9
- Issue types: Epic=10000, Task=10006, Sub-task=10007, Bug=10008, Story=10005
- 5-role agent accounts: see `.agent/teams/roles.md` or `_private/dev/CREDENTIALS.txt`

### Jira Operating Rules
1. Orchestrator creates and assigns tickets to one of 5 agent accounts
2. Add `subrole:<role>` label and `[role]` comment prefix for traceability
3. Handoffs recorded in Jira comments before chat handoff
4. Validation evidence required from sf.validation before Ready for QA
5. Risk/blocking comments required from sf.riskqa before Blocked
6. If credential missing: Blocked + Jira comment + wait for human

### Workflow
```
Human idea → Copilot refines → Jira Epic + Tasks
  → Team prompt written → Human launches team
  → Team executes → Copilot validates → Jira evidence
  → Ready for QA → Human validates → Done
```

## DEV Strong Iteration Policy

For installer regressions, reinstall issues, or environment drift tickets:
1. DEV-only VPS/K3s reset
2. DEV-only GitHub repo cleanup (explicit allowlist)
3. DEV-only Docker Hub cleanup (explicit allowlist)
4. DEV-only Tailscale cleanup (explicit allowlist)
5. Full reinstall + e2e validation

Safety: Never touch prod. Never cleanup without allowlist. Blocked if scope missing.
Evidence: Before/after snapshots, prompt hash, run artifact path.

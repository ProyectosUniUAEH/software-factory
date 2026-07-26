# SOFTWARE_FACTORY Package

This folder is the clean, portable source package for Kaanbal Engine / Software Factory.

## Included

- `softwarefactory/` - installer and CLI source
- `kaanbal-api/` - FastAPI backend source
- `kaanbal-console/` - Vue console source
- `kaanbal-templates/` - deployable template catalog and manifests
- `infra-gitops/` - GitOps manifests
- `.agent/`, `AGENTS.md`, `CLAUDE.md` - agent/project context
- `agent-worklog/`, `AGENT_WORKLOG.md` - recent operational notes

## Excluded

- credentials and SSH keys
- `.env` files
- `node_modules/`, `dist/`, build artifacts and caches
- archived experiments, test data, chat replays and local Vaultwarden data

## Secrets Location

Secrets were moved outside this package:

```powershell
D:\SOFTWARE_FACTORY_SECRETS
```

DEV SSH example:

```powershell
ssh -i "D:\SOFTWARE_FACTORY_SECRETS\dev\keys\vps.pem" root@194.163.191.139
```

Do not commit `D:\SOFTWARE_FACTORY_SECRETS`.


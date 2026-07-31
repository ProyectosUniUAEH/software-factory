#!/usr/bin/env bash
# Publica kaanbal-templates en GitHub (idempotente).
set -euo pipefail
set -a
source /etc/kaanbal/installer.env
set +a
ORG="${GITHUB_ORG:-${github_org:-ProyectosUniUAEH}}"
TOKEN="${GITOPS_TOKEN:-${github_token:-${git_token:-}}}"
if [ -z "$TOKEN" ]; then
  echo "ERROR: falta github_token en /etc/kaanbal/installer.env" >&2
  exit 1
fi
export TOKEN ORG
code=$(curl -sS -o /dev/null -w "%{http_code}" \
  -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/$ORG/kaanbal-templates")
if [ "$code" = "404" ]; then
  curl -sS -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/orgs/$ORG/repos" \
    -d '{"name":"kaanbal-templates","private":true,"description":"Kaanbal deployable templates catalog"}' >/dev/null
  echo "Repo creado: $ORG/kaanbal-templates"
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/installer"
python3 -c "
import os, sys
sys.path.insert(0, os.getcwd())
import gitops_publish
from server import run
token = os.environ['TOKEN']
org = os.environ['ORG']
path = os.path.join(os.path.dirname(os.getcwd()), 'kaanbal-templates')
sha, err = gitops_publish.publish_source(run, token, org, 'kaanbal-templates', path, log_fn=print)
if err:
    print('ERROR:', err)
    sys.exit(1)
print('OK', sha[:7])
"

#!/usr/bin/env bash
set -euo pipefail
tr -d '\r' < /etc/kaanbal/installer.env > /tmp/kb-installer.env
set -a
source /tmp/kb-installer.env
set +a
ORG="${GITHUB_ORG:-${github_org:-ProyectosUniUAEH}}"
TOKEN="${GITOPS_TOKEN:-${github_token:-${git_token:-}}}"
export TOKEN ORG
code=$(curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: token $TOKEN" "https://api.github.com/repos/$ORG/kaanbal-templates")
if [ "$code" = "404" ]; then
  curl -sS -X POST -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/orgs/$ORG/repos" \
    -d '{"name":"kaanbal-templates","private":true,"description":"Kaanbal deployable templates catalog"}' >/dev/null
  echo "Repo creado"
fi
cd /home/andres/kaanbal-next/installer
python3 -c "import os,sys; sys.path.insert(0, os.getcwd()); import gitops_publish; from server import run; token=os.environ['TOKEN']; org=os.environ['ORG']; path='/home/andres/kaanbal-next/kaanbal-templates'; sha, err = gitops_publish.publish_source(run, token, org, 'kaanbal-templates', path, log_fn=print); print('ERROR:', err) if err else print('OK', sha[:7]); sys.exit(1 if err else 0)"

#!/usr/bin/env bash
# ==============================================================================
# core-upgrade.sh — actualiza el engine de una célula ya instalada (ADR-002)
# ==============================================================================
# Versión manual y auditable de la transacción descrita en el ADR. Se ejecuta
# EN EL NODO de la célula, nunca dentro del pod de la API: cuando le toca a
# `kaanbal-api` recibir su nueva imagen, el proceso que conduce el upgrade no
# puede ser el que muere. Ese es el mismo motivo por el que el servicio
# automático usará un Job y no el proceso de la API.
#
#   snapshot → preflight → drift → sync → build → promote → verify
#                                              └─── rollback ───┘
#
# Uso:
#   sudo KAANBAL_ORG=<org> bash core-upgrade.sh --ref main
#   sudo KAANBAL_ORG=<org> bash core-upgrade.sh --phase build
#   sudo bash core-upgrade.sh --snapshot
#   sudo KAANBAL_ORG=<org> bash core-upgrade.sh --rollback
set -euo pipefail

NS=prod
SOURCE_DIR=${KAANBAL_SOURCE:-/home/pam/kaanbal-source}
COMPONENTS=(kaanbal-api kaanbal-console)
KANIKO_IMAGE=gcr.io/kaniko-project/executor:v1.24.0
GIT_SECRET=kaanbal-build-git
REGISTRY_SECRET=regcred
BUILD_TIMEOUT=${BUILD_TIMEOUT:-1200}
VERIFY_TIMEOUT=${VERIFY_TIMEOUT:-420}

REF=main
PHASE=all

while (($#)); do
  case "$1" in
    --ref) shift; REF="${1:?--ref necesita una revisión}" ;;
    --source) shift; SOURCE_DIR="${1:?--source necesita una ruta}" ;;
    --phase) shift; PHASE="${1:?--phase necesita sync|build|promote|verify|all}" ;;
    --snapshot) PHASE=snapshot ;;
    --rollback) PHASE=rollback ;;
    *) echo "Argumento desconocido: $1" >&2; exit 2 ;;
  esac
  shift || true
done

log()  { printf '[kaanbal-upgrade] %s\n' "$*"; }
warn() { printf '[kaanbal-upgrade] ⚠ %s\n' "$*" >&2; }
die()  { printf '[kaanbal-upgrade] ERROR: %s\n' "$*" >&2; exit 1; }

command -v kubectl >/dev/null || die "kubectl no está en PATH"

snapshot() {
  kubectl get deploy "${COMPONENTS[@]}" -n "$NS" \
    -o jsonpath='{range .items[*]}{.metadata.name}={.spec.template.spec.containers[0].image}{"\n"}{end}'
}

log "Estado actual:"
snapshot | sed 's/^/  /'
[[ "$PHASE" == snapshot ]] && exit 0

ORG=${KAANBAL_ORG:-}
[[ -n "$ORG" ]] || die "Exporta KAANBAL_ORG con la org de GitHub de esta célula (ej: siboenglishnest)"

TOKEN=$(kubectl get secret "$GIT_SECRET" -n "$NS" -o jsonpath='{.data.token}' | base64 -d)
[[ -n "$TOKEN" ]] || die "No se pudo leer el Secret $GIT_SECRET"

DOCKER_USER=$(kubectl get deploy kaanbal-api -n "$NS" \
  -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d/ -f1)
[[ -n "$DOCKER_USER" ]] || die "No se pudo deducir el usuario de Docker Hub del Deployment"

# SHA publicado en cada repo standalone → tag, igual al que produciría el CI.
component_tag() {
  local repo=$1 sha
  sha=$(git ls-remote "https://x-access-token:$TOKEN@github.com/$ORG/$repo.git" refs/heads/main | cut -f1)
  [[ -n "$sha" ]] || die "No se pudo leer el HEAD de $ORG/$repo"
  printf 'prod-%s' "${sha:0:7}"
}

# ── Promoción: un solo commit para todos los componentes ─────────────────────
# Un commit por componente daría ventanas donde corren versiones mezcladas.
promote() {
  local mode=$1 W
  W=$(mktemp -d)
  git clone --quiet "https://x-access-token:$TOKEN@github.com/$ORG/infra-gitops.git" "$W/repo"
  cd "$W/repo"
  git config user.email "kaanbal@localhost"
  git config user.name "Kaanbal Upgrade"

  if [[ "$mode" == revert ]]; then
    git revert --no-edit HEAD >/dev/null || { cd /; rm -rf "$W"; die "No se pudo revertir el último commit de infra-gitops"; }
  else
    local c tag f
    for c in "${COMPONENTS[@]}"; do
      tag=$(component_tag "$c")
      f="apps/$c/overlays/prod/kustomization.yaml"
      [[ -f "$f" ]] || { cd /; rm -rf "$W"; die "No existe $f en infra-gitops"; }
      sed -i "s|^\( *newTag:\).*|\1 $tag|" "$f"
      log "  $c → $tag"
    done
    git add -A
    if git diff --cached --quiet; then
      log "infra-gitops ya apunta a estos tags"
      cd /; rm -rf "$W"; return 0
    fi
    git commit --quiet -m "upgrade: promover core del monorepo@${UPSTREAM:0:7}"
  fi

  git push --quiet origin HEAD:main
  cd /; rm -rf "$W"

  # Forzar reconciliación en vez de esperar el poll de ArgoCD.
  local app
  for app in "${COMPONENTS[@]}"; do
    kubectl annotate application "${app}-prod" -n argocd \
      argocd.argoproj.io/refresh=hard --overwrite >/dev/null 2>&1 || true
  done
}

# ── Verificación: la imagen debe llegar Y el pod quedar listo ────────────────
verify() {
  local deadline=$((SECONDS + VERIFY_TIMEOUT)) c want ok=1
  local got=""
  for c in "${COMPONENTS[@]}"; do
    want=$(component_tag "$c")
    got=""
    log "Esperando $c → $want"
    while ((SECONDS < deadline)); do
      got=$(kubectl get deploy "$c" -n "$NS" \
        -o jsonpath='{.spec.template.spec.containers[0].image}' | awk -F: '{print $NF}')
      [[ "$got" == "$want" ]] && break
      sleep 10
    done
    if [[ "$got" != "$want" ]]; then
      warn "$c sigue en $got: ArgoCD no aplicó el tag nuevo"
      ok=0; continue
    fi
    if ! kubectl rollout status "deploy/$c" -n "$NS" --timeout=180s >/dev/null 2>&1; then
      warn "$c no alcanzó Ready con la imagen nueva"
      ok=0
    else
      log "  $c listo en $want"
    fi
  done
  return $((1 - ok))
}

if [[ "$PHASE" == rollback ]]; then
  log "Revirtiendo el último commit de infra-gitops"
  UPSTREAM=""
  promote revert
  log "Revertido. ArgoCD volverá a la imagen anterior; las imágenes siguen publicadas."
  exit 0
fi

# ── Preflight + sync ─────────────────────────────────────────────────────────
UPSTREAM=""
if [[ "$PHASE" == all || "$PHASE" == sync ]]; then
  [[ -d "$SOURCE_DIR/SOFTWARE_FACTORY" ]] || die "No hay checkout del monorepo en $SOURCE_DIR"
  log "Actualizando el checkout a $REF"
  git -C "$SOURCE_DIR" fetch --depth 50 origin "$REF" >/dev/null 2>&1
  git -C "$SOURCE_DIR" checkout --quiet --detach FETCH_HEAD
  UPSTREAM=$(git -C "$SOURCE_DIR" rev-parse HEAD)
  log "Monorepo en ${UPSTREAM:0:7}"

  POD=$(kubectl get pod -n "$NS" -l app=kaanbal-api -o jsonpath='{.items[0].metadata.name}')
  log "Preflight de imports dentro de $POD"
  kubectl cp "$SOURCE_DIR/SOFTWARE_FACTORY/kaanbal-api/app" "$NS/$POD:/tmp/pf-app" >/dev/null
  kubectl cp "$SOURCE_DIR/SOFTWARE_FACTORY/kaanbal-api/main.py" "$NS/$POD:/tmp/pf-main.py" >/dev/null
  kubectl exec -n "$NS" "$POD" -- sh -c '
    set -e; rm -rf /tmp/pf; mkdir -p /tmp/pf
    mv /tmp/pf-app /tmp/pf/app; cp /tmp/pf-main.py /tmp/pf/main.py
    cd /tmp/pf && python -c "
import importlib, sys
sys.path.insert(0, \"/tmp/pf\")
for m in [\"app.routers.core\",\"app.routers.apps\",\"app.routers.domains\",\"app.services.app_deployer\",\"main\"]:
    importlib.import_module(m)
print(\"preflight ok\")
"
    rm -rf /tmp/pf /tmp/pf-main.py
  ' || die "El código nuevo no importa contra las dependencias reales. No se despliega nada."

  # Deriva: nunca pisar código local en silencio.
  for c in "${COMPONENTS[@]}"; do
    count=$(curl -sf -H "Authorization: Bearer $TOKEN" \
      "https://api.github.com/repos/$ORG/$c/commits?per_page=100" | grep -c '"sha"' || echo 0)
    if [[ "$count" -gt 3 ]]; then
      die "$ORG/$c tiene historia propia ($count commits): puede estar tuneado.
     Resuelve la deriva antes de sobrescribirlo (ver ADR-002)."
    fi
  done

  for c in "${COMPONENTS[@]}"; do
    W=$(mktemp -d)
    git clone --quiet "https://x-access-token:$TOKEN@github.com/$ORG/$c.git" "$W/repo"
    find "$W/repo" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
    ( cd "$SOURCE_DIR/SOFTWARE_FACTORY/$c" \
      && tar --exclude=.git --exclude=node_modules --exclude=dist \
             --exclude=__pycache__ --exclude='*.pyc' -cf - . ) \
    | ( cd "$W/repo" && tar -xf - )
    cd "$W/repo"
    git config user.email "kaanbal@localhost"
    git config user.name "Kaanbal Upgrade"
    git add -A
    if git diff --cached --quiet; then
      log "$c: sin cambios"
    else
      git commit --quiet -m "upgrade: sync desde software-factory@${UPSTREAM:0:7}"
      git push --quiet origin HEAD:main
      log "$c publicado en $ORG/$c → $(git rev-parse HEAD | cut -c1-7)"
    fi
    cd /; rm -rf "$W"
  done
fi

# ── Build ────────────────────────────────────────────────────────────────────
if [[ "$PHASE" == all || "$PHASE" == build ]]; then
  kubectl create secret generic "$GIT_SECRET" -n "$NS" \
    --from-literal=token="$TOKEN" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  for c in "${COMPONENTS[@]}"; do
    TAG=$(component_tag "$c")
    JOB="kaanbal-build-${c}-${TAG#prod-}"
    log "Construyendo $c:$TAG (Job $JOB)"
    kubectl delete job "$JOB" -n "$NS" --ignore-not-found >/dev/null 2>&1

    kubectl apply -f - >/dev/null <<JOBEOF
apiVersion: batch/v1
kind: Job
metadata:
  name: $JOB
  namespace: $NS
  labels:
    kaanbal-engine.io/component: builder
spec:
  backoffLimit: 1
  ttlSecondsAfterFinished: 1800
  template:
    metadata:
      labels:
        kaanbal-engine.io/component: builder
    spec:
      restartPolicy: Never
      containers:
      - name: kaniko
        image: $KANIKO_IMAGE
        args:
        - --context=git://github.com/$ORG/$c.git#refs/heads/main
        - --dockerfile=Dockerfile
        - --destination=index.docker.io/$DOCKER_USER/$c:$TAG
        - --single-snapshot
        - --verbosity=info
        env:
        - name: GIT_USERNAME
          value: x-access-token
        - name: GIT_PASSWORD
          valueFrom:
            secretKeyRef:
              name: $GIT_SECRET
              key: token
        resources:
          requests: {cpu: 500m, memory: 1Gi}
          limits: {cpu: "4", memory: 4Gi}
        volumeMounts:
        - name: docker-config
          mountPath: /kaniko/.docker
      volumes:
      - name: docker-config
        secret:
          secretName: $REGISTRY_SECRET
          items:
          - key: .dockerconfigjson
            path: config.json
JOBEOF

    if ! kubectl wait --for=condition=complete "job/$JOB" -n "$NS" \
         --timeout="${BUILD_TIMEOUT}s" >/dev/null 2>&1; then
      warn "El build de $c no completó. Últimas líneas:"
      kubectl logs "job/$JOB" -n "$NS" --tail=25 2>&1 | sed 's/^/    /' || true
      die "Build fallido: no se promueve nada. La célula sigue en su versión anterior."
    fi
    log "  $c:$TAG publicado en Docker Hub"
  done
fi

# ── Promote + verify, con rollback automático ────────────────────────────────
if [[ "$PHASE" == all || "$PHASE" == promote ]]; then
  log "Promoviendo tags en infra-gitops"
  promote apply

  if verify; then
    log "✅ Upgrade verificado."
    snapshot | sed 's/^/  /'
  else
    warn "La verificación falló — revirtiendo automáticamente"
    promote revert
    if verify; then
      die "Se revirtió a la versión anterior y quedó sana. Revisa los logs del build."
    fi
    die "Rollback aplicado pero la célula no verifica. Revisa 'kubectl get pods -n $NS'."
  fi
fi

if [[ "$PHASE" == verify ]]; then
  verify && log "✅ Verificado." || die "No verifica."
fi

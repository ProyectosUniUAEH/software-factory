#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
echo "=== Starting K3s Setup ==="

K3S_VERSION="${k3s_version}"
K3S_TOKEN="${k3s_token}"
DOMAIN="${domain_name}"
EMAIL="${email_letsencrypt}"
EIP="${elastic_ip}"
ARGOCD_PASS="${argocd_password}"
GIT_USER="${git_username}"
GIT_TOKEN="${git_token}"
GIT_REPO="${git_repo_url}"
TS_ID="${tailscale_client_id}"
TS_SECRET="${tailscale_client_secret}"

apt-get update -y && apt-get install -y curl wget jq git python3-pip
pip3 install bcrypt

# Get AWS instance metadata for provider-id (needed by Cluster Autoscaler)
IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 300")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" http://169.254.169.254/latest/meta-data/placement/availability-zone)
PROVIDER_ID="aws:///$AZ/$INSTANCE_ID"
echo ">>> Provider ID: $PROVIDER_ID"

# Add swap to prevent OOM on small instances
fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' >> /etc/sysctl.conf
sysctl vm.swappiness=10

curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$K3S_VERSION" sh -s - server \
  --token "$K3S_TOKEN" --tls-san "$EIP" --tls-san "$DOMAIN" --tls-san "*.$DOMAIN" \
  --disable traefik --disable servicelb --write-kubeconfig-mode 644 --node-name "master-1" \
  --kubelet-arg "provider-id=$PROVIDER_ID" \
  --node-taint "node-role.kubernetes.io/control-plane:NoSchedule"

sleep 30
mkdir -p /home/ubuntu/.kube
cp /etc/rancher/k3s/k3s.yaml /home/ubuntu/.kube/config
chown -R ubuntu:ubuntu /home/ubuntu/.kube
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
until kubectl get nodes | grep -q "Ready"; do sleep 5; done
echo "=== K3s Ready ==="

curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add jetstack https://charts.jetstack.io
helm repo add aws-ebs-csi-driver https://kubernetes-sigs.github.io/aws-ebs-csi-driver
helm repo update

kubectl create ns ingress-nginx --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx \
  --set controller.kind=DaemonSet --set controller.hostPort.enabled=true \
  --set controller.hostPort.ports.http=80 --set controller.hostPort.ports.https=443 \
  --set controller.service.type=ClusterIP --set controller.ingressClassResource.default=true \
  --set controller.config.use-forwarded-headers=true \
  --set controller.tolerations[0].key=node-role.kubernetes.io/control-plane \
  --set controller.tolerations[0].operator=Exists \
  --set controller.tolerations[0].effect=NoSchedule \
  --wait --timeout 5m
kubectl wait --for=condition=ready pod -l app.kubernetes.io/component=controller -n ingress-nginx --timeout=120s

kubectl create ns cert-manager --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager \
  --set installCRDs=true --set prometheus.enabled=false --wait --timeout 5m
sleep 20
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=120s

cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: $EMAIL
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

helm upgrade --install aws-ebs-csi-driver aws-ebs-csi-driver/aws-ebs-csi-driver \
  -n kube-system --set controller.replicaCount=1 --set node.tolerateAllTaints=true \
  --set controller.extraVolumeTags.Project="${project_name}" \
  --set controller.extraVolumeTags.Domain="${domain_name}" \
  --set controller.extraVolumeTags.ManagedBy="software-factory" \
  --wait --timeout 5m
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=aws-ebs-csi-driver -n kube-system --timeout=120s || true

cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-gp3
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
parameters:
  type: gp3
  encrypted: "true"
allowVolumeExpansion: true
---
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-gp3-retain
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Retain
parameters:
  type: gp3
  encrypted: "true"
allowVolumeExpansion: true
EOF
kubectl patch storageclass local-path -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}' 2>/dev/null || true

# --- Metrics Server (enables kubectl top and HPA) ---
# K3s v1.29+ comes with metrics-server pre-installed (without Helm labels).
# Only install via Helm if no metrics-server deployment exists already.
if kubectl get deployment metrics-server -n kube-system >/dev/null 2>&1; then
  echo "metrics-server already present (K3s built-in), skipping Helm install"
else
  helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server
  helm repo update
  helm upgrade --install metrics-server metrics-server/metrics-server \
    -n kube-system \
    --set args[0]=--kubelet-insecure-tls \
    --wait --timeout 5m || echo "WARN: metrics-server helm install failed, continuing"
fi

# --- Cluster Autoscaler (scales ASG based on pending pods) ---
helm repo add autoscaler https://kubernetes.github.io/autoscaler
helm repo update
helm upgrade --install cluster-autoscaler autoscaler/cluster-autoscaler \
  -n kube-system \
  --set autoDiscovery.clusterName=${project_name} \
  --set awsRegion=${aws_region} \
  --set cloudProvider=aws \
  --set extraArgs.balance-similar-node-groups=true \
  --set extraArgs.skip-nodes-with-local-storage=false \
  --wait --timeout 5m

kubectl create ns argocd --dry-run=client -o yaml | kubectl apply -f -
# Use --server-side to avoid "annotations too long" error on ArgoCD CRDs (>262KB)
kubectl apply --server-side --force-conflicts -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s
curl -sSL -o /usr/local/bin/argocd https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
chmod +x /usr/local/bin/argocd

if [ -n "$ARGOCD_PASS" ]; then
  HP=$(python3 -c "import bcrypt; print(bcrypt.hashpw('$ARGOCD_PASS'.encode(), bcrypt.gensalt()).decode())")
  MT=$(date +%FT%T%Z)
  kubectl -n argocd patch secret argocd-secret -p "{\"stringData\":{\"admin.password\":\"$HP\",\"admin.passwordMtime\":\"$MT\"}}"
fi

if [ -n "$GIT_TOKEN" ]; then
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: private-repo-creds
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
stringData:
  type: git
  url: $GIT_REPO
  username: $GIT_USER
  password: $GIT_TOKEN
EOF
fi

cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-server
  namespace: argocd
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: HTTPS
    nginx.ingress.kubernetes.io/ssl-passthrough: "true"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - cd.$DOMAIN
    secretName: argocd-server-tls
  rules:
  - host: cd.$DOMAIN
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: argocd-server
            port:
              number: 443
EOF

# ==============================================================================
# EBS VOLUME RECOVERY
# If this is a re-deployment (destroy + apply), orphaned EBS volumes from the 
# previous cluster may exist in "available" state. Pre-create PersistentVolumes 
# pointing to them so ArgoCD's PVCs bind to existing data instead of creating 
# new empty volumes.
# The EBS CSI driver automatically tags volumes with PVC namespace + name.
# The IAM role (AmazonEBSCSIDriverPolicy) already has ec2:DescribeVolumes.
# ==============================================================================
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo "${aws_region}")

echo "=== Checking for orphaned EBS volumes to recover (region: $REGION) ==="
RECOVERED_VOLS=$(aws ec2 describe-volumes \
  --region "$REGION" \
  --filters \
    "Name=status,Values=available" \
    "Name=tag:ManagedBy,Values=software-factory" \
    "Name=tag:kubernetes.io/created-for/pvc/name,Values=*" \
  --query 'Volumes[*].{
    id:VolumeId,
    az:AvailabilityZone,
    size:Size,
    pvc:Tags[?Key==`kubernetes.io/created-for/pvc/name`].Value|[0],
    ns:Tags[?Key==`kubernetes.io/created-for/pvc/namespace`].Value|[0]
  }' \
  --output json 2>/dev/null || echo "[]")

RECOVER_COUNT=$(echo "$RECOVERED_VOLS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
echo "Found $RECOVER_COUNT orphaned EBS volumes"

if [ "$RECOVER_COUNT" -gt "0" ]; then
  echo "Creating pre-bound PersistentVolumes for recovered data..."
  echo "$RECOVERED_VOLS" | python3 << 'PY_EOF'
import json, sys, subprocess
vols = json.load(sys.stdin)
for v in vols:
    pvc_ns  = v.get('ns','')
    pvc_name = v.get('pvc','')
    vol_id  = v.get('id','')
    az      = v.get('az','')
    size    = v.get('size', 10)
    if not all([pvc_ns, pvc_name, vol_id]):
        continue
    pv_name = f"recover-{pvc_ns}-{pvc_name}"
    manifest = f"""apiVersion: v1
kind: PersistentVolume
metadata:
  name: {pv_name}
  annotations:
    pv.kubernetes.io/provisioned-by: ebs.csi.aws.com
  labels:
    recovered-from: ebs
spec:
  capacity:
    storage: {size}Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ebs-gp3-retain
  csi:
    driver: ebs.csi.aws.com
    volumeHandle: {vol_id}
    fsType: ext4
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: topology.kubernetes.io/zone
          operator: In
          values:
          - {az}
  claimRef:
    namespace: {pvc_ns}
    name: {pvc_name}
"""
    r = subprocess.run(['kubectl', 'apply', '-f', '-'], input=manifest.encode(), capture_output=True)
    status = 'RECOVERED' if r.returncode == 0 else r.stderr.decode()
    print(f"  {pv_name} [{vol_id}] → {status}")
PY_EOF
  echo "Volume recovery complete"
fi

cd /tmp
RP=$(echo "$GIT_REPO" | sed 's|https://||')
git clone "https://$GIT_USER:$GIT_TOKEN@$RP" bootstrap 2>/dev/null || true
[ -f "bootstrap/argocd/bootstrap/app-of-apps.yaml" ] && kubectl apply -f bootstrap/argocd/bootstrap/app-of-apps.yaml
rm -rf /tmp/bootstrap

if [ -n "$TS_ID" ] && [ -n "$TS_SECRET" ]; then
kubectl create ns tailscale --dry-run=client -o yaml | kubectl apply -f -
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: operator-oauth
  namespace: tailscale
type: Opaque
stringData:
  client_id: $TS_ID
  client_secret: $TS_SECRET
EOF
fi

# Create Docker Hub credentials secret for Kaanbal API
if [ -n "${docker_username}" ] && [ -n "${docker_token}" ]; then
kubectl create ns prod --dry-run=client -o yaml | kubectl apply -f -
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: docker-hub-creds
  namespace: prod
type: Opaque
stringData:
  username: ${docker_username}
  token: ${docker_token}
EOF
fi

for ns in dev staging prod apps monitoring vault; do
  kubectl create ns $ns --dry-run=client -o yaml | kubectl apply -f -
done

# --- Kaanbal Admin Bootstrap Secret ---
# Stored in K8s; the kaanbal-bootstrap-job (PostSync) reads this to create the first admin user
if [ -n "${kaanbal_admin_user}" ] && [ -n "${kaanbal_admin_password}" ]; then
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: kaanbal-bootstrap-creds
  namespace: prod
type: Opaque
stringData:
  username: "${kaanbal_admin_user}"
  password: "${kaanbal_admin_password}"
EOF
fi

echo "=== Setup Complete ==="
kubectl get nodes
kubectl get sc
touch /home/ubuntu/.software-factory-installed

# ──────────────────────────────────────────────────────────────────────────────
# POST-PROVISIONING: Wait for kaanbal-api + seed MongoDB
# Runs in background so it doesn't block the initial cloud-init completion.
# Waits for ArgoCD to sync kaanbal-api, then:
#   1. Seeds system_config (argocd_url, domain, etc.)
#   2. Calls POST /api/v1/system/import-from-cluster to derive app exposures
# NOTE: Terraform template vars use $${...}; bash vars use $VAR (no braces).
# ──────────────────────────────────────────────────────────────────────────────
KAANBAL_API="https://kaanbal-api.${domain_name}"
KAANBAL_USER="${kaanbal_admin_user}"
KAANBAL_PASS="${kaanbal_admin_password}"
KAANBAL_DOMAIN="${domain_name}"
KAANBAL_ARGOCD_URL="https://cd.${domain_name}"
KAANBAL_GIT_USER="${git_username}"
KAANBAL_GIT_TOKEN="${git_token}"
KAANBAL_BB_EMAIL="${bitbucket_email}"
KAANBAL_BB_WS="${bitbucket_workspace}"
KAANBAL_DH_USER="${docker_username}"
KAANBAL_DH_TOKEN="${docker_token}"
KAANBAL_VAULT_TOKEN="${vault_init_token}"
KAANBAL_VAULT_HOST="${vault_hostname}"
KAANBAL_TS_SUFFIX="${tailscale_dns_suffix}"

cat > /usr/local/bin/kaanbal-post-provision.sh <<"SCRIPT_EOF"
#!/bin/bash
# =============================================================================
# Kaanbal Post-Provisioning SCRIPT
# Runs once after terraform apply (in background, does not block cloud-init).
# Goals:
#   1. Wait for kaanbal-api to be healthy
#   2. Seed MongoDB system_config with all terraform.tfvars credentials
#   3. Validate Bitbucket core repos exist (log warning if missing)
#   4. Call import-from-cluster to derive app exposures from K8s Ingresses
# IDEMPOTENT: safe to re-run after destroy/apply
# =============================================================================
set -e
LOG=/var/log/kaanbal-post-provision.log

KAANBAL_API="__KAANBAL_API__"
KAANBAL_USER="__KAANBAL_USER__"
KAANBAL_PASS="__KAANBAL_PASS__"
DOMAIN="futurefarms.mx"
ARGOCD_URL="__ARGOCD_URL__"
GIT_USER="futurefarms-softwarefactory"
GIT_TOKEN="__GIT_TOKEN__"
BB_EMAIL="__BB_EMAIL__"
BB_WS="__BB_WS__"
DOCKER_USER="andresupmh"
DOCKER_TOKEN="__DOCKER_TOKEN__"
VAULT_TOKEN="__VAULT_TOKEN__"
VAULT_HOST="__VAULT_HOST__"
TS_SUFFIX="__TS_SUFFIX__"

log() { echo "[$(date +%H:%M:%S)] [kaanbal-post-provision] $*" | tee -a "$LOG"; }

log "==================================================="
log "  Kaanbal Post-Provisioning — domain: $DOMAIN"
log "==================================================="

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Wait for kaanbal-api pod (up to 15 min)
# ─────────────────────────────────────────────────────────────────────────────
log "Step 1: Waiting for kaanbal-api deployment..."
for i in $(seq 1 90); do
  READY=$(kubectl get pods -n prod -l app=kaanbal-api --no-headers 2>/dev/null | grep -c "1/1.*Running" || true)
  if [ "$READY" -ge 1 ]; then
    log "  kaanbal-api pod ready (attempt $i)"
    break
  fi
  if [ "$i" -eq 90 ]; then
    log "  ERROR: kaanbal-api never became ready after 15min. Check ArgoCD."
    exit 1
  fi
  log "  [$i/90] not ready — sleeping 10s..."
  sleep 10
done

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Wait for HTTP health (up to 5 min)
# ─────────────────────────────────────────────────────────────────────────────
log "Step 2: Waiting for HTTP health..."
for i in $(seq 1 30); do
  HSTATUS=$(curl -sk "$KAANBAL_API/api/v1/health" 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "error")
  if [ "$HSTATUS" = "healthy" ]; then
    log "  API healthy"
    break
  fi
  if [ "$i" -eq 30 ]; then
    log "  ERROR: API never healthy. Last status: $HSTATUS"
    exit 1
  fi
  log "  [$i/30] status=$HSTATUS — sleeping 10s..."
  sleep 10
done

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Authenticate
# ─────────────────────────────────────────────────────────────────────────────
log "Step 3: Authenticating as $KAANBAL_USER..."
TOKEN=$(curl -sf -X POST "$KAANBAL_API/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$KAANBAL_USER&password=$KAANBAL_PASS" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  log "  ERROR: Could not get auth token. Is kaanbal_admin_user/password correct?"
  exit 1
fi
log "  Auth OK"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Idempotency check: skip seeding if already configured
# ─────────────────────────────────────────────────────────────────────────────
log "Step 4: Checking idempotency..."
CURRENT_DOMAIN=$(curl -sk "$KAANBAL_API/api/v1/admin/settings" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('domain',''))" 2>/dev/null || echo "")

if [ "$CURRENT_DOMAIN" = "$DOMAIN" ]; then
  log "  system_config already seeded for domain=$DOMAIN — skipping full re-seed"
  log "  (To force re-seed: delete _id=main from MongoDB system_config and re-run)"
  SKIP_SEED=1
else
  SKIP_SEED=0
  log "  system_config empty or different domain ('$CURRENT_DOMAIN' vs '$DOMAIN') — seeding"
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Seed system_config (all credentials from terraform.tfvars)
# ─────────────────────────────────────────────────────────────────────────────
if [ "$SKIP_SEED" -eq 0 ]; then
  log "Step 5: Seeding system_config with all credentials..."

  # Build JSON payload dynamically — skip empty optional fields
  PAYLOAD=$(python3 << PYEOF
import json

cfg = {
    "domain":               "$DOMAIN",
    "argocd_url":           "$ARGOCD_URL",
    "git_username":         "$GIT_USER",
    "git_token":            "$GIT_TOKEN",
    "bitbucket_email":      "$BB_EMAIL",
    "bitbucket_workspace":  "$BB_WS",
    "dockerhub_username":   "$DOCKER_USER",
    "dockerhub_token":      "$DOCKER_TOKEN",
}

# Optional: only include if provided
if "$VAULT_TOKEN":    cfg["vault_token"]          = "$VAULT_TOKEN"
if "$VAULT_HOST":     cfg["vault_hostname"]        = "$VAULT_HOST"
if "$VAULT_HOST":     cfg["vault_addr"]            = "http://vault.vault.svc.cluster.local:8200"
if "$TS_SUFFIX":      cfg["tailscale_dns_suffix"]  = "$TS_SUFFIX"

print(json.dumps(cfg))
PYEOF
)

  SEED_RESULT=$(curl -sf -X PUT "$KAANBAL_API/api/v1/admin/settings" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" 2>/dev/null || echo '{"error":"seed failed"}')
  echo "$SEED_RESULT" | python3 -c "
import json,sys
r=json.load(sys.stdin)
if 'error' in r: print('  WARN seed:', r)
else: print('  system_config seeded OK — fields:', list(r.keys()))
" 2>/dev/null | tee -a "$LOG"
else
  log "Step 5: SKIPPED (idempotency)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — Validate core Bitbucket repos exist
# ─────────────────────────────────────────────────────────────────────────────
log "Step 6: Validating Bitbucket core repos..."
CORE_REPOS="kaanbal-api kaanbal-console infra-gitops"
MISSING_REPOS=""
for REPO in $CORE_REPOS; do
  HTTP_CODE=$(curl -sk -o /dev/null -w "%%{http_code}" \
    "https://api.bitbucket.org/2.0/repositories/$BB_WS/$REPO" \
    -u "$BB_EMAIL:$GIT_TOKEN" 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    log "  ✓ $BB_WS/$REPO exists"
  else
    log "  ✗ WARN: $BB_WS/$REPO NOT FOUND (HTTP $HTTP_CODE)"
    MISSING_REPOS="$MISSING_REPOS $REPO"
  fi
done
if [ -n "$MISSING_REPOS" ]; then
  log ""
  log "  WARNING: Missing repos:$MISSING_REPOS"
  log "  The platform can still run from Docker Hub pre-built images."
  log "  To enable CI/CD pipelines for these apps, create the repos in"
  log "  Bitbucket workspace '$BB_WS' and push the source code."
fi

# ─────────────────────────────────────────────────────────────────────────────
# STEP 7 — Wait for ArgoCD to sync app ingresses, then import exposures
# ─────────────────────────────────────────────────────────────────────────────
log "Step 7: Waiting 90s for ArgoCD to sync app ingresses..."
sleep 90

log "Step 7b: Calling POST /system/import-from-cluster to map app exposures..."
IRESULT=$(curl -sf -X POST "$KAANBAL_API/api/v1/system/import-from-cluster" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" 2>/dev/null \
  || echo '{"error":"import-from-cluster failed"}')
echo "$IRESULT" | python3 -m json.tool 2>/dev/null | tee -a "$LOG"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 8 — Auto-seed vault root token from K8s Secret (vault-auto-init job)
# If VAULT_TOKEN was empty in tfvars (new cluster), the vault-auto-init-job
# PostSync hook writes the root token to Secret vault/vault-init-keys.
# We wait for it and then seed it into MongoDB system_config automatically.
# ─────────────────────────────────────────────────────────────────────────────
log "Step 8: Checking Vault initialization..."
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
if [ -z "$VAULT_TOKEN" ]; then
  log "  vault_token not set in tfvars — waiting for vault-auto-init job (up to 10min)..."
  for i in $(seq 1 60); do
    SECRET_VAL=$(kubectl get secret vault-init-keys -n vault \
      -o jsonpath='{.data.root-token}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
    if [ -n "$SECRET_VAL" ]; then
      VAULT_TOKEN="$SECRET_VAL"
      log "  ✅ Got vault root token from vault-init-keys (attempt $i)"
      break
    fi
    if [ "$i" -eq 60 ]; then
      log "  WARN: vault-init-keys secret not found after 10min — continuing without vault seed"
      log "  Vault token must be seeded manually: admin > Infrastructure > Vault"
    else
      log "  [$i/60] vault-init-keys not ready — sleeping 10s..."
      sleep 10
    fi
  done
else
  log "  vault_token provided in tfvars — using terraform value"
fi

if [ -n "$VAULT_TOKEN" ] && [ -n "$VAULT_HOST" ]; then
  log "  Seeding vault credentials into system_config..."
  V_PAYLOAD=$(python3 -c "
import json
print(json.dumps({
    'vault_token':    '$VAULT_TOKEN',
    'vault_hostname': '$VAULT_HOST',
    'vault_addr':     'http://vault.vault.svc.cluster.local:8200',
}))
")
  V_RESULT=$(curl -sf -X PUT "$KAANBAL_API/api/v1/admin/settings" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$V_PAYLOAD" 2>/dev/null || echo '{"error":"vault seed failed"}')
  echo "$V_RESULT" | python3 -c "
import json,sys
r=json.load(sys.stdin)
if 'error' in r: print('  WARN vault seed:', r)
else: print('  ✅ Vault credentials seeded OK')
" 2>/dev/null | tee -a "$LOG"
elif [ -z "$VAULT_HOST" ]; then
  log "  SKIP: VAULT_HOST not configured — vault seeding skipped"
fi

log "==================================================="
log "  Kaanbal Post-Provisioning COMPLETE"
log "  Console: https://kaanbal-console.$DOMAIN"
log "  ArgoCD:  $ARGOCD_URL"
if [ -n "$TS_SUFFIX" ]; then
log "  Tailscale DNS suffix: $TS_SUFFIX"
fi
log "==================================================="
SCRIPT_EOF

# Substitute Terraform-expanded values into the script
sed -i "s|__KAANBAL_API__|$KAANBAL_API|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__KAANBAL_USER__|$KAANBAL_USER|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__KAANBAL_PASS__|$KAANBAL_PASS|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|futurefarms.mx|$KAANBAL_DOMAIN|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__ARGOCD_URL__|$KAANBAL_ARGOCD_URL|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|futurefarms-softwarefactory|$KAANBAL_GIT_USER|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__GIT_TOKEN__|$KAANBAL_GIT_TOKEN|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__BB_EMAIL__|$KAANBAL_BB_EMAIL|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__BB_WS__|$KAANBAL_BB_WS|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|andresupmh|$KAANBAL_DH_USER|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__DOCKER_TOKEN__|$KAANBAL_DH_TOKEN|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__VAULT_TOKEN__|$KAANBAL_VAULT_TOKEN|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__VAULT_HOST__|$KAANBAL_VAULT_HOST|g" /usr/local/bin/kaanbal-post-provision.sh
sed -i "s|__TS_SUFFIX__|$KAANBAL_TS_SUFFIX|g" /usr/local/bin/kaanbal-post-provision.sh
chmod +x /usr/local/bin/kaanbal-post-provision.sh

# Run post-provisioning in background (doesn't block cloud-init)
nohup bash /usr/local/bin/kaanbal-post-provision.sh > /var/log/kaanbal-post-provision.log 2>&1 &
echo "Post-provisioning job started (PID=$!). Logs: /var/log/kaanbal-post-provision.log"

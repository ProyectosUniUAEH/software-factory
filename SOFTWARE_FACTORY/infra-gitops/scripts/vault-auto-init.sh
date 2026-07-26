#!/bin/bash
# ==============================================================================
# Vault Auto-Init Script
# ==============================================================================
# This script runs as a K8s Job after cluster bootstrap.
# It waits for Vault to be ready, initializes it (if fresh), and stores
# the root token + unseal keys in a K8s secret for safekeeping.
#
# With AWS KMS auto-unseal configured, Vault automatically unseals on restart.
# This script only needs to run ONCE on a fresh Vault installation.
# ==============================================================================

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://vault.vault.svc.cluster.local:8200}"
NAMESPACE="${VAULT_NAMESPACE:-vault}"
SECRET_NAME="${SECRET_NAME:-vault-init-keys}"
MAX_WAIT="${MAX_WAIT:-600}"  # 10 minutes max wait

echo "🔐 Vault Auto-Init Script"
echo "  Vault address: $VAULT_ADDR"
echo "  Namespace: $NAMESPACE"
echo "  Secret name: $SECRET_NAME"
echo ""

# ==============================================================================
# 1. Wait for Vault pod to be ready
# ==============================================================================
echo "⏳ Waiting for Vault to be reachable..."
elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -s -o /dev/null -w "%{http_code}" "$VAULT_ADDR/v1/sys/health" 2>/dev/null | grep -qE "200|429|501|503"; then
        echo "  ✅ Vault is reachable"
        break
    fi
    sleep 10
    elapsed=$((elapsed + 10))
    echo "  Still waiting... ($elapsed s)"
done

if [ $elapsed -ge $MAX_WAIT ]; then
    echo "❌ Vault not reachable after ${MAX_WAIT}s. Exiting."
    exit 1
fi

# ==============================================================================
# 2. Check Vault status
# ==============================================================================
echo ""
echo "🔍 Checking Vault status..."
HEALTH=$(curl -s "$VAULT_ADDR/v1/sys/health" || echo '{}')
INITIALIZED=$(echo "$HEALTH" | jq -r '.initialized // false')
SEALED=$(echo "$HEALTH" | jq -r '.sealed // true')

echo "  Initialized: $INITIALIZED"
echo "  Sealed: $SEALED"

# ==============================================================================
# 3. Initialize if needed
# ==============================================================================
if [ "$INITIALIZED" = "false" ]; then
    echo ""
    echo "🔑 Initializing Vault (first-time setup)..."
    # With KMS auto-unseal: recovery_shares instead of secret_shares
    INIT_RESULT=$(curl -s -X POST "$VAULT_ADDR/v1/sys/init" \
        -H "Content-Type: application/json" \
        -d '{"recovery_shares": 5, "recovery_threshold": 3}')
    
    ROOT_TOKEN=$(echo "$INIT_RESULT" | jq -r '.root_token // empty')
    RECOVERY_KEYS=$(echo "$INIT_RESULT" | jq -r '.recovery_keys_b64 // [] | join(",")')
    
    if [ -z "$ROOT_TOKEN" ]; then
        echo "❌ Failed to initialize Vault. Response:"
        echo "$INIT_RESULT" | jq .
        exit 1
    fi
    
    echo "  ✅ Vault initialized!"
    echo "  Root token: ${ROOT_TOKEN:0:10}..."
    
    # Store keys in K8s Secret
    echo ""
    echo "💾 Storing init keys in K8s Secret '$SECRET_NAME'..."
    
    # Create/update the secret
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: $SECRET_NAME
  namespace: $NAMESPACE
  labels:
    app.kubernetes.io/name: vault
    app.kubernetes.io/component: init-keys
    software-factory.io/managed: "true"
  annotations:
    software-factory.io/init-date: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
type: Opaque
stringData:
  root-token: "$ROOT_TOKEN"
  recovery-keys: "$RECOVERY_KEYS"
EOF
    
    echo "  ✅ Keys stored in secret '$NAMESPACE/$SECRET_NAME'"
    
    # ==============================================================================
    # 4. Wait for auto-unseal (KMS handles this)
    # ==============================================================================
    echo ""
    echo "⏳ Waiting for auto-unseal (KMS)..."
    unseal_wait=0
    while [ $unseal_wait -lt 120 ]; do
        HEALTH=$(curl -s "$VAULT_ADDR/v1/sys/health" || echo '{}')
        SEALED=$(echo "$HEALTH" | jq -r '.sealed // true')
        if [ "$SEALED" = "false" ]; then
            echo "  ✅ Vault is unsealed!"
            break
        fi
        sleep 5
        unseal_wait=$((unseal_wait + 5))
    done
    
    if [ "$SEALED" = "true" ]; then
        echo "⚠️  Vault still sealed after 120s. KMS auto-unseal may not be configured."
        echo "  Manual unseal may be required."
    fi
    
    # ==============================================================================
    # 5. Enable KV v2 secret engine
    # ==============================================================================
    if [ "$SEALED" = "false" ]; then
        echo ""
        echo "🔧 Configuring Vault..."
        
        # Enable KV v2
        echo "  Enabling KV v2 at secret/..."
        curl -s -X POST "$VAULT_ADDR/v1/sys/mounts/secret" \
            -H "X-Vault-Token: $ROOT_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"type": "kv", "options": {"version": "2"}}' || echo "  (already exists)"
        
        # Create read-only policy for apps
        echo "  Creating app-read-only policy..."
        curl -s -X PUT "$VAULT_ADDR/v1/sys/policies/acl/app-read-only" \
            -H "X-Vault-Token: $ROOT_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{
                "policy": "path \"secret/data/*\" {\n  capabilities = [\"read\", \"list\"]\n}\npath \"secret/metadata/*\" {\n  capabilities = [\"list\"]\n}"
            }' || echo "  (policy error, non-fatal)"
        
        echo "  ✅ Vault configured!"
    fi
    
    echo ""
    echo "============================================================"
    echo "🎉 VAULT INITIALIZATION COMPLETE"
    echo "============================================================"
    echo ""
    echo "Root token stored in: kubectl -n $NAMESPACE get secret $SECRET_NAME -o jsonpath='{.data.root-token}' | base64 -d"
    echo ""
    echo "To use in terraform.tfvars (optional, for Vault provider):"
    echo "  vault_init_token = \"$ROOT_TOKEN\""
    echo ""
    
elif [ "$INITIALIZED" = "true" ] && [ "$SEALED" = "false" ]; then
    echo ""
    echo "✅ Vault is already initialized and unsealed. Nothing to do."
    
elif [ "$INITIALIZED" = "true" ] && [ "$SEALED" = "true" ]; then
    echo ""
    echo "⚠️  Vault is initialized but SEALED."
    echo "  AWS KMS auto-unseal should handle this automatically."
    echo "  If still sealed after 2-3 minutes, check:"
    echo "    - KMS key alias: software-factory-vault-unseal"
    echo "    - IAM role permissions for kms:Encrypt, kms:Decrypt"
    echo "    - Vault logs: kubectl -n vault logs -l app.kubernetes.io/name=vault"
fi

echo ""
echo "🏁 Vault auto-init script complete."

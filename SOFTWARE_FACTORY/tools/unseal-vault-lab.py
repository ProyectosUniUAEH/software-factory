#!/usr/bin/env python3
"""Unseal Vault on lab using vault-init-keys secret. Never prints secrets."""
import base64
import json
import subprocess
import sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    st = run([
        "sudo", "-n", "kubectl", "-n", "vault", "exec", "deploy/vault", "--",
        "vault", "status", "-format=json",
    ])
    # vault status exits 2 when sealed
    try:
        status = json.loads(st.stdout or "{}")
    except json.JSONDecodeError:
        print("FAIL: cannot parse vault status", file=sys.stderr)
        print((st.stderr or st.stdout or "")[:300], file=sys.stderr)
        return 1

    print(f"initialized={status.get('initialized')} sealed={status.get('sealed')}")
    if not status.get("initialized"):
        print("FAIL: vault not initialized")
        return 1
    if not status.get("sealed"):
        print("OK: already unsealed")
        return 0

    ks = run([
        "sudo", "-n", "kubectl", "-n", "vault", "get", "secret", "vault-init-keys",
        "-o", "jsonpath={.data.unseal-key}",
    ])
    if ks.returncode != 0 or not (ks.stdout or "").strip():
        print("FAIL: vault-init-keys/unseal-key missing")
        return 1
    unseal = base64.b64decode(ks.stdout.strip()).decode()
    ur = run([
        "sudo", "-n", "kubectl", "-n", "vault", "exec", "deploy/vault", "--",
        "vault", "operator", "unseal", unseal,
    ])
    if ur.returncode != 0:
        print("FAIL: unseal command failed")
        print((ur.stderr or ur.stdout or "")[:300], file=sys.stderr)
        return 1

    st2 = run([
        "sudo", "-n", "kubectl", "-n", "vault", "exec", "deploy/vault", "--",
        "vault", "status", "-format=json",
    ])
    try:
        status2 = json.loads(st2.stdout or "{}")
    except json.JSONDecodeError:
        status2 = {}
    print(f"after: sealed={status2.get('sealed')}")
    return 0 if not status2.get("sealed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

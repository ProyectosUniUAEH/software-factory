#!/usr/bin/env python3
"""¿Puede el cliente OAuth emitir authkeys con tag:k8s-operator?

El operador de Tailscale para Kubernetes arranca pidiendo una authkey con esa
etiqueta. Si la ACL del tailnet no la declara, o el cliente OAuth no la tiene
concedida, el operador entra en CrashLoopBackOff con un 400 y el resto de la
plataforma parece sano. Comprobarlo antes cuesta una llamada.

  python3 tools/check-tailscale-tag.py --env /etc/kaanbal/installer.env
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

TAG = "tag:k8s-operator"
TOKEN_URL = "https://api.tailscale.com/api/v2/oauth/token"
KEYS_URL = "https://api.tailscale.com/api/v2/tailnet/-/keys"


def load_env(path):
    values = {}
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip().replace("\r", "")
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip().upper()] = value.strip().strip("'\"")
    return values


def access_token(client_id, client_secret):
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()
    request = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode()).get("access_token", "")


def try_mint_key(token, tag=TAG):
    """Intenta crear una authkey efímera con la etiqueta. Devuelve (ok, detalle)."""
    payload = {
        "capabilities": {
            "devices": {"create": {
                "reusable": False, "ephemeral": True, "preauthorized": True,
                "tags": [tag],
            }}
        },
        "expirySeconds": 300,
        # Tailscale rechaza descripciones con signos de puntuación.
        "description": "kaanbal preflight",
    }
    request = urllib.request.Request(
        KEYS_URL, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode())
        return True, body.get("id", "")
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode()[:200]}"
    except Exception as exc:
        return False, str(exc)[:200]


def revoke(token, key_id):
    request = urllib.request.Request(
        f"{KEYS_URL}/{urllib.parse.quote(key_id)}",
        headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    try:
        urllib.request.urlopen(request, timeout=15).close()
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="/etc/kaanbal/installer.env")
    parser.add_argument("--tag", default=TAG)
    args = parser.parse_args()

    env = load_env(args.env)
    client_id = env.get("TAILSCALE_CLIENT_ID", "")
    client_secret = env.get("TAILSCALE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("No hay credenciales de Tailscale en el archivo.")
        return 2

    token = access_token(client_id, client_secret)
    if not token:
        print("El cliente OAuth no devolvió token.")
        return 2
    print("OAuth: token obtenido.")

    ok, detail = try_mint_key(token, args.tag)
    if ok:
        revoke(token, detail)
        print(f"OK: el cliente puede emitir authkeys con {args.tag}.")
        return 0

    print(f"FALLA: no puede emitir authkeys con {args.tag}.")
    print(f"  {detail}")
    print()
    print("Arréglalo en https://login.tailscale.com/admin/acls añadiendo la")
    print("etiqueta a la política y concediéndosela al cliente OAuth:")
    print()
    print('  "tagOwners": {')
    print(f'    "{args.tag}": ["autogroup:admin"]')
    print("  }")
    return 1


if __name__ == "__main__":
    sys.exit(main())

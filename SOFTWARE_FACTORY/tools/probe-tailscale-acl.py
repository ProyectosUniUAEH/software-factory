#!/usr/bin/env python3
"""Probar qué puede hacer el OAuth de Tailscale: ACL read/write + tags."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

ENV = "/etc/kaanbal/installer.env"


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


def http(method, url, token=None, data=None, auth=None, headers=None):
    hdrs = dict(headers or {})
    body = None
    if data is not None:
        if isinstance(data, dict):
            body = json.dumps(data).encode()
            hdrs.setdefault("Content-Type", "application/json")
        else:
            body = data if isinstance(data, bytes) else str(data).encode()
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    if auth:
        import base64
        cred = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            etag = resp.headers.get("ETag", "")
            try:
                return resp.status, json.loads(raw) if raw else {}, etag, raw
            except json.JSONDecodeError:
                return resp.status, {"raw": raw[:500]}, etag, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            body_j = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body_j = {"raw": raw[:500]}
        return exc.code, body_j, "", raw


def main():
    env = load_env(ENV)
    cid = env["TAILSCALE_CLIENT_ID"]
    csec = env["TAILSCALE_CLIENT_SECRET"]

    print("=== 1. OAuth token ===")
    status, resp, _, _ = http(
        "POST", "https://api.tailscale.com/api/v2/oauth/token",
        auth=(cid, csec),
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    print("status:", status, "keys:", list(resp.keys()) if isinstance(resp, dict) else resp)
    token = resp.get("access_token", "")
    if not token:
        print("FAIL token")
        return 1

    print("\n=== 2. GET ACL ===")
    status, acl, etag, raw = http(
        "GET", "https://api.tailscale.com/api/v2/tailnet/-/acl",
        token=token,
        headers={"Accept": "application/json"},
    )
    print("status:", status, "etag:", etag[:40] if etag else "")
    if status != 200:
        print("ACL READ FAIL:", acl)
        print("=> OAuth client needs policy/ACL scope")
        return 2

    tag_owners = acl.get("tagOwners") or acl.get("tagowners") or {}
    print("tagOwners keys:", sorted(tag_owners.keys()))
    print("has tag:k8s-operator:", "tag:k8s-operator" in tag_owners)
    print("has tag:k8s:", "tag:k8s" in tag_owners)
    print("acl keys:", sorted(acl.keys()))

    # Dry-run: what we would add (don't POST yet unless --apply)
    apply = "--apply" in sys.argv
    needed = {
        "tag:k8s-operator": ["autogroup:admin"],
        "tag:k8s": ["tag:k8s-operator"],
        "tag:database": ["tag:k8s-operator"],
        "tag:iot": ["tag:k8s-operator"],
    }
    missing = {k: v for k, v in needed.items() if k not in tag_owners}
    print("\n=== 3. Missing tags ===")
    print(missing or "(none)")

    if not missing:
        print("ACL already has required tags")
        return 0

    if not apply:
        print("\n(dry-run) pass --apply to POST ACL merge")
        return 0

    print("\n=== 4. POST ACL merge ===")
    new_owners = dict(tag_owners)
    new_owners.update(missing)
    new_acl = dict(acl)
    new_acl["tagOwners"] = new_owners
    # Prefer canonical key
    if "tagowners" in new_acl and "tagOwners" in new_acl:
        new_acl.pop("tagowners", None)

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if etag:
        headers["If-Match"] = etag
    status, resp2, _, raw2 = http(
        "POST", "https://api.tailscale.com/api/v2/tailnet/-/acl",
        token=token, data=new_acl, headers=headers,
    )
    print("POST status:", status)
    if status not in (200, 201):
        print("ACL WRITE FAIL:", resp2)
        print("raw:", raw2[:400])
        return 3
    print("ACL WRITE OK")
    owners = (resp2.get("tagOwners") or resp2.get("tagowners") or {})
    print("tagOwners now:", sorted(owners.keys()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

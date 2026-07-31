#!/usr/bin/env python3
"""Aplica tagOwners + grants member→tag:k8s en el tailnet (fix VPN access)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "installer"))

from server import ensure_tailscale_acl_tags, parse_env_text  # noqa: E402


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/etc/kaanbal/installer.env"
    with open(path, encoding="utf-8") as fh:
        cfg = parse_env_text(fh.read())
    cid = (cfg.get("tailscale_id") or "").strip()
    secret = (cfg.get("tailscale_secret") or "").strip()
    if not cid or not secret:
        raise SystemExit("missing TAILSCALE_CLIENT_ID/SECRET")

    def log(msg, level="info"):
        print(f"[{level}] {msg}", flush=True)

    ok, detail = ensure_tailscale_acl_tags(cid, secret, log_fn=log)
    print(f"RESULT ok={ok} detail={detail}", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

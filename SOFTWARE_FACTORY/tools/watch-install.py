#!/usr/bin/env python3
"""Sigue una instalación en curso desde fuera, leyendo la API del instalador.

Útil cuando el proceso corre en segundo plano: muestra los pasos y la bitácora
sin interferir con quien está conduciendo la instalación.

  python3 tools/watch-install.py [--once] [--tail N]
"""

import argparse
import json
import time
import urllib.request

TOKEN_FILE = "/run/kaanbal-installer/token"
MARKS = {"done": "✓", "error": "✗", "failed": "✗", "running": "·",
         "skipped": "–", "pending": " "}
ORDER = ["sistema", "k3s", "nodo", "argocd", "ia", "cloudflared",
         "repos", "imagenes", "gitops", "plataforma", "acceso"]


def state(token, port=3000):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/state",
        headers={"X-Kaanbal-Token": token})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


def render(snapshot, tail):
    print("fase:", snapshot.get("phase"))
    steps = snapshot.get("steps") or {}
    for step_id in ORDER:
        step = steps.get(step_id)
        if not step:
            continue
        mark = MARKS.get(step.get("status"), "?")
        detail = step.get("detail", "")
        print(f"  {mark} {step_id:<12} {detail}")

    entries = [e for e in (snapshot.get("log") or [])
               if e.get("level") not in ("cmd", "out")]
    print(f"\nbitácora (últimas {tail}):")
    for entry in entries[-tail:]:
        print(f"  {entry.get('level', ''):<5} {entry.get('message', '')}")

    handoff = snapshot.get("handoff") or {}
    if handoff:
        print("\nresultado:")
        for key in ("domain", "console_url", "api_url", "argocd_url",
                    "console_exposure", "console_reachable", "tunnel_live"):
            if key in handoff:
                print(f"  {key}: {handoff[key]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--tail", type=int, default=25)
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--token", default="")
    args = parser.parse_args()

    token = args.token
    if not token:
        with open(TOKEN_FILE, encoding="utf-8") as handle:
            token = handle.read().strip()

    while True:
        snapshot = state(token, args.port)
        render(snapshot, args.tail)
        if args.once or snapshot.get("phase") in ("done", "error"):
            return 0 if snapshot.get("phase") != "error" else 1
        print("-" * 60, flush=True)
        time.sleep(10)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash
set -euo pipefail
sudo -n kubectl -n prod exec deploy/kaanbal-api -- python <<'PY'
import urllib.request, json
d = json.load(urllib.request.urlopen("http://127.0.0.1:8000/openapi.json"))
paths = [p for p in d.get("paths", {}) if "environments" in p or "exposure" in p]
print("PATHS:")
for p in sorted(paths):
    methods = ",".join(d["paths"][p].keys())
    print(f"  {methods.upper():12} {p}")
PY
sudo -n kubectl -n prod get deploy kaanbal-console -o jsonpath='{.spec.template.spec.containers[0].image}'; echo

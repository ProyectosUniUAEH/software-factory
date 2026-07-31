#!/usr/bin/env python3
import json, subprocess, sys

for app in ("front1-dev", "front1-staging", "front1-prod"):
    out = subprocess.check_output(
        ["k3s", "kubectl", "-n", "argocd", "get", "application", app, "-o", "json"],
        text=True,
    )
    src = json.loads(out)["spec"]["source"]
    print(app, src.get("repoURL"), src.get("path"))

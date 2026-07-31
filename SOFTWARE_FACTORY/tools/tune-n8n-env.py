#!/usr/bin/env python3
import base64
import json
import subprocess
import time


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    if out:
        print(out)
    return out


extras = {
    "N8N_LISTEN_ADDRESS": "0.0.0.0",
    "N8N_PORT": "5678",
    "N8N_RUNNERS_ENABLED": "false",
    "NODE_OPTIONS": "--max-old-space-size=1024",
    "N8N_DIAGNOSTICS_ENABLED": "false",
}

open("/tmp/n8n-mem-patch.yaml", "w").write(
    """
spec:
  template:
    spec:
      containers:
      - name: n8n
        resources:
          requests:
            memory: 512Mi
            cpu: 100m
          limits:
            memory: "2Gi"
            cpu: "1"
"""
)

for ns in ("prod", "dev", "staging"):
    print(f"===== {ns} =====")
    secs = sh(f"k3s kubectl -n {ns} get secrets -o name")
    n8n = [l for l in secs.splitlines() if "lab-n8n-secrets" in l][0].split("/", 1)[-1]
    data = json.loads(
        subprocess.check_output(
            ["k3s", "kubectl", "-n", ns, "get", "secret", n8n, "-o", "json"], text=True
        )
    )["data"]
    decoded = {k: base64.b64decode(v).decode() for k, v in data.items()}
    decoded.update(extras)
    patch = {"data": {k: base64.b64encode(v.encode()).decode() for k, v in decoded.items()}}
    path = f"/tmp/n8n-env-{ns}.json"
    open(path, "w").write(json.dumps(patch))
    sh(f"k3s kubectl -n {ns} patch secret {n8n} --type merge --patch-file {path}")
    sh(f"k3s kubectl -n {ns} patch sts lab-n8n --patch-file /tmp/n8n-mem-patch.yaml")
    sh(f"k3s kubectl -n {ns} delete pod lab-n8n-0 --force --grace-period=0")

print("waiting startup...")
time.sleep(50)
sh("k3s kubectl get pods -A | grep n8n")
sh("k3s kubectl -n prod logs lab-n8n-0 --tail=20")
sh("k3s kubectl -n prod exec lab-n8n-0 -- wget -qO- --timeout=5 http://127.0.0.1:5678/ 2>&1 | head -5")
sh("curl -sS -o /dev/null -w 'public=%{http_code}\\n' --max-time 20 https://lab-n8n.softwarefactory.site/")
print("DONE")

#!/usr/bin/env python3
import subprocess
import time


def sh(cmd):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    print(((r.stdout or "") + (r.stderr or "")).strip())


print("=== svc/ingress ===")
sh("k3s kubectl -n prod get svc lab-n8n -o yaml")
sh("k3s kubectl -n prod get ingress lab-n8n -o yaml")

print("\n=== bump memory via file ===")
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
            memory: 1536Mi
            cpu: "1"
"""
)
for ns in ("prod", "dev", "staging"):
    sh(f"k3s kubectl -n {ns} patch sts lab-n8n --patch-file /tmp/n8n-mem-patch.yaml")

time.sleep(5)
# port-forward test
sh("k3s kubectl -n prod get endpoints lab-n8n -o yaml")
sh(
    "k3s kubectl -n prod run curl-n8n --rm -i --restart=Never --image=curlimages/curl:8.5.0 -- "
    "curl -sS -o /dev/null -w '%{http_code}' --max-time 10 http://lab-n8n.prod.svc.cluster.local:5678/"
)
sh("curl -sS -o /dev/null -w 'public=%{http_code}\\n' --max-time 15 https://lab-n8n.softwarefactory.site/")
print("DONE")

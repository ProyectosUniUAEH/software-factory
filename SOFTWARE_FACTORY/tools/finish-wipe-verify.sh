#!/usr/bin/env bash
set -euo pipefail
[[ "${EUID}" -eq 0 ]] || exec sudo -n bash "$0" "$@"

systemctl disable --now kaanbal-installer 2>/dev/null || true
pkill -f 'installer/server.py' 2>/dev/null || true
pkill -f k3s 2>/dev/null || true

rm -rf /var/lib/kaanbal-installer /run/kaanbal-installer /var/lib/kaanbal \
  /tmp/kaanbal-* /etc/rancher /var/lib/rancher /var/lib/kubelet \
  /etc/cni /opt/cni /var/lib/cni 2>/dev/null || true
rm -f /usr/local/bin/k3s /usr/local/bin/kubectl /usr/local/bin/crictl \
  /usr/local/bin/k3s-uninstall.sh /usr/local/bin/k3s-killall.sh 2>/dev/null || true
rm -f /etc/systemd/system/k3s*.service /etc/systemd/system/kaanbal*.service 2>/dev/null || true

if [[ -f /tmp/kaanbal-installer.env.wipebak ]]; then
  mkdir -p /etc/kaanbal
  cp -a /tmp/kaanbal-installer.env.wipebak /etc/kaanbal/installer.env
  chmod 600 /etc/kaanbal/installer.env
fi

# also ensure env from reinstall file if backup missing
if [[ ! -f /etc/kaanbal/installer.env && -f /home/andres/kaanbal-reinstall.env ]]; then
  mkdir -p /etc/kaanbal
  tr -d '\r' </home/andres/kaanbal-reinstall.env >/etc/kaanbal/installer.env
  chmod 600 /etc/kaanbal/installer.env
fi

for h in /home/andres /root; do
  rm -rf "$h/.kube" 2>/dev/null || true
done

systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

echo "=== VERIFY ==="
if command -v k3s >/dev/null 2>&1; then echo "k3s_PRESENT"; else echo "k3s_ABSENT"; fi
systemctl is-active k3s 2>&1 || true
systemctl is-active kaanbal-installer 2>&1 || true
ls -la /etc/kaanbal/ 2>&1 || true
if [[ -f /etc/kaanbal/installer.env ]]; then echo "CREDENTIALS_OK"; else echo "CREDENTIALS_MISSING"; fi
if [[ -d /var/lib/rancher ]]; then echo "rancher_PRESENT"; else echo "rancher_ABSENT"; fi
if [[ -d /var/lib/kaanbal ]]; then echo "kaanbal_lib_PRESENT"; else echo "kaanbal_lib_ABSENT"; fi
ss -lntp 2>/dev/null | grep -E ':6443|:3000|:8080' || echo "ports_clean"
echo "WIPE_UBUNTU_DONE"

#!/usr/bin/env bash
# PoC Kaanbal Appliance: pantalla full-screen al boot + un botón para consola.
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIOSK_USER="${SUDO_USER:-andres}"
KIOSK_HOME="$(getent passwd "$KIOSK_USER" | cut -d: -f6)"
HTTP_PORT=8888
KIOSK_DIR="${KIOSK_HOME}/kaanbal-kiosk-preview"
KIOSK_UNIT=kaanbal-kiosk-preview.service
MODE_UNIT=kaanbal-mode-switch.service

log() { printf '\033[1;36m[kiosk]\033[0m %s\n' "$*"; }

[[ "${EUID}" -eq 0 ]] || { echo "Ejecuta con sudo"; exit 1; }

log "Instalando stack gráfico mínimo (sin escritorio completo)..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  xserver-xorg xinit openbox \
  epiphany-browser dbus-x11 \
  wmctrl xdotool \
  fonts-dejavu-core fonts-liberation \
  python3 curl

mkdir -p /etc/kaanbal/openbox /usr/local/bin

log "Copiando assets del kiosk..."
install -d -m 755 "$KIOSK_DIR"
install -m 644 "${SOURCE_DIR}/index.html" "$KIOSK_DIR/index.html"
install -m 755 "${SOURCE_DIR}/kiosk-start.sh" /usr/local/bin/kaanbal-kiosk-start.sh
install -m 644 "${SOURCE_DIR}/openbox-kiosk.xml" /etc/kaanbal/openbox/kiosk.xml
install -m 644 "${SOURCE_DIR}/console-return.txt" /etc/kaanbal/console-return.txt
install -m 755 "${SOURCE_DIR}/bin/kaanbal-ui" /usr/local/bin/kaanbal-ui
install -m 755 "${SOURCE_DIR}/bin/kaanbal-console" /usr/local/bin/kaanbal-console
install -m 755 "${SOURCE_DIR}/mode-switch.py" /usr/local/bin/kaanbal-mode-switch.py
sed -i 's/\r$//' /usr/local/bin/kaanbal-kiosk-start.sh \
  /usr/local/bin/kaanbal-ui /usr/local/bin/kaanbal-console \
  /usr/local/bin/kaanbal-mode-switch.py

if ! command -v google-chrome-stable >/dev/null 2>&1 && \
   ! command -v chromium-browser >/dev/null 2>&1 && \
   ! command -v chromium >/dev/null 2>&1; then
  log "Intentando Google Chrome (.deb) para kiosk puro..."
  tmpdeb="$(mktemp /tmp/google-chrome.XXXX.deb)"
  if curl -fsSL -o "$tmpdeb" \
    "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"; then
    dpkg -i "$tmpdeb" 2>/dev/null || apt-get install -fy -qq
  fi
  rm -f "$tmpdeb"
fi

log "Permisos para alternar modo sin contraseña (usuario ${KIOSK_USER})..."
cat >/etc/sudoers.d/kaanbal-kiosk <<EOF
${KIOSK_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/kaanbal-ui
${KIOSK_USER} ALL=(ALL) NOPASSWD: /usr/local/bin/kaanbal-console
EOF
chmod 440 /etc/sudoers.d/kaanbal-kiosk
visudo -cf /etc/sudoers.d/kaanbal-kiosk

loginctl enable-linger "$KIOSK_USER" 2>/dev/null || true

cat >"/etc/systemd/system/${MODE_UNIT}" <<EOF
[Unit]
Description=Kaanbal API local modo kiosk/consola
After=network.target

[Service]
User=root
ExecStart=/usr/bin/python3 /usr/local/bin/kaanbal-mode-switch.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat >"/etc/systemd/system/${KIOSK_UNIT}" <<EOF
[Unit]
Description=Kaanbal interfaz full-screen (tty1)
After=network-online.target ${MODE_UNIT} kaanbal-kiosk-http.service
Wants=${MODE_UNIT} kaanbal-kiosk-http.service
Conflicts=getty@tty1.service

[Service]
User=root
TTYPath=/dev/tty1
StandardInput=tty
StandardOutput=journal
StandardError=journal
Environment=DISPLAY=:0
Environment=HOME=/root
Environment=XDG_RUNTIME_DIR=/run/user/0
Environment=KAANBAL_KIOSK_URL=http://127.0.0.1:${HTTP_PORT}/
ExecStartPre=/bin/chvt 1
ExecStartPre=/bin/sh -c 'until curl -sf http://127.0.0.1:${HTTP_PORT}/ >/dev/null; do sleep 1; done'
ExecStart=/usr/bin/xinit /usr/local/bin/kaanbal-kiosk-start.sh -- /usr/bin/X :0 vt1 -nolisten tcp
Restart=always
RestartSec=4

[Install]
WantedBy=multi-user.target
EOF

cat >"/etc/systemd/system/kaanbal-kiosk-http.service" <<EOF
[Unit]
Description=Kaanbal UI estática local
After=network.target

[Service]
User=${KIOSK_USER}
WorkingDirectory=${KIOSK_DIR}
ExecStart=/usr/bin/python3 -m http.server ${HTTP_PORT} --bind 127.0.0.1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /etc/update-motd.d
cat >/etc/update-motd.d/99-kaanbal <<'MOTD'
#!/bin/sh
cat /etc/kaanbal/console-return.txt 2>/dev/null || true
MOTD
chmod 755 /etc/update-motd.d/99-kaanbal

systemctl daemon-reload
systemctl enable kaanbal-kiosk-http.service "$MODE_UNIT" "$KIOSK_UNIT"
systemctl restart kaanbal-kiosk-http.service "$MODE_UNIT"
systemctl restart "$KIOSK_UNIT"

log ""
log "PoC listo."
log "  Pantalla física (tty1): interfaz Kaanbal full-screen"
log "  Volver desde consola:   sudo kaanbal-ui"
log "  Ir a consola (SSH):     sudo kaanbal-console"
log "  Boton en UI:            Consola (esquina inferior derecha)"

#!/usr/bin/env bash
set -euo pipefail
URL="${KAANBAL_KIOSK_URL:-http://127.0.0.1:8888/}"
OB_CONFIG="${KAANBAL_OB_CONFIG:-/etc/kaanbal/openbox/kiosk.xml}"

CHROMIUM_FLAGS=(
  --kiosk
  --app="$URL"
  --no-first-run
  --disable-infobars
  --disable-session-crashed-bubble
  --disable-translate
  --noerrdialogs
  --overscroll-history-navigation=0
  --check-for-update-interval=31536000
)

# Google Chrome no permite ejecutarse como root sin esto.
if [[ "$(id -u)" -eq 0 ]]; then
  CHROMIUM_FLAGS+=(--no-sandbox --disable-dev-shm-usage)
fi

browser_cmd() {
  if command -v google-chrome-stable >/dev/null 2>&1; then
    echo "google-chrome-stable ${CHROMIUM_FLAGS[*]}"
  elif command -v chromium-browser >/dev/null 2>&1; then
    echo "chromium-browser ${CHROMIUM_FLAGS[*]}"
  elif command -v chromium >/dev/null 2>&1; then
    echo "chromium ${CHROMIUM_FLAGS[*]}"
  else
    return 1
  fi
}

if cmd="$(browser_cmd 2>/dev/null)"; then
  # Chromium --kiosk: una sola superficie web, sin chrome del navegador.
  exec bash -c "$cmd"
fi

# Respaldo: Openbox sin decoraciones + navegador maximizado.
openbox --config-file "$OB_CONFIG" &
sleep 2

if command -v epiphany-browser >/dev/null 2>&1 && command -v dbus-launch >/dev/null 2>&1; then
  dbus-launch --exit-with-session epiphany-browser --application-mode "$URL" &
elif command -v surf >/dev/null 2>&1; then
  surf -F "$URL" &
else
  echo "No hay navegador kiosk disponible" >&2
  exit 1
fi

if command -v wmctrl >/dev/null 2>&1 && command -v xdotool >/dev/null 2>&1; then
  wid=""
  for _ in $(seq 1 20); do
    wid="$(xdotool search --class "Epiphany" 2>/dev/null | head -1 || true)"
    [[ -n "$wid" ]] && break
    wid="$(xdotool search --class "Surf" 2>/dev/null | head -1 || true)"
    [[ -n "$wid" ]] && break
    sleep 1
  done
  if [[ -n "$wid" ]]; then
    wmctrl -i -r "$wid" -b add,fullscreen,above,sticky
    xdotool windowactivate "$wid"
  fi
fi

wait

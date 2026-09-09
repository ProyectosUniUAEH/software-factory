#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE="kaanbal-installer"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_HOME="/var/lib/kaanbal"
STATE_DIR="/var/lib/kaanbal-installer"
CONFIG_DIR="/etc/kaanbal"
RUNTIME_ENV="${CONFIG_DIR}/installer-runtime.env"
CREDS_ENV="${CONFIG_DIR}/installer.env"
RESET_MODE=""
RESET_REMOTE=false
PRESERVE="credentials"
ENV_SOURCE=""
UNATTENDED=false
CHECK_ONLY=false
ORIGINAL_ARGS=("$@")

log() { printf '\033[1;36m[kaanbal]\033[0m %s\n' "$*"; }
ok() { printf '\033[1;32m  OK\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  AVISO\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m  ERROR\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Uso:
  sudo bash ./install.sh                                   # asistente web
  sudo bash ./install.sh --env /ruta/a/.env                # asistente precargado
  sudo bash ./install.sh --unattended --env /ruta/a/.env   # sin navegador
  sudo bash ./install.sh --check --env /ruta/a/.env        # solo validar
  sudo bash ./install.sh --reset-local --preserve-credentials
  sudo bash ./install.sh --reset-local --wipe-credentials
  sudo bash ./install.sh --reset-local --reset-remote      # modo desarrollo

  Actualizar componentes YA instalados (sin wipe):
    sudo bash tools/rebuild-platform.sh api|console|agent|templates|core
    sudo bash tools/rebuild-platform.sh wipe-full   # solo from-zero

  --unattended     Instala de principio a fin leyendo el .env, sin abrir el
                   asistente. Valida todas las credenciales ANTES de tocar la
                   máquina y verifica las URLs al terminar.
  --check          Solo valida el .env contra cada proveedor y sale. No instala
                   ni borra nada.
  --reset-local    Elimina k3s y los servicios Kaanbal de esta máquina.
  --reset-remote   Además borra los repos del sistema en GitHub
                   (infra-gitops, kaanbal-api, kaanbal-console,
                   kaanbal-templates) y sus imágenes en Docker Hub, para
                   instalar realmente desde cero. Allowlist estricta por
                   nombre exacto: tus apps y sus repos NO se tocan.

Copia installer/config.example fuera del checkout para el modo desatendido.
Sin --reset-remote no se elimina nada fuera de esta máquina.
EOF
}

while (($#)); do
  case "$1" in
    --reset-local) RESET_MODE="local" ;;
    --reset-remote) RESET_REMOTE=true ;;
    --unattended) UNATTENDED=true ;;
    --check) CHECK_ONLY=true ;;
    --preserve-credentials) PRESERVE="credentials" ;;
    --wipe-credentials) PRESERVE="none" ;;
    --env)
      shift
      [[ $# -gt 0 ]] || die "--env requiere una ruta"
      ENV_SOURCE="$1"
      ;;
    -h|--help) usage; exit 0 ;;
    *) die "Opción desconocida: $1" ;;
  esac
  shift
done

if { $UNATTENDED || $CHECK_ONLY; } && [[ -z "$ENV_SOURCE" ]]; then
  die "--unattended y --check necesitan --env con tu archivo de configuración."
fi

if [[ "${EUID}" -ne 0 ]]; then
  command -v sudo >/dev/null || die "Ejecuta como root o instala sudo."
  exec sudo bash "$0" "${ORIGINAL_ARGS[@]}"
fi

[[ "$(uname -s)" == "Linux" ]] || die "Kaanbal requiere Linux."
command -v systemctl >/dev/null || die "systemd es obligatorio."
SYSTEMD_STATE="$(systemctl is-system-running 2>/dev/null || true)"
[[ "$SYSTEMD_STATE" == "running" || "$SYSTEMD_STATE" == "degraded" ]] \
  || die "systemd no está activo (estado: ${SYSTEMD_STATE:-desconocido})."

for cmd in python3 curl git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log "Instalando dependencias base..."
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 curl git
    break
  fi
done

# Solo detenemos nuestra unidad; nunca procesos ajenos por su puerto.
if ! $CHECK_ONLY; then
if systemctl cat "$SERVICE" >/dev/null 2>&1; then
  [[ "$(systemctl show "$SERVICE" --property=Description --value)" == "Kaanbal temporary privileged installer" ]] \
    || die "Existe una unidad ${SERVICE} ajena; no se modifica."
  systemctl stop "$SERVICE"
fi
python3 - <<'PYPORT'
import socket
for port in (3000, 4600, 8080):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Puerto {port} ocupado. Libera el servicio responsable antes de reintentar; no se detuvo ningún proceso ajeno.")
PYPORT
fi

# Las credenciales se importan ANTES de cualquier reset: el reset remoto las
# necesita para autenticarse, y --wipe-credentials las borra al final.
install -d -m 700 "$CONFIG_DIR"
touch "$CREDS_ENV"
chmod 600 "$CREDS_ENV"
if [[ -n "$ENV_SOURCE" ]]; then
  [[ -f "$ENV_SOURCE" ]] || die "No existe el archivo: $ENV_SOURCE"
  # Un .env editado en Windows llega con CRLF y cada valor arrastra un \r
  # invisible: el token de Docker Hub deja de autenticar y las URLs se rompen
  # con errores que no mencionan el retorno de carro por ningún lado.
  # Si ENV_SOURCE == CREDS_ENV, `> "$CREDS_ENV"` trunca el archivo antes de
  # leerlo y deja credenciales vacías (falla silenciosa típica en reinstalación).
  if [[ "$(realpath -m "$ENV_SOURCE" 2>/dev/null || readlink -f "$ENV_SOURCE" 2>/dev/null || echo "$ENV_SOURCE")" == \
        "$(realpath -m "$CREDS_ENV" 2>/dev/null || readlink -f "$CREDS_ENV" 2>/dev/null || echo "$CREDS_ENV")" ]]; then
    tmp="$(mktemp)"
    tr -d '\r' <"$ENV_SOURCE" >"$tmp"
    cat "$tmp" >"$CREDS_ENV"
    rm -f "$tmp"
  else
    [[ ! -s "$CREDS_ENV" ]] || die "Ya existen credenciales en ${CREDS_ENV}. Inicia sin --env para conservarlas; no se sobrescriben."
    tr -d '\r' <"$ENV_SOURCE" >"$CREDS_ENV"
  fi
  chmod 600 "$CREDS_ENV"
  ok "Credenciales importadas desde ${ENV_SOURCE}"
fi

# Validación previa contra cada proveedor. En desatendido es una barrera: si una
# credencial no sirve, no se borra ni se instala nada. Con el asistente es solo
# informativa, porque lo que falte se puede completar en pantalla.
if [[ -n "$ENV_SOURCE" ]]; then
  check_args=(--env "$CREDS_ENV" --check-only)
  $RESET_REMOTE && check_args+=(--expect-reset)
  if $UNATTENDED || $CHECK_ONLY; then
    python3 "${SOURCE_DIR}/installer/unattended.py" "${check_args[@]}" \
      || die "La configuración no está lista. No se tocó nada."
    if $CHECK_ONLY; then
      ok "Configuración válida: la instalación puede proceder."
      exit 0
    fi
  else
    python3 "${SOURCE_DIR}/installer/unattended.py" "${check_args[@]}" \
      || warn "El preflight encontró faltantes; podrás corregirlos en el asistente."
  fi
fi

if $RESET_REMOTE; then
  log "Reset remoto: borrando repos e imágenes del sistema Kaanbal..."
  python3 "${SOURCE_DIR}/tools/reset-remote.py" --env "$CREDS_ENV" --yes \
    || die "El reset remoto falló; corrige y reintenta antes de instalar."
fi

if [[ "$RESET_MODE" == "local" ]]; then
  args=(--yes)
  [[ "$PRESERVE" == "credentials" ]] && args+=(--preserve-credentials) || args+=(--wipe-credentials)
  bash "${SOURCE_DIR}/tools/reset-local.sh" "${args[@]}"
fi

MEM_GB="$(awk '/MemTotal/ {printf "%.0f", $2/1024/1024}' /proc/meminfo)"
CPUS="$(nproc)"
DISK_GB="$(df -BG / | awk 'NR==2 {gsub("G","",$4); print $4}')"
[[ "$MEM_GB" -ge 4 ]] || die "RAM insuficiente: ${MEM_GB}GB; mínimo 4GB."
[[ "$CPUS" -ge 2 ]] || die "CPU insuficiente: ${CPUS}; mínimo 2."
[[ "$DISK_GB" -ge 15 ]] || die "Disco insuficiente: ${DISK_GB}GB libres; mínimo 15GB."

# El reset local pudo borrar estos directorios; se recrean tras él.
install -d -m 700 "$CONFIG_DIR" "$STATE_HOME" "$STATE_DIR" /run/kaanbal-installer
touch "$CREDS_ENV"
chmod 600 "$CREDS_ENV"

# Migrar la configuración del agente creada por una ejecución manual anterior.
CALLER="${SUDO_USER:-}"
if [[ -n "$CALLER" && "$CALLER" != "root" ]]; then
  CALLER_HOME="$(getent passwd "$CALLER" | cut -d: -f6)"
  if [[ -d "${CALLER_HOME}/.acuaponsito" && ! -d "${STATE_HOME}/.acuaponsito" ]]; then
    cp -a "${CALLER_HOME}/.acuaponsito" "${STATE_HOME}/.acuaponsito"
  fi
fi
chmod 700 "$STATE_HOME"

TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
TOKEN_HASH="$(printf '%s' "$TOKEN" | sha256sum | cut -c1-12)"
cat >"$RUNTIME_ENV" <<EOF
KAANBAL_INSTALLER_TOKEN=${TOKEN}
KAANBAL_INSTALLER_PORT=3000
KAANBAL_INSTALLER_HOST=127.0.0.1
ACUA_HOST=127.0.0.1
KAANBAL_INSTALLER_STATE_DIR=${STATE_DIR}
KAANBAL_CREDENTIALS_FILE=${CREDS_ENV}
KAANBAL_INSTALLER_PRIVILEGED=1
HOME=${STATE_HOME}
EOF
chmod 600 "$RUNTIME_ENV"
printf '%s' "$TOKEN" > /run/kaanbal-installer/token
chmod 600 /run/kaanbal-installer/token

cat >"/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=Kaanbal temporary privileged installer
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${SOURCE_DIR}
EnvironmentFile=${RUNTIME_ENV}
ExecStart=/usr/bin/python3 ${SOURCE_DIR}/installer/server.py
Restart=on-failure
RestartSec=2
UMask=0077

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "$SERVICE"
ready=false
for attempt in {1..30}; do
  if curl --fail --silent --max-time 2 http://127.0.0.1:3000/ >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
$ready || die "El instalador no respondió. Consulta sudo journalctl -u ${SERVICE} -n 50; no compartas tokens."

if $UNATTENDED; then
  # El servicio ya está arriba; ahora se conduce la instalación por su API, que
  # es exactamente lo que hace el asistente cuando pulsas "Instalar".
  exec python3 "${SOURCE_DIR}/installer/unattended.py" \
    --env "$CREDS_ENV" --token "$TOKEN"
fi

ok "Bootstrap preparado: ${MEM_GB}GB RAM, ${CPUS} CPU, ${DISK_GB}GB libres"
ok "Token temporal fingerprint: ${TOKEN_HASH}"
printf '\nEn otra terminal de tu PC, conserva abierto este túnel (sustituye el alias):\n\n'
printf '  ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:3000:127.0.0.1:3000 -L 127.0.0.1:4600:127.0.0.1:4600 -L 127.0.0.1:8080:127.0.0.1:8080 pam-lab\n'
printf '\nAbre en el navegador de tu PC:\n\n  http://localhost:3000/?token=%s\n\n' "$TOKEN"
printf 'El token se revoca y este servicio se deshabilita al confirmar el acceso final.\n'

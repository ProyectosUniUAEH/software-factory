#!/usr/bin/env bash
# Public entry point. Download this file first; never execute a partial curl pipe.
set -Eeuo pipefail
REPO="https://github.com/ProyectosUniUAEH/software-factory.git"
REVISION="main"
DESTINATION="${HOME}/kaanbal-source"
die() { printf '[kaanbal] ERROR: %s\n' "$*" >&2; exit 1; }
while (($#)); do
  case "$1" in
    --ref) shift; (($#)) || die '--ref necesita una revisión'; REVISION="$1" ;;
    --dir) shift; (($#)) || die '--dir necesita una ruta'; DESTINATION="$1" ;;
    -h|--help)
      printf 'Uso: bash install.sh [--ref commit|tag|branch] [--dir directorio-nuevo]\n'
      printf 'Reanudar: sudo bash <directorio>/SOFTWARE_FACTORY/install.sh\n'
      exit 0 ;;
    *) die "Opción desconocida: $1" ;;
  esac
  shift
done
[[ "$(uname -s)" == Linux ]] || die 'Ejecuta este comando dentro del servidor Ubuntu por SSH.'
[[ "$REVISION" =~ ^[a-zA-Z0-9][a-zA-Z0-9._/-]*$ ]] || die 'Revisión Git inválida.'
[[ ! -e "$DESTINATION" && ! -L "$DESTINATION" ]] || die "Ya existe $DESTINATION. No se sobrescribe. Reanuda su instalador o elige --dir con una ruta nueva."
command -v systemctl >/dev/null || die 'Se requiere Ubuntu Server con systemd.'
if ((EUID != 0)); then
  command -v sudo >/dev/null || die 'Se requiere sudo.'
  printf '[kaanbal] Introduce personalmente la contraseña sudo si se solicita.\n'
  sudo -v
fi
as_root() { if ((EUID == 0)); then "$@"; else sudo "$@"; fi; }
if ! command -v git >/dev/null || ! command -v python3 >/dev/null || ! command -v curl >/dev/null; then
  as_root apt-get update
  as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 curl ca-certificates
fi
# mkdir fails instead of replacing an existing checkout, including on a race.
mkdir -p "$(dirname "$DESTINATION")"
mkdir -m 700 "$DESTINATION"
git -C "$DESTINATION" init --quiet
git -C "$DESTINATION" remote add origin "$REPO"
GIT_TERMINAL_PROMPT=0 git -C "$DESTINATION" fetch --depth 1 origin "$REVISION" \
  || die 'No se pudo descargar la revisión pública. El directorio parcial se conserva para diagnóstico; no se ejecutó el instalador.'
git -C "$DESTINATION" checkout --quiet --detach FETCH_HEAD
printf '[kaanbal] Revisión descargada: '
git -C "$DESTINATION" rev-parse HEAD
[[ -f "$DESTINATION/SOFTWARE_FACTORY/install.sh" ]] || die 'Esta revisión no contiene el instalador.'
as_root bash "$DESTINATION/SOFTWARE_FACTORY/install.sh"

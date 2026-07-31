#!/usr/bin/env bash
set -euo pipefail
SRC=/home/andres/kaanbal-reinstall.env
DST=/etc/kaanbal/installer.env
[[ -f "$SRC" ]] || { echo "MISSING_SRC"; exit 1; }
sudo -n mkdir -p /etc/kaanbal
TMP=$(mktemp)
tr -d '\r' <"$SRC" >"$TMP"
sudo -n cp "$TMP" "$DST"
sudo -n chmod 600 "$DST"
rm -f "$TMP"
echo "SRC_BYTES=$(wc -c <"$SRC")"
echo "DST_BYTES=$(sudo -n wc -c <"$DST")"
echo "DST_KEYS=$(sudo -n cut -d= -f1 "$DST" | tr '\n' ' ')"

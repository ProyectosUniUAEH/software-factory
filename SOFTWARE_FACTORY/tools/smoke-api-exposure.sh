#!/usr/bin/env bash
set -euo pipefail
sudo -n kubectl -n prod exec deploy/kaanbal-api -- python -c \
  'from app.services.exposure.connection_surfaces import build_env_surfaces; print("SURFACES_IMPORT_OK")'
sudo -n kubectl -n prod exec deploy/kaanbal-api -- python -c \
  'from app.services.exposure.switch_service import ExposureSwitchService; print("SWITCH_IMPORT_OK")'
# OpenAPI has exposure patch?
sudo -n kubectl -n prod exec deploy/kaanbal-api -- python -c \
  'import urllib.request,json; d=json.load(urllib.request.urlopen("http://127.0.0.1:8000/openapi.json")); paths=[p for p in d.get("paths",{}) if "exposure" in p]; print("PATHS", paths)'

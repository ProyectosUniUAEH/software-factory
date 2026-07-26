#!/bin/bash
ARGOCD_PASSWORD='vwsT6Gz0OBlhP0kp'
HASHED_PASSWORD=$(htpasswd -bnBC 10 "" "$ARGOCD_PASSWORD" | tr -d ':\n' | sed 's/$2y/$2a/')
MTIME=$(date +%FT%T%Z)

kubectl -n argocd patch secret argocd-secret -p "{\"stringData\": {\"admin.password\": \"$HASHED_PASSWORD\", \"admin.passwordMtime\": \"$MTIME\"}}"

echo "Password configured!"

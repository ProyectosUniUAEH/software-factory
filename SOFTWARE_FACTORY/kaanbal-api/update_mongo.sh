#!/bin/bash
sudo kubectl exec -n prod datastore-8697cdd48d-79nck -- mongosh "mongodb://admin:CHANGEME_DB_PASSWORD@localhost:27017/forge?authSource=admin" --quiet --eval '
db.system_config.updateOne(
  {_id: "main"},
  {$set: {
    cloudflare_tunnel_id: "e1937c82-4b9a-4c21-a414-ffe3569356cd",
    cloudflare_zone_id: "ace2218f9c27d80923ce85a763f5bae6"
  }}
)
'

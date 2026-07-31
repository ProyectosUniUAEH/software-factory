---
name: preflight-lab
description: Inventario de solo lectura del servidor lab 192.168.1.198 vía ssh andres-lan. Usar antes de instalar o modificar el host.
---

# Preflight lab

## Precondiciones

- Acceso: `ssh andres-lan` desde máquina del usuario (LAN/Tailscale).
- Solo comandos de lectura salvo aprobación explícita.

## Comandos permitidos

```bash
ssh andres-lan "hostnamectl; uname -a; lsb_release -a 2>/dev/null; lscpu; free -h; lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS; df -hT; ip -brief address; systemctl --failed 2>/dev/null; ss -tulpn 2>/dev/null | head -30"
```

## Salida

Rellenar plantilla en `docs/contracts/LAB_SERVER.md` y adjuntar a ticket SF-005.

## Prohibido en preflight

Formateos, instalar K3s, cambiar firewall/SSH, borrar paquetes.

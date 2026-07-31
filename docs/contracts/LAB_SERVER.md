# Servidor lab — contrato operativo

## Acceso

```bash
ssh andres-lan
# equivalente: ssh andres@192.168.1.198
```

Solo accesible desde LAN o Tailscale. Agentes cloud **no** tienen acceso directo.

## Reglas para agentes

| Permitido (Fase 0-1) | Requiere aprobación |
|----------------------|---------------------|
| `hostnamectl`, `uname -a`, `free -h`, `lsblk`, `df -h` | Instalar paquetes |
| `ip -brief address`, `systemctl --failed` | Cambios firewall/SSH |
| `kubectl get` (si k3s existe) | `kubectl delete`, formateos |
| Scripts en `AGENTS/labs/` de solo lectura | Instalar K3s |

## Comandos encapsulados (futuro)

```bash
make lab-preflight   # inventario sin modificar
make lab-status      # estado plataforma
make lab-verify      # health checks
```

## Inventario (plantilla)

```yaml
host:
  name: kaanbal-lab
  address: 192.168.1.198
  os: ubuntu
  cpu: null
  memory: null
  storage: null
  network: ethernet
  notes: ""
```

Rellenar en ticket SF-005 tras preflight.

## Estrategia de prueba

1. **LXD/VM** — reinstalar en segundos (desarrollo diario)
2. **Metal** — corrida de aceptación cronometrada (evidencia tesis)

## UI en arranque (plan)

- Instalador Kaanbal: systemd → `http://<ip>:3000/?token=...`
- Cockpit (admin host): puerto 9090 — red, disco, usuarios

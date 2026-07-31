# Kaanbal — Visión (resumen)

> Plataforma local-first e híbrida para desplegar aplicaciones de dominio, integrar agentes gobernados, automatizar procesos y operar modelos de IA sobre infraestructura local con computo externo bajo demanda.

## Propuesta de valor

Convertir el conocimiento de una especialista en una aplicación operativa y, después, convertir sus datos en procesos reproducibles y modelos utilizables.

## Relación Kaanbal ↔ FagoLab

- **Kaanbal** = plataforma (infra, GitOps, identidad, agentes, artefactos).
- **FagoLab** = primera aplicación vertical (lógica científica de fagoterapia).

## Dos carriles

| Carril | Dónde vive | Criterio de "terminado" |
|--------|------------|------------------------|
| Producto | `software-factory` (+ repos generados por instalador) | CI verde, GitOps synced, health OK |
| Académico | `kaanbal-research` (privado) | Evidencia metodológica, bitácora, tesis |

## POC actual

Instalar en PC local Ubuntu Server (Pamela / laboratorio) el stack completo: Kaanbal + FagoLab, demostrando que un investigador puede replicar el escenario en su propia máquina con su propia org GitHub.

## Secuencia prioritaria

```text
Contexto y contratos → seguridad host → instalador → Kaanbal Core
→ Tailscale/Cloudflare → app prueba → FagoLab → backup/restore
→ Agent Runtime → artefactos → MLOps
```

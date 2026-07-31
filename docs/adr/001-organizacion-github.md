# ADR-001: Organización GitHub canónica

Estado: **aceptado** — 2026-07-26

## Contexto

Existen referencias a tres organizaciones:

- `ProyectosUniUAEH` — remoto actual de software-factory y fago-sistema
- `futurefarms-softwarefactory` — hardcodeado en ApplicationSets y AGENTS legacy
- `futurefarms-mx` — README del instalador

## Decisión propuesta

| Uso | Org |
|-----|-----|
| POC privada (Andrés: Kaanbal + FagoLab) | `ProyectosUniUAEH` |
| Instalador open source (futuro) | Repo público separado; cada cliente elige **su** org al instalar |
| Investigación | `ProyectosUniUAEH/kaanbal-research` (privado) |

## Consecuencias

- Reemplazar hardcodes `futurefarms-*` por variables de instalación
- ApplicationSets deben apuntar al `infra-gitops` del cliente
- Documentar en wizard del instalador: org obligatoria

## Alternativas rechazadas

- Mantener `futurefarms-softwarefactory` — no es la org del POC actual
- Un solo monorepo para runtime — el deployer clona repos separados por diseño

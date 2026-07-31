# Contrato de documentación Confluence — SoftwareFa

Space: **SoftwareFa** (`524291`)  
URL: https://asistenteia97.atlassian.net/wiki/spaces/SoftwareFa  
Homepage ID: `524383`

## Regla de oro

| Dónde | Qué vive | Por qué |
|-------|----------|---------|
| **Git** `docs/` | ADRs, contratos, arquitectura, código-adjacent | Se revisa en el PR; fuente técnica canónica |
| **Jira SF** | Estado, criterios, evidencia corta | Unidad de trabajo |
| **Confluence** | Narrativa, guías, bitácora legible, onboarding OSS | Humanos, comité, futuros contribuidores |
| **Miro** | Diagramas visuales, workshops | Exploración y presentación |
| **Chat Cursor** | PRUEBAS manuales en crudo | Evidencia inmediata → luego sintetizada |

**Nunca duplicar** un ADR completo en Confluence. Enlazar al archivo en Git.

**Nunca** pegar secretos, tokens, IPs privadas sensibles, ni datos de participantes.

---

## Jerarquía del space

```text
SoftwareFactory Home
├── 1. Producto y usuarios
│   ├── Qué es Kaanbal
│   ├── Guía de instalación (lab / Pamela)
│   ├── Guía de la consola
│   └── FAQ y troubleshooting
├── 2. Documentación técnica (índice → Git)
│   ├── Arquitectura (resumen + enlaces)
│   ├── Contratos y ADRs (índice)
│   ├── GitOps y repos generados
│   └── Referencia del instalador
├── 3. Bitácora de desarrollo
│   ├── Fase 0 — Bootstrap
│   ├── Entregas por ticket (SF-XXX)
│   └── Lecciones aprendidas
├── 4. Open Source
│   ├── Por qué open-core
│   ├── Cómo contribuir (resumen → CONTRIBUTING.md)
│   ├── Seguridad y reporte de vulnerabilidades
│   └── Roadmap público
└── 5. Enlaces rápidos
    ├── Jira SF board
    ├── Miro Kaanbal
    └── Repos GitHub
```

---

## Tipos de página y plantillas

### A. Página de producto (audiencia: usuario / administrador)

**Cuándo:** nueva feature visible, guía de instalación, FAQ.

**Secciones obligatorias:**
1. Para quién es
2. Qué lograrás al terminar
3. Requisitos previos
4. Pasos numerados
5. Verificación (cómo saber que funcionó)
6. Problemas frecuentes
7. Enlaces relacionados (Jira, Git, Miro)

### B. Página técnica (audiencia: desarrollador)

**Cuándo:** arquitectura, flujo GitOps, contrato de API.

**Secciones obligatorias:**
1. Contexto (2–3 frases)
2. Diagrama o enlace Miro
3. Componentes y responsabilidades
4. **Enlace al doc canónico en Git** (no copiar)
5. Decisiones pendientes
6. Tickets relacionados (SF-XXX)

### C. Entrega de ticket (audiencia: equipo + futuro tú)

**Cuándo:** al cerrar SF-XXX (`tarea-cerrar`).

**Secciones obligatorias:**
1. Ticket: SF-XXX — título
2. Objetivo
3. Qué se hizo (bullets)
4. PR / commits (enlaces)
5. Pruebas ejecutadas (copiar bloque PRUEBA del chat)
6. Riesgos y rollback
7. Qué quedó pendiente

**Nombre de página:** `SF-XXX — {título corto}`  
**Padre:** sección Bitácora → Fase correspondiente

### D. Bitácora de fase (audiencia: tesis + OSS)

**Cuándo:** inicio/fin de fase o milestone (SF-1, SF-8).

**Secciones:** objetivo, tickets incluidos, timeline, métricas (ej. tiempo instalación), lecciones, enlaces.

---

## Flujo del documentador

```text
Trigger: "documenta SF-XXX" | cierre de sesión | milestone
  → Leer Jira SF-XXX
  → Leer comentarios + PRUEBA en chat
  → Elegir plantilla A/B/C/D
  → Crear o actualizar página Confluence
  → Enlazar desde homepage o índice de fase
  → Comentar en Jira: "Doc: {url Confluence}"
```

---

## Open Source — criterio de calidad

Un doc en Confluence está listo para respaldar OSS cuando:

- [ ] Un contribuidor externo entiende qué es Kaanbal sin leer el chat
- [ ] La guía de instalación es reproducible sin credenciales tuyas personales
- [ ] Cada decisión importante enlaza a ADR en Git o explica el porqué en prosa
- [ ] No hay secretos ni referencias a orgs/domains obsoletos sin marcar como histórico

---

## IDs Confluence (actualizar al crear páginas)

| Página | ID |
|--------|-----|
| Homepage / Mapa | 524383 |
| Space | 524291 |
| 1. Producto y usuarios | 164041 |
| 2. Documentación técnica | 622593 |
| 3. Bitácora de desarrollo | 164061 |
| 4. Open Source | 196753 |

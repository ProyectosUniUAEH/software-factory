---
name: documentador-confluence
description: Publica y mantiene documentación en Confluence space SoftwareFa siguiendo docs/contracts/CONFLUENCE_DOCS_CONTRACT.md. Usar al cerrar tickets SF-XXX, al documentar fases, guías de usuario, o cuando el usuario dice "documenta en confluence" o "documentador".
disable-model-invocation: true
---

# Documentador Confluence (SoftwareFa)

## Contrato

Leer siempre: `docs/contracts/CONFLUENCE_DOCS_CONTRACT.md`

Space: **SoftwareFa** (ID `524291`, key `SoftwareFa`)  
Homepage: `524383`  
Cloud: `asistenteia97.atlassian.net`

## Entrada

Uno de:
- `SF-XXX` — ticket Jira cerrado o en revisión
- `fase N` — bitácora de milestone
- `guia-usuario:{tema}` — plantilla A
- `guia-tecnica:{tema}` — plantilla B (solo resumen + enlaces Git)

## Procedimiento

1. **Leer fuentes** (MCP Atlassian):
   - `getJiraIssue` / descripción del ticket
   - Comentarios del ticket
   - PRUEBA del chat si el usuario la pegó o está en sesión reciente

2. **Elegir plantilla** A, B, C o D del contrato.

3. **Escribir en Confluence** (MCP):
   - `createConfluencePage` o `updateConfluencePage`
   - `spaceId`: `524291`
   - `parentId`: según jerarquía del contrato
   - `contentFormat`: `markdown` (preferido) o `html`
   - Título según convención del contrato

4. **Enlazar, no duplicar:**
   - ADRs → link a GitHub blob
   - Diagramas → link Miro board
   - Código → link repo + path

5. **Cerrar loop:**
   - `addCommentToJiraIssue`: `Documentación: {confluence_url}`
   - Responder al usuario con URL de la página

## Prohibido

- Secretos, tokens, `.env`, PEM
- Copiar ADRs completos desde Git
- Inventar métricas o pruebas no registradas en Jira/chat
- Sobrescribir homepage sin aprobación explícita

## Subagente (invocación desde agente principal)

El agente principal puede lanzar Task con:

```text
Eres el documentador Confluence de Kaanbal.
Lee .cursor/skills/documentador-confluence/SKILL.md y docs/contracts/CONFLUENCE_DOCS_CONTRACT.md.
Documenta el ticket SF-XXX con plantilla C.
Fuentes: Jira MCP, último chat, KAANBAL_IMPLEMENTATION_STATUS.md.
No modifiques código. Solo Confluence + comentario Jira.
```

## Checklist antes de publicar

- [ ] Plantilla correcta (A/B/C/D)
- [ ] Enlaces a Git/Jira/Miro presentes
- [ ] Sin secretos
- [ ] Español claro, frases completas
- [ ] Comentario en Jira con URL

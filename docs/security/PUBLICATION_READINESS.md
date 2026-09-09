# Revisión previa a publicación — 2026-09-08

## Decisión

**Mantener el repositorio privado.** La limpieza del árbol actual no autoriza
publicar su historial. No se modificó la visibilidad ni se reescribió el remoto.

## Alcance y resultado

- Gitleaks 8.30.1, binario verificado con el checksum de su release.
- Tres commits originales, todas las referencias locales descargadas de origin.
- 21 detecciones históricas: 20 asignaciones de credenciales literales en
  manifiestos de aplicaciones antiguas y un script de Argo; una referencia de
  imagen Docker es falso positivo.
- Las 20 asignaciones se sustituyeron por configuración requerida en esta rama.
  Los manifiestos de apps de ejemplo no deben desplegarse con `CHANGE_ME`.
- No se imprimieron ni se probaron las credenciales. Deben tratarse como
  potencialmente comprometidas, aunque su vigencia no se haya comprobado.
- No hay `.env` ni `.pem` versionados en las rutas revisadas del historial.
  No se abrieron archivos de esas clases. No se auditó la carpeta externa de
  credenciales ni el contenido de archivos ignorados del equipo del usuario.
- Una exploración automática no certifica ausencia absoluta de secretos.

Ubicaciones a revisar para rotación: `infra-gitops/apps/*/overlays/*/kustomization.yaml`
(secretos de app y contraseñas de bases de datos) y
`infra-gitops/terraform/scripts/set-argocd-pass.sh`. No se reproducen sus valores.

## Antes de cambiar la visibilidad

1. Identificar instalaciones que usaron esas credenciales y rotarlas allí. Esto
   requiere acceso y coordinación con sus propietarios; este PR no las rota.
2. Elegir una publicación de historial limpio: repositorio nuevo desde la revisión
   saneada o reescritura coordinada de TODAS las referencias del repositorio actual.
   Cambiar sólo la rama predeterminada no elimina las otras referencias.
3. Si se conserva la URL mediante reescritura, guardar respaldo privado, coordinar
   los clones existentes y revisar PR, tags y referencias retenidas por GitHub.
   No ejecutar un force-push genérico sin revisar exactamente las referencias.
4. Repetir el escaneo de historial y del árbol que se publicará. Revisar también
   releases, adjuntos, artefactos y datos retenidos fuera de los commits.
5. Completar instalación desde cero, acceso, reinicio y recuperación en `pam-lab`.

## Cambios del instalador incluidos

- Ruta pública de bootstrap con descarga completa antes de ejecutar y revisión fijable.
- Loopback para wizard, runtime del asistente y acceso provisional Argo, mediante SSH.
- Puertos ocupados no provocan la terminación de servicios desconocidos.
- Kubeconfig administrativo con modo 600 en instalaciones nuevas.
- UI y modo desatendido comparten validación de configuración y proveedores.
- Vault conserva material de recuperación ANTES del unseal; aborta si falla y
  verifica KV v2. Su recuperación no imprime claves ni reinicializa almacenamiento.
- El hook de inicialización KMS no participa en el baseline local Shamir.
- Fallos de configuración, CI o acceso no se anuncian como instalación completa.
- Finalización comprueba login real contra la API; VPN exige confirmación del usuario.

## Límites pendientes

No se ejecutó instalación integral en Ubuntu 26.04 ni se verificaron las versiones
externas móviles de K3s/Argo/Tailscale. No hay auto-unseal. El token raíz utilizado
por el bootstrap sigue siendo la credencial Vault sembrada en la API, como en la
implementación anterior; sustituirlo por autenticación de alcance limitado y su
ciclo de renovación es una mejora pendiente. El respaldo de claves no reemplaza
el respaldo de datos. No se declara esta entrega producción validada.

## Evidencia local

Pruebas ejecutadas en Windows con Python 3.12 y PyYAML 6.0.2: 88 pruebas
correctas, ninguna omitida. Sintaxis Bash de ambas entradas y JavaScript del
wizard correctas. Los 17 YAML modificados y el workflow parsean correctamente.
Gitleaks del árbol saneado: cero detecciones. El historial original mantiene las
20 asignaciones detectadas hasta realizar una limpieza separada.

# Kaanbal

Kaanbal instala y administra aplicaciones en un servidor propio usando GitHub,
GitOps y Argo CD. Las aplicaciones pueden exponerse en LAN, VPN o públicamente.

## Estado de esta entrega

Instalador piloto en validación. **No cambiar todavía este repositorio a público:**
la revisión del historial encontró credenciales anteriores. Eliminarlas del árbol
actual no las elimina de commits, ramas ni PR anteriores. Consulta el
[informe de publicación](docs/security/PUBLICATION_READINESS.md).

## Instalar

El recorrido completo de Ubuntu, clave SSH, alias, túnel y navegador está en el
[manual de Pamela](docs/guides/PAMELA_INSTALL.md). Después de aprobar la publicación,
ejecuta dentro de la sesión SSH del servidor:

```bash
( set -e; if ! command -v curl >/dev/null; then sudo apt-get update; sudo apt-get install -y curl ca-certificates; fi; revision=main; script=$(mktemp); trap 'rm -f "$script"' EXIT; curl --fail --show-error --location "https://raw.githubusercontent.com/ProyectosUniUAEH/software-factory/${revision}/install.sh" --output "$script"; bash "$script" --ref "$revision" )
```

Usa un SHA aprobado en lugar de `main` para repetir exactamente el código de una
prueba. La versión de K3s y Argo usada por el instalador aún requiere fijación y
validación integral; fijar el código no fija todas las dependencias externas.

El usuario atiende sudo en su terminal y completa las credenciales en el navegador.
No hace falta entregar contraseñas, archivos `.env` ni claves privadas al agente.
El instalador se atiende por túnel SSH y escucha solamente en loopback.

El perfil actual necesita GitHub y Docker Hub. Cloudflare y dominio corresponden
al acceso público; Tailscale al privado. No se ha implementado el builder local
con registro OCI alternativo. Vault usa recuperación manual después de reiniciar.

## Desarrollo y verificación

```bash
python3 -m pip install PyYAML==6.0.2
python3 -m unittest discover -s SOFTWARE_FACTORY/installer -p 'test_*.py'
bash -n install.sh
bash -n SOFTWARE_FACTORY/install.sh
node --check SOFTWARE_FACTORY/installer/static/app.js
```

PyYAML es una dependencia de pruebas; el instalador usa Python stdlib.

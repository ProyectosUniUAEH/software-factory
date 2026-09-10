# Handoff — instalación limpia de Kaanbal en Pam Lab

## Objetivo

Acompañar la instalación real de Kaanbal en el Ubuntu Server de Pamela, detectar
errores, corregir el producto en `main`, validar la corrección y repetir la
instalación limpia cuando sea necesario.

Al iniciar, responde exactamente con esta frase después de verificar el repo:

> Encontré la fuente principal de Kaanbal y el contexto de Pam Lab. Estoy verificando el instalador y el servidor.

## Fuente principal

- Repositorio: `ProyectosUniUAEH/software-factory`
- Rama de prueba autorizada: `main`
- Revisión conocida al crear este handoff: `1416004`
- Entrada pública: `install.sh`
- Instalador real: `SOFTWARE_FACTORY/install.sh`
- Pruebas: `SOFTWARE_FACTORY/installer/test_*.py`
- Manual: `docs/guides/PAMELA_INSTALL.md`

Antes de actuar, ejecuta `git fetch origin main`, compara `HEAD` con
`origin/main` y trabaja con la revisión más reciente. Andrés autorizó durante
este piloto commits y pushes directos a `main` para acelerar las pruebas.

## Pam Lab

- Usuario Linux: `pam`
- IP LAN conocida: `192.168.1.48`
- IP Tailscale conocida: `100.99.9.107`
- Alias esperados: `pam-lab` y `pam-lab-vpn`
- El usuario introduce personalmente contraseñas de SSH y `sudo`.

Estado observado al crear este handoff: `pam-lab-vpn` informó que su
`IdentityFile` no existe. No busques, abras ni imprimas claves privadas. Si el
alias sigue fallando, informa la ruta ausente sin mostrar contenido y pide al
usuario corregirla o conectarse temporalmente con contraseña.

## Comando único de prueba

Con Tailscale previamente instalado y autenticado en Ubuntu:

```bash
curl -fsSL https://raw.githubusercontent.com/ProyectosUniUAEH/software-factory/main/install.sh -o /tmp/kaanbal-install.sh && bash /tmp/kaanbal-install.sh --ref main --reset --tailscale
```

El comando descarga antes de borrar, limpia solamente la instalación local
administrada por Kaanbal, solicita `sudo` y debe imprimir una URL parecida a:

```text
http://100.99.9.107:3000/?token=TOKEN_TEMPORAL
```

Nunca copies el token al chat, a Git, a logs compartidos ni a este documento.

## Diagnóstico seguro

Si ocurre un error:

1. Confirma el SHA descargado y el estado limpio del repo.
2. Comprueba `systemctl status kaanbal-installer`, `k3s` y los puertos
   `3000`, `4600` y `8080` sin imprimir variables de entorno.
3. Lee sólo las líneas necesarias de `journalctl -u kaanbal-installer`; redacta
   tokens, contraseñas y URLs de sesión.
4. Reproduce el fallo en código, añade una prueba útil y ejecuta toda la suite
   del instalador.
5. Corrige en `main`, vuelve a validar, sube el commit y repite desde cero sólo
   dentro del alcance de Kaanbal en Pam Lab.

No leas `.env`, `*.pem`, archivos de recuperación de Vault ni el token de
`/run/kaanbal-installer`. No borres contenedores o datos ajenos a Kaanbal. No
modifiques recursos externos de GitHub, Cloudflare, Docker Hub o Tailscale
durante un reset local.

## Criterio de éxito

- El bootstrap imprime una URL LAN o Tailscale con token en una sola ejecución.
- La UI en `3000` y Acuaponsito en `4600` responden desde el navegador elegido.
- Las credenciales se validan antes de desplegar.
- La instalación completa termina, permite login y muestra el estado de Argo.
- Se documentan errores y evidencia sin secretos.

# Instalación piloto de Kaanbal para Pamela

La validación integral en Ubuntu 26.04, el reinicio y la recuperación están
pendientes hasta ejecutar las pruebas de este manual. No incorporar todavía
información importante del laboratorio.

## 1. Preparar Ubuntu Server

Instala Ubuntu Server con OpenSSH Server y un usuario con sudo. Conecta el
servidor a la red local, preferiblemente por Ethernet. Obtén su IP con
`hostname -I`. Comprueba RAM, disco, Internet y que cerrar la tapa no suspenda
el equipo. Revisa los servicios existentes antes de instalar o borrar nada.

## 2. Conectar Windows mediante SSH

En PowerShell de tu PC: `ssh pam@192.168.1.48`. Sustituye usuario e IP cuando
corresponda. Verifica la huella contra la consola del servidor antes de aceptar
la conexión inicial. Introduce tú la contraseña de Ubuntu; `exit` regresa a tu PC.

Conserva el alias y la clave si ya funcionan. Para una clave nueva:

```powershell
Test-Path "$env:USERPROFILE/.ssh/pam_lab_ed25519"
ssh-keygen -t ed25519 -f "$env:USERPROFILE/.ssh/pam_lab_ed25519" -C "pamela-laboratorio"
```

Si Test-Path devuelve True, elige otro nombre. No sobrescribas la clave.
Introduce personalmente una frase de paso. Ed25519 usa OpenSSH y no necesita
convertirse ni llamarse `.pem`. El archivo sin extensión es privado; `.pub` es
público. El agente nunca debe abrir la clave privada ni pedir que la pegues.

Instala solamente la pública; el humano introduce la contraseña inicial:

```powershell
Get-Content "$env:USERPROFILE/.ssh/pam_lab_ed25519.pub" | ssh pam@192.168.1.48 'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys; tr -d "\r" >> ~/.ssh/authorized_keys'
```

Añade a `%USERPROFILE%\.ssh\config`, sin reemplazar entradas ni duplicar alias:

```sshconfig
Host pam-lab
    HostName 192.168.1.48
    User pam
    IdentityFile ~/.ssh/pam_lab_ed25519
    IdentitiesOnly yes
```

Comprueba `ssh pam-lab`. La frase de paso puede solicitarse. Si está disponible
OpenSSH Authentication Agent en Windows, `ssh-add "$env:USERPROFILE/.ssh/pam_lab_ed25519"`
permite desbloquear la clave para tu sesión. Introduce tú la frase. No la
elimines ni habilites sudo sin contraseña para facilitar acceso a un agente.

Cursor, Claude o Codex pueden usar ese alias. El humano atiende los prompts
interactivos y confirma al agente que continúe. SSH y sudo son autenticaciones
distintas: sudo puede pedir la contraseña de Ubuntu aunque SSH use una clave.

## 3. Un comando de instalación

El repositorio y la revisión deben ser públicos. Dentro de `ssh pam-lab`:

```bash
( set -e; if ! command -v curl >/dev/null; then sudo apt-get update; sudo apt-get install -y curl ca-certificates; fi; revision=main; script=$(mktemp); trap 'rm -f "$script"' EXIT; curl --fail --show-error --location "https://raw.githubusercontent.com/ProyectosUniUAEH/software-factory/${revision}/install.sh" --output "$script"; bash "$script" --ref "$revision" )
```

Para reproducir la prueba, reemplaza `main` por el SHA completo aprobado al
publicar; usa el mismo SHA para Pamela. `main` es móvil. Curl debe terminar
correctamente antes de ejecutar el archivo: un 404 del repo privado detiene
el comando. El bootstrap descarga en `~/kaanbal-source` y muestra el SHA. No
reemplaza directorios existentes. Instala dependencias básicas si faltan; el
humano introduce sudo cuando se solicite. Las credenciales van después en UI.

Para reanudar un checkout válido ya descargado:

```bash
sudo bash ~/kaanbal-source/SOFTWARE_FACTORY/install.sh
```

No borres carpetas ni uses reset para resolver errores sin diagnóstico. Una
descarga parcial se conserva para revisar; `--dir` permite elegir otra ruta
nueva. Las credenciales existentes no se sobrescriben con otro archivo.

## 4. Abrir el navegador y completar credenciales

Desde otra terminal PowerShell de la PC, conserva abierto:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:3000:127.0.0.1:3000 -L 127.0.0.1:4600:127.0.0.1:4600 -L 127.0.0.1:8080:127.0.0.1:8080 pam-lab
```

Abre la URL `http://localhost:3000/?token=...` impresa por el instalador. No
compartas ese token ni capturas que lo incluyan. Loopback más SSH protege el
transporte; no publiques esos puertos HTTP. 4600 sirve al asistente IA y 8080
al acceso provisional de Argo. Si un puerto está ocupado, identifica al dueño;
no mates servicios desconocidos. Cerrar el túnel interrumpe el navegador, pero
el instalador sigue bajo systemd. Reabre el túnel para retomar el progreso.

Crea el administrador y una contraseña larga. Completa los proveedores:

- GitHub: organización/usuario donde puedas crear repos. PAT classic con
  `repo`, `workflow` y `read:org` según la organización. SSO puede requerir
  autorización. `delete_repo` no es necesario para instalar. Usa un destino de
  prueba que no contenga repos del core de otra instalación.
- Docker Hub: usuario y token dedicado de lectura/escritura para publicar las
  imágenes. Sigue siendo parte del flujo actual.
- Cloudflare: para publicación, cuenta, zona/dominio y permisos Tunnel/DNS
  indicados por el asistente. La zona debe pertenecer a la cuenta elegida.
- Tailscale: para VPN, OAuth del operador y tags/grants indicados por las
  validaciones. Autenticar OAuth no prueba conectividad. La PC también necesita
  acceso a la tailnet.
- IA: opcional; puede configurarse después.

El humano introduce secretos en UI, nunca en el chat. El modo por archivo
`--unattended --env /ruta/segura/...` sigue disponible; este manual usa UI. El
agente nunca lee `.env` ni claves privadas. Corrige validaciones fallidas antes
de instalar; conserva evidencia sin credenciales del progreso.

## 5. Verificación, Vault y reinicio

Comprueba login real, pods, aplicaciones de Argo y una app de demostración por
el canal elegido. Confirma el cierre del instalador después de verificar el
acceso administrativo.

Vault usa desbloqueo manual en este piloto. Conserva sus claves originales en
un respaldo protegido fuera del servidor mediante el mecanismo de entrega
validado. El token raíz es distinto de la clave de desbloqueo; ambos son
secretos. Una copia en el mismo clúster no es un respaldo externo. No generes
una clave sustituta ni reinicialices Vault para corregir acceso.

El instalador guarda la recuperación en `/etc/kaanbal/vault-recovery.json`,
con permisos 600. Para preparar una copia que puedas descargar, ejecuta tú
estos comandos en la sesión SSH (no imprimen su contenido):

```bash
sudo install -D -m 600 -o "$USER" -g "$(id -gn)" /etc/kaanbal/vault-recovery.json "$HOME/.local/share/kaanbal/vault-recovery.json"
```

Desde PowerShell descarga mediante SCP a una carpeta personal protegida:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE/kaanbal-backup" | Out-Null
scp pam-lab:.local/share/kaanbal/vault-recovery.json "$env:USERPROFILE/kaanbal-backup/vault-recovery.json"
```

Guarda esa copia en almacenamiento cifrado o un gestor de secretos y limita
quién accede a ella. No la adjuntes al chat ni la añadas a Git. Es material de
recuperación, no una copia de los datos de las aplicaciones.

Coordina un reinicio. Para desbloquear con el archivo protegido ya instalado:

```bash
sudo python3 ~/kaanbal-source/SOFTWARE_FACTORY/installer/vault_bootstrap.py --recover
```

El comando usa las claves originales sin imprimirlas y rechaza inicializar un
Vault vacío. Si falta el archivo, restaura primero el respaldo original a su
ruta con propietario root y modo 600. El agente comprueba estado sin leerlo. No pongas la clave como argumento de una orden que quede en logs
o historial. Este procedimiento no configura auto-unseal externo. Respalda los
datos y prueba restauración: las claves solas no recuperan los datos.

Documenta las pruebas antes de afirmar que está listo:

```text
PRUEBA: piloto Kaanbal — revisión <SHA>
FECHA:
PRECONDICIONES: Ubuntu, recursos, SSH y proveedores elegidos.
PASOS: instalación UI; login; app demo; reinicio coordinado;
       desbloqueo Vault; persistencia y restauración de backup.
RESULTADO ESPERADO: acceso y datos conservados; recuperación documentada.
RESULTADO OBTENIDO:
EVIDENCIA: comandos y URLs sin tokens, capturas sin credenciales.
APROBADO: sí/no; enumerar verificaciones pendientes.
```

Explicación breve: “Kaanbal permite instalar y administrar aplicaciones en
nuestro servidor. Colaboramos en GitHub, validamos cambios y desplegamos versiones
controladas, con acceso local, VPN o público según la aplicación. Estamos
verificando persistencia y recuperación antes de cargar información importante”.

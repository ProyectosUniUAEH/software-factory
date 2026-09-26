# Migración a `kaanbal-softwarefactory/software-factory`

El proyecto se mudó de `ProyectosUniUAEH/software-factory` a
**`kaanbal-softwarefactory/software-factory`** y empieza allí como una sola versión
inicial (`v1.0.0`), sin el historial anterior. Este documento explica qué hacer con
una célula que ya está instalada.

## Qué cambia y qué no

| Cambia | No cambia |
|---|---|
| De dónde la célula descarga actualizaciones | Tus apps, dominios, bases de datos y volúmenes |
| El `origin` del checkout `~/kaanbal-source` del nodo | Vault, secretos y credenciales |
| El commit instalado deja de existir en el historial del repo nuevo | Tus repos de GitHub (`infra-gitops`, `kaanbal-api`, …) |

## Por qué son dos actualizaciones

Una célula solo puede recibir actualizaciones de donde *ya sabe* buscarlas. Por eso el
cambio de fuente viaja por el camino de siempre y el resto llega después:

1. **Primera actualización, desde el repo anterior.** Trae la lógica nueva: la célula
   pasa a consultar el repo nuevo y, en el nodo, `origin` deja de apuntar al anterior.
2. **Segunda actualización, desde el repo nuevo.** El commit que la célula tiene
   instalado ya no existe en ese historial, así que Updates no puede comparar; ofrece
   directamente la última revisión de `main`. Al aplicarla queda registrada la
   procedencia nueva (`upstream: kaanbal-softwarefactory/software-factory`) y las
   actualizaciones siguientes vuelven a listar commits con normalidad.

## Paso a paso (consola)

1. **Updates → Actualizar ahora.** Espera a que termine el Job y la consola vuelva.
2. Recarga **Updates**. Debe decir *«El commit instalado (`xxxxxxx`) no existe en
   `kaanbal-softwarefactory/software-factory`: el proyecto se mudó o reescribió su
   historial»* y mostrar el botón **Actualizar ahora**.
3. Pulsa **Actualizar ahora** otra vez.
4. Comprueba que Updates muestra `main @ …` de la fuente nueva y *«Esta célula está al día»*.

## Paso a paso (desde el nodo)

```bash
sudo KAANBAL_ORG=<tu-org> bash ~/kaanbal-source/SOFTWARE_FACTORY/tools/core-upgrade.sh --ref main
# El script muda `origin` al repo nuevo. Vuelve a ejecutarlo para aplicar v1:
sudo KAANBAL_ORG=<tu-org> bash ~/kaanbal-source/SOFTWARE_FACTORY/tools/core-upgrade.sh --ref main
```

Si prefieres mudar el remoto tú mismo, o mantener uno propio (un fork):

```bash
git -C ~/kaanbal-source remote set-url origin https://github.com/kaanbal-softwarefactory/software-factory.git
# Para que el script NO toque origin:
sudo KAANBAL_KEEP_ORIGIN=1 KAANBAL_ORG=<tu-org> bash ~/kaanbal-source/SOFTWARE_FACTORY/tools/core-upgrade.sh --ref main
```

## Instalar o actualizar desde un fork

El repo oficial es el valor por defecto; se puede cambiar sin reconstruir nada:

- **Instalación nueva:** `KAANBAL_REPO=https://github.com/<owner>/<repo>.git bash install.sh …`
- **Célula existente:** define `core_upstream: "<owner>/<repo>"` en `system_config`, o la
  variable `KAANBAL_UPSTREAM` en el Deployment de `kaanbal-api`. Un valor que no sea
  `owner/repo` de GitHub se ignora y se usa el oficial.

## Si algo sale mal

El upgrade es una transacción con verificación y **rollback automático**: si los pods no
quedan sanos, se restauran las imágenes anteriores. La migración solo cambia dónde se
buscan actualizaciones; volver atrás es `git -C ~/kaanbal-source remote set-url origin <url-anterior>`.

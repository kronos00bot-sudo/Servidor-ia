# Guía de Remediación de Seguridad
## DGX Spark (Servidor) + UM890 PRO (Cliente)
### Stack de IA local: Ollama · OpenClaw · Telegram · Open WebUI

> **Resumen de hallazgos:** 4 Críticos · 6 Altos · 5 Medios · 4 Informativos
>
> Se recomienda abordar primero los hallazgos **Críticos** antes de poner el sistema en producción.

---

## Índice

- [Hallazgos Críticos](#hallazgos-críticos)
  - [C1 — Ollama expuesto sin autenticación](#c1--ollama-expuesto-en-todas-las-interfaces-sin-autenticación)
  - [C2 — OpenClaw gateway con auth deshabilitada](#c2--openclaw-gateway-con-autenticación-completamente-deshabilitada)
  - [C3 — Instalación mediante curl | sh sin verificación](#c3--instalación-de-software-mediante-curl--sh-sin-verificación)
  - [C4 — Open WebUI con --network=host sin auth inicial](#c4--open-webui-con---networkhost-y-sin-autenticación-inicial-configurada)
- [Hallazgos de Nivel Alto](#hallazgos-de-nivel-alto)
  - [A1 — Secure Boot deshabilitado](#a1--secure-boot-deshabilitado-explícitamente-en-el-um890)
  - [A2 — Token de Telegram en texto plano](#a2--token-de-telegram-almacenado-en-texto-plano)
  - [A3 — Credenciales OAuth de Google sin protección](#a3--credenciales-oauth-de-google-sin-protección-adecuada)
  - [A4 — Agente IA con acceso completo a Google Workspace](#a4--agente-ia-con-acceso-completo-a-google-workspace-sin-confirmación-humana)
  - [A5 — Usuario en el grupo docker](#a5--usuario-en-el-grupo-docker-equivale-a-root-sin-contraseña)
  - [A6 — Symlink global de gog controlable por el usuario](#a6--symlink-global-de-gog-controlable-por-el-usuario)
- [Hallazgos de Nivel Medio](#hallazgos-de-nivel-medio)
  - [M1 — Open WebUI usando imagen :main](#m1--open-webui-usando-imagen-main-tag-mutable)
  - [M2 — Bot de Telegram accesible antes del pairing](#m2--bot-de-telegram-accesible-a-cualquier-usuario-antes-del-pairing)
  - [M3 — Memoria del agente en texto plano](#m3--memoria-del-agente-en-texto-plano-sin-cifrado-de-disco)
  - [M4 — OpenClaw desde npm sin verificación adicional](#m4--instalación-de-openclaw-desde-npm-sin-verificación-adicional)
  - [M5 — Acceso del UM890 al DGX sin Tailscale ACLs](#m5--acceso-del-um890-al-dgx-sin-tailscale-acls-configuradas)
- [Hallazgos Informativos](#hallazgos-informativos)
  - [I1 — App Google Cloud en modo Externo publicada](#i1--app-de-google-cloud-en-modo-externo-publicada)
  - [I2 — loginctl enable-linger: agente activo sin sesión](#i2--loginctl-enable-linger-agente-activo-sin-sesión)
  - [I3 — OLLAMA_DEBUG=INFO expone fragmentos en logs](#i3--ollama_debuginfo-puede-exponer-fragmentos-de-prompts-en-logs)
  - [I4 — IP de Tailscale hardcodeada en múltiples archivos](#i4--ip-de-tailscale-del-dgx-hardcodeada-en-múltiples-archivos)
- [Checklist de Verificación Final](#checklist-de-verificación-final)

---

## Hallazgos Críticos

> ⛔ Resolver estos puntos **antes** de conectar el sistema a cualquier red o servicio externo.

---

### C1 — Ollama expuesto en todas las interfaces sin autenticación

**Severidad:** `CRÍTICO`  
**Afecta:** DGX Spark (§11) · UM890 PRO (§19.2)

Las secciones §11 y §19.2 configuran `OLLAMA_HOST=0.0.0.0`, exponiendo el puerto `11434` en todas las interfaces de red. Ollama no tiene autenticación nativa: cualquier dispositivo en la red local o en la tailnet puede listar modelos, ejecutar inferencia y subir modelos personalizados sin credenciales.

#### Cómo arreglarlo

**Paso 1 — Restringir Ollama a localhost en ambas máquinas:**

```bash
# En DGX y UM890 — editar el override de systemd
sudo nano /etc/systemd/system/ollama.service.d/override.conf

# Cambiar:
Environment="OLLAMA_HOST=0.0.0.0"
# Por:
Environment="OLLAMA_HOST=127.0.0.1"

sudo systemctl daemon-reload && sudo systemctl restart ollama
```

**Paso 2 — Instalar un reverse proxy con autenticación (ejemplo con Caddy):**

```bash
sudo apt install -y caddy

# /etc/caddy/Caddyfile
:11435 {
  basicauth {
    mloco <hash_de_contraseña>
  }
  reverse_proxy 127.0.0.1:11434
}

# Generar hash de contraseña:
caddy hash-password
```

**Paso 3 —** Actualizar las referencias al DGX en el UM890 para incluir credenciales o apuntar al puerto del proxy.

---

### C2 — OpenClaw gateway con autenticación completamente deshabilitada

**Severidad:** `CRÍTICO`  
**Afecta:** UM890 PRO (§20.2)

La configuración del UM890 incluye tres flags peligrosos simultáneamente: `"allowInsecureAuth": true`, `"dangerouslyDisableDeviceAuth": true` y `"dangerouslyAllowHostHeaderOriginFallback": true`. Con `bind: lan` el gateway queda accesible en la red local sin ninguna verificación de identidad.

#### Cómo arreglarlo

**Paso 1 — Editar `~/.openclaw/openclaw.json` y corregir el bloque `controlUi`:**

```json
"controlUi": {
  "allowInsecureAuth": false,
  "dangerouslyAllowHostHeaderOriginFallback": false,
  "dangerouslyDisableDeviceAuth": false,
  "allowedOrigins": [
    "http://127.0.0.1:18789",
    "http://localhost:18789"
  ]
}
```

**Paso 2 — Cambiar `bind` de `lan` a `loopback`:**

```json
"gateway": {
  "bind": "loopback",
  ...
}
```

**Paso 3 — Para acceder al panel web desde otro dispositivo, usar un túnel SSH:**

```bash
ssh -L 18789:127.0.0.1:18789 mloco@IP_UM890
# Luego abrir: http://localhost:18789
```

---

### C3 — Instalación de software mediante `curl | sh` sin verificación

**Severidad:** `CRÍTICO`  
**Afecta:** DGX Spark (§6.1, §8.1, §12.2) · UM890 PRO (§19.1, §20.1, §23.1)

Se usa el patrón `curl ... | sh` en tres instalaciones: Ollama, Node.js y Tailscale. Este patrón ejecuta código remoto con privilegios de root sin verificar hash ni firma criptográfica. Un ataque MITM, CDN comprometido o DNS envenenado permite ejecución de código arbitrario.

#### Cómo arreglarlo

**Para Ollama — descargar y verificar antes de ejecutar:**

```bash
# Descargar el script
curl -fsSL https://ollama.com/install.sh -o /tmp/ollama-install.sh

# Verificar el hash SHA256 contra el publicado en la web oficial
sha256sum /tmp/ollama-install.sh

# Solo si el hash coincide, ejecutar:
bash /tmp/ollama-install.sh
```

**Para Tailscale — usar el repositorio APT con verificación GPG:**

```bash
# Descargar la clave GPG y verificar el fingerprint en tailscale.com
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg -o /tmp/ts.gpg
gpg --show-keys /tmp/ts.gpg
sudo mv /tmp/ts.gpg /usr/share/keyrings/tailscale-archive-keyring.gpg

# Instalar desde APT (paquetes firmados)
sudo apt install -y tailscale
```

**Para Node.js —** usar `nvm` o el repositorio oficial de NodeSource con verificación GPG, o instalar directamente desde los repositorios de Ubuntu.

---

### C4 — Open WebUI con `--network=host` y sin autenticación inicial configurada

**Severidad:** `CRÍTICO`  
**Afecta:** DGX Spark (§10) · UM890 PRO (§22)

Docker se lanza con `--network=host`, lo que elimina el aislamiento de red del contenedor y expone el puerto `3000` en todas las interfaces. Open WebUI permite que el primer visitante cree la cuenta de administrador, pudiendo ser aprovechado por otro dispositivo en la red.

#### Cómo arreglarlo

**Paso 1 — Reemplazar el comando `docker run` en ambas máquinas:**

```bash
# Detener el contenedor actual
docker stop open-webui && docker rm open-webui

# Relanzar con puerto vinculado solo a localhost y versión fija
docker run -d \
  --name open-webui \
  -p 127.0.0.1:3000:8080 \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:v0.5.20

# Sustituir v0.5.20 por la última versión estable disponible en:
# https://github.com/open-webui/open-webui/releases
```

**Paso 2 —** Acceder inmediatamente a `http://localhost:3000` y crear la cuenta de administrador.

**Paso 3 —** Para acceder desde otros dispositivos, usar un túnel SSH o configurar autenticación y HTTPS con Caddy/nginx.

---

## Hallazgos de Nivel Alto

> ⚠️ Resolver estos puntos antes de exponer el sistema a usuarios adicionales o a internet.

---

### A1 — Secure Boot deshabilitado explícitamente en el UM890

**Severidad:** `ALTO`  
**Afecta:** UM890 PRO (§16.4)

La sección §16.4 indica desactivar Secure Boot. Esto elimina la protección contra bootkits y rootkits que se instalen antes del sistema operativo.

#### Cómo arreglarlo

**Opción 1 — Reactivar Secure Boot con MOK para el driver AMDGPU:**

```bash
# Generar clave MOK (Machine Owner Key)
openssl req -new -x509 -newkey rsa:2048 -keyout /root/mok.key \
  -out /root/mok.crt -days 3650 -subj '/CN=MOK signing key/' -nodes

# Importar la clave
sudo mokutil --import /root/mok.crt

# Reiniciar y aceptar el MOK en el menú azul (MokManager)
sudo reboot
```

**Opción 2 — Si Secure Boot no puede reactivarse, habilitar cifrado de disco LUKS:**

En la próxima instalación de Ubuntu 26.04, seleccionar la opción de cifrado de disco durante el proceso de instalación, o configurar LUKS manualmente en el particionado.

---

### A2 — Token de Telegram almacenado en texto plano

**Severidad:** `ALTO`  
**Afecta:** DGX Spark (§9.2) · UM890 PRO (§21.1)

El token del bot se almacena en `~/.openclaw/config.json` sin cifrado. Cualquier proceso con acceso al directorio home o el propio agente agéntico con herramientas de filesystem puede leer y exfiltrar el token.

#### Cómo arreglarlo

**Paso 1 — Asegurar permisos:**

```bash
chmod 700 ~/.openclaw
chmod 600 ~/.openclaw/openclaw.json
chmod 600 ~/.openclaw/config.json  # si existe
```

**Paso 2 — Usar variables de entorno inyectadas por systemd:**

```bash
# En ~/.openclaw/openclaw.json, la referencia ya debe ser:
# "botToken": "${OPENCLAW_TELEGRAM_BOT_TOKEN}"

# Crear el fichero de credenciales seguro
touch ~/.credentials
chmod 600 ~/.credentials
echo 'OPENCLAW_TELEGRAM_BOT_TOKEN=<TELEGRAM_BOT_TOKEN>' >> ~/.credentials

# Añadir al servicio en ~/.config/systemd/user/openclaw-gateway.service:
# EnvironmentFile=%h/.credentials
```

---

### A3 — Credenciales OAuth de Google sin protección adecuada

**Severidad:** `ALTO`  
**Afecta:** DGX Spark (§13.4)

El archivo `client_secret.json` se copia al home del DGX sin permisos especificados. Este archivo otorga acceso OAuth a Gmail, Drive, Calendar, Contacts y Sheets.

#### Cómo arreglarlo

**Paso 1 — Asegurar permisos y mover a directorio protegido:**

```bash
mkdir -p ~/.config/gog && chmod 700 ~/.config/gog
mv ~/client_secret.json ~/.config/gog/client_secret.json
chmod 600 ~/.config/gog/client_secret.json

# Actualizar la referencia en gog
gog auth credentials ~/.config/gog/client_secret.json
```

**Paso 2 — Eliminar el archivo tras la autenticación inicial:**

```bash
# Verificar que los tokens están guardados
gog auth list --check
# → tu.correo@gmail.com  ✓

# Si los tokens están presentes, eliminar el client_secret
rm ~/.config/gog/client_secret.json
# ⚠️ Guardar una copia offline segura por si hay que reautenticar
```

---

### A4 — Agente IA con acceso completo a Google Workspace sin confirmación humana

**Severidad:** `ALTO`  
**Afecta:** DGX Spark (§13.2, §13.5)

El skill `gog` otorga al agente permisos de lectura, escritura, envío y eliminación sobre Gmail, Calendar, Drive, Docs, Sheets y Contacts. Un prompt injection en cualquier email o documento procesado puede convertirse en exfiltración o envío de emails maliciosos.

#### Cómo arreglarlo

**Paso 1 —** Reducir los scopes de OAuth al mínimo necesario en la consola de Google Cloud (`APIs y servicios → Pantalla de consentimiento OAuth`).

**Paso 2 —** Buscar en la documentación de OpenClaw la opción de confirmación humana antes de acciones destructivas (`human-in-the-loop` o `confirm before action`).

**Paso 3 — Usar una cuenta de Google separada y exclusiva para el agente:**

```bash
# Crear una cuenta dedicada (ej. agente.ia@gmail.com)
# Solo compartir los documentos/calendarios específicos necesarios
# Nunca dar acceso a la cuenta personal principal

# Revisar accesos periódicamente en:
# https://myaccount.google.com/permissions
```

---

### A5 — Usuario en el grupo docker (equivale a root sin contraseña)

**Severidad:** `ALTO`  
**Afecta:** DGX Spark (§5.3)

Pertenecer al grupo `docker` permite montar el sistema de archivos raíz del host dentro de un contenedor y obtener acceso completo de escritura, incluyendo `/etc/shadow`. Es una escalada de privilegios trivial y conocida.

#### Cómo arreglarlo

**Opción recomendada — Configurar Docker en modo rootless:**

```bash
# Instalar dependencias
sudo apt install -y uidmap dbus-user-session

# Salir del grupo docker
sudo gpasswd -d $USER docker

# Configurar Docker rootless
dockerd-rootless-setuptool.sh install

# Activar en la sesión actual
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock

# Añadir al .bashrc para persistencia
echo 'export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock' >> ~/.bashrc
```

---

### A6 — Symlink global de `gog` controlable por el usuario

**Severidad:** `ALTO`  
**Afecta:** DGX Spark (§13.3)

`sudo ln -s /home/$(whoami)/.local/bin/gog /usr/local/bin/gog` crea un symlink global que apunta a un binario controlado por el usuario. Si ese binario es reemplazado, cualquier usuario del sistema que ejecute `gog` ejecutará el binario modificado.

#### Cómo arreglarlo

```bash
# Eliminar el symlink existente
sudo rm /usr/local/bin/gog

# Copiar el binario real (no un symlink)
sudo cp ~/.local/bin/gog /usr/local/bin/gog
sudo chown root:root /usr/local/bin/gog
sudo chmod 755 /usr/local/bin/gog

# Verificar que no es un symlink
ls -la /usr/local/bin/gog
# → -rwxr-xr-x root root ...  ✅
```

> Al actualizar `gog` en el futuro, repetir el proceso de copia en lugar de actualizar solo `~/.local/bin/`.

---

## Hallazgos de Nivel Medio

> 🔵 Abordar estos puntos para mejorar la postura de seguridad general del sistema.

---

### M1 — Open WebUI usando imagen `:main` (tag mutable)

**Severidad:** `MEDIO`  
**Afecta:** DGX Spark (§10) · UM890 PRO (§22)

El tag `main` cambia con cada commit y puede introducir vulnerabilidades de seguridad sin aviso ni control de versión.

#### Cómo arreglarlo

```bash
# Ver la última versión estable en:
# https://github.com/open-webui/open-webui/releases

docker stop open-webui && docker rm open-webui

docker run -d \
  --name open-webui \
  -p 127.0.0.1:3000:8080 \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:v0.5.20
```

---

### M2 — Bot de Telegram accesible a cualquier usuario antes del pairing

**Severidad:** `MEDIO`  
**Afecta:** DGX Spark (§9.3) · UM890 PRO (§21.1)

Hasta completar el emparejamiento, el bot responde a cualquier mensaje revelando el Telegram user ID y el código de pairing. Si `ownerAllowFrom` no está configurado, otros usuarios pueden interactuar con el agente.

#### Cómo arreglarlo

**Paso 1 —** Completar el pairing inmediatamente tras crear el bot.

**Paso 2 — Verificar `ownerAllowFrom` en el JSON:**

```json
"commands": {
  "ownerAllowFrom": ["telegram:<TELEGRAM_USER_ID>"]
}
```

> Tu ID numérico se obtiene escribiendo a `@userinfobot` en Telegram.

**Paso 3 — Activar privacy mode en @BotFather:**

```
/mybots → Selecciona tu bot → Bot Settings → Group Privacy → Enable
```

---

### M3 — Memoria del agente en texto plano sin cifrado de disco

**Severidad:** `MEDIO`  
**Afecta:** DGX Spark · UM890 PRO (§24.1)

`~/.memoria/memory.md` se configura con `chmod 600` (correcto), pero sin cifrado de disco es accesible mediante arranque desde USB.

#### Cómo arreglarlo

**Opción 1 — Cifrar el directorio de memoria con gocryptfs:**

```bash
sudo apt install -y gocryptfs

# Crear el vault cifrado
mkdir -p ~/.memoria-vault
gocryptfs -init ~/.memoria-vault

# Montar en ~/.memoria
mkdir -p ~/.memoria
gocryptfs ~/.memoria-vault ~/.memoria

# Desmontar al cerrar sesión
fusermount -u ~/.memoria
```

**Opción 2 —** En la siguiente instalación del sistema, habilitar cifrado de disco completo LUKS. Ubuntu 26.04 lo ofrece durante el proceso de instalación.

---

### M4 — Instalación de OpenClaw desde npm sin verificación adicional

**Severidad:** `MEDIO`  
**Afecta:** DGX Spark (§8.3) · UM890 PRO (§20.1)

El ecosistema npm ha tenido múltiples incidentes de supply chain. OpenClaw tiene acceso al filesystem y a servicios externos, por lo que una versión comprometida sería especialmente dañina.

#### Cómo arreglarlo

```bash
# Ver información del paquete antes de instalar
npm info openclaw

# Descargar sin instalar para inspección
npm pack openclaw
tar -tzf openclaw-*.tgz | head -30

# Instalar y auditar inmediatamente
sudo npm install -g openclaw@latest
npm audit

# Verificar el mantenedor del paquete en:
# https://www.npmjs.com/package/openclaw
```

---

### M5 — Acceso del UM890 al DGX sin Tailscale ACLs configuradas

**Severidad:** `MEDIO`  
**Afecta:** UM890 PRO (§23)

Cualquier dispositivo que se una a la tailnet tiene acceso al servidor de inferencia del DGX en el puerto `11434`.

#### Cómo arreglarlo

Configurar Tailscale ACLs desde el panel de administración en `https://login.tailscale.com/admin/acls`:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["<UM890_TAILSCALE_IP>"],
      "dst": ["<DGX_TAILSCALE_IP>:11434"]
    },
    {
      "action": "accept",
      "src": ["autogroup:member"],
      "dst": ["autogroup:member:22"]
    }
  ]
}
```

> Sustituir `<UM890_TAILSCALE_IP>` por la IP Tailscale real del UM890 (obtenida con `tailscale ip`).

---

## Hallazgos Informativos

> ℹ️ Mejoras recomendadas que reducen la superficie de ataque sin ser urgentes.

---

### I1 — App de Google Cloud en modo Externo publicada

**Severidad:** `INFO`  
**Afecta:** DGX Spark (§13.2)

La guía indica publicar la app OAuth como "Externo" para evitar expiración de tokens. Esto permite que cualquier cuenta de Google inicie el flujo OAuth si obtiene la URL del cliente.

#### Alternativa recomendada

Para uso personal, mantener la app en modo **Testing** y añadir la cuenta como usuario de prueba. Los tokens no expiran y la app no es pública:

```
En Google Cloud Console:
APIs y servicios → Pantalla de consentimiento OAuth
→ Cambiar estado de publicación a "Testing"
→ Añadir tu correo en "Usuarios de prueba"
```

> Los tokens en modo Testing **no expiran** a los 7 días. El límite de 7 días solo aplica a apps no verificadas en modo Producción.

---

### I2 — `loginctl enable-linger`: agente activo sin sesión

**Severidad:** `INFO`  
**Afecta:** UM890 PRO (§20.3)

`enable-linger` hace que `openclaw-gateway` se ejecute 24/7 sin que el usuario esté logueado. Si la cuenta es comprometida, el agente estará activo continuamente sin que nadie lo note.

#### Buenas prácticas

```bash
# Ver logs en tiempo real
journalctl --user -fu openclaw-gateway

# Ver actividad de las últimas 24 horas
journalctl --user -u openclaw-gateway --since '24 hours ago'

# Buscar actividad sospechosa
journalctl --user -u openclaw-gateway --since '24 hours ago' \
  | grep -i 'request\|tool\|exec'
```

---

### I3 — `OLLAMA_DEBUG=INFO` puede exponer fragmentos de prompts en logs

**Severidad:** `INFO`  
**Afecta:** UM890 PRO (§19.2)

El nivel `INFO` puede incluir fragmentos de prompts y respuestas en los logs de journalctl, accesibles a usuarios del grupo `systemd-journal`.

#### Cómo ajustar

```bash
sudo nano /etc/systemd/system/ollama.service.d/override.conf

# Cambiar:
Environment="OLLAMA_DEBUG=INFO"
# Por:
Environment="OLLAMA_DEBUG=WARNING"

sudo systemctl daemon-reload && sudo systemctl restart ollama

# Verificar qué usuarios tienen acceso a los logs:
getent group systemd-journal
```

---

### I4 — IP de Tailscale del DGX hardcodeada en múltiples archivos

**Severidad:** `INFO`  
**Afecta:** UM890 PRO (§23.3, §27)

La IP `<DGX_TAILSCALE_IP>` aparece en `config.yaml` de Continue.dev, scripts de verificación y otros archivos. Si el DGX cambia de IP en la tailnet, todas las referencias quedan rotas.

#### Cómo mejorar

Usar el hostname de MagicDNS en todos los archivos de configuración:

```bash
# En ~/.continue/config.yaml:
apiBase: http://spark-be9d:11434    # en lugar de http://<DGX_TAILSCALE_IP>:11434

# En el .credentials del UM890:
DGX_OLLAMA_URL=http://spark-be9d:11434

# Verificar que MagicDNS está activo:
tailscale status
ping spark-be9d    # debe resolver correctamente ✅
```

---

## Checklist de Verificación Final

Una vez completadas las remediaciones, verificar cada punto:

### Críticos
- [ ] Ollama escucha solo en `127.0.0.1` (o detrás de proxy con autenticación)
- [ ] OpenClaw gateway: flags `dangerously*` eliminados y `bind` en `loopback`
- [ ] Open WebUI: puerto vinculado a `127.0.0.1` y cuenta admin creada inmediatamente
- [ ] Scripts de instalación verificados con SHA256 antes de ejecutar

### Altos
- [ ] Secure Boot activo con MOK, o LUKS habilitado como compensación
- [ ] Token de Telegram en variable de entorno, no en JSON plano
- [ ] `client_secret.json` con `chmod 600`, idealmente eliminado tras la autenticación
- [ ] Scopes de Google reducidos al mínimo necesario
- [ ] Docker en modo rootless, o usuario fuera del grupo `docker`
- [ ] Binario de `gog` copiado a `/usr/local/bin` (no symlink)

### Medios
- [ ] Open WebUI fijado a una versión semántica específica (no `:main`)
- [ ] Bot de Telegram con `ownerAllowFrom` configurado y privacy mode activo
- [ ] `~/.memoria` cifrado con gocryptfs, o disco con LUKS
- [ ] Paquete `openclaw` auditado con `npm audit`
- [ ] Tailscale ACLs configuradas para limitar acceso al puerto `11434`

### Informativos
- [ ] App Google Cloud en modo Testing (no Externo/Producción)
- [ ] Logs de `openclaw-gateway` monitorizados regularmente
- [ ] `OLLAMA_DEBUG=WARNING` en producción
- [ ] Hostnames MagicDNS usados en lugar de IPs hardcodeadas

---

*Análisis realizado en mayo de 2026 sobre la guía unificada DGX Spark + UM890 PRO.*  
*DGX OS 7.4 · Ubuntu 26.04 LTS · Ollama 0.23+ · OpenClaw 2026.x · Tailscale · ROCm · Vulkan RADV PHOENIX*

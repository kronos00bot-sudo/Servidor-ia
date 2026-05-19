# Plan Maestro de Remediación de Seguridad
## DGX Spark + UM890 PRO | Mayo 2026

> **Objetivo**: Eliminar 19 vulnerabilidades (4 críticas, 6 altas, 5 medias, 4 informativas) en el stack distribuido de IA local.
>
> **Duración estimada**: 5–7 días · **Riesgo inicial**: CRÍTICO

---

## Índice

- [Fase 0 — Preparación](#fase-0--preparación)
- [Fase 1 — Críticos](#fase-1--críticos)
  - [C1 — Ollama sin autenticación](#c1--ollama-sin-autenticación)
  - [C2 — OpenClaw con auth deshabilitada](#c2--openclaw-con-auth-deshabilitada)
  - [C3 — Instalación curl | sh sin verificación](#c3--instalación-curl--sh-sin-verificación)
  - [C4 — Open WebUI expuesto en red](#c4--open-webui-expuesto-en-red)
- [Fase 2 — Altos](#fase-2--altos)
  - [A1 — Secure Boot deshabilitado](#a1--secure-boot-deshabilitado)
  - [A2 — Token Telegram en texto plano](#a2--token-telegram-en-texto-plano)
  - [A3 — Credenciales Google OAuth sin protección](#a3--credenciales-google-oauth-sin-protección)
  - [A4 — Agente IA con acceso completo sin confirmación](#a4--agente-ia-con-acceso-completo-sin-confirmación)
  - [A5 — Usuario en grupo docker](#a5--usuario-en-grupo-docker)
  - [A6 — Symlink global de gog](#a6--symlink-global-de-gog)
- [Fase 3 — Medios](#fase-3--medios)
  - [M1 — Open WebUI con tag :main](#m1--open-webui-con-tag-main)
  - [M2 — Bot Telegram antes del pairing](#m2--bot-telegram-antes-del-pairing)
  - [M3 — Memoria del agente en texto plano](#m3--memoria-del-agente-en-texto-plano)
  - [M4 — OpenClaw desde npm sin verificación](#m4--openclaw-desde-npm-sin-verificación)
  - [M5 — Sin Tailscale ACLs](#m5--sin-tailscale-acls)
- [Fase 4 — Informativos](#fase-4--informativos)
  - [I1 — App Google Cloud en modo Externo](#i1--app-google-cloud-en-modo-externo)
  - [I2 — Monitoreo de openclaw-gateway](#i2--monitoreo-de-openclaw-gateway)
  - [I3 — OLLAMA_DEBUG en producción](#i3--ollama_debug-en-producción)
  - [I4 — IPs hardcodeadas](#i4--ips-hardcodeadas)
- [Checklist Final](#checklist-final)
- [Timeline](#timeline)
- [Troubleshooting](#troubleshooting)

---

## Fase 0 — Preparación

> ⏱ Hacer **antes** de cualquier cambio. ~30 minutos.

### P1: Auditoría inicial

```bash
# Puertos abiertos en DGX y UM890 (ejecutar en ambas)
netstat -tlnp | grep -E '3000|11434|18789'

# Grupos críticos
getent group docker
getent group systemd-journal
```

### P2: Backup de configuraciones

```bash
DIR=~/backup-seguridad-$(date +%Y%m%d)
mkdir -p "$DIR"
cp -r ~/.openclaw "$DIR/"
cp -r ~/.config/gog "$DIR/" 2>/dev/null || true
cp ~/.credentials "$DIR/" 2>/dev/null || true
echo "Backup guardado en $DIR"
```

### P3: Verificar servicios activos

```bash
# DGX
systemctl --user status openclaw-gateway
systemctl status ollama

# UM890
docker ps
tailscale status
```

### P4: Anotar IPs Tailscale

```bash
# DGX
tailscale ip -4    # → ej: 100.64.129.87

# UM890
tailscale ip -4    # → ej: 100.64.X.Y
```

---

## Fase 1 — Críticos

> ⛔ Resolver **antes** de conectar a cualquier red externa.

---

### C1 — Ollama sin Autenticación

**Severidad**: `CRÍTICO` | **Máquina**: DGX + UM890 | **Puerto**: 11434

**Riesgo**: Cualquier dispositivo en la red puede ejecutar modelos, listarlos y subir modelos propios sin credenciales.

#### Paso 1 — Restringir Ollama a localhost

```bash
# En DGX y UM890
sudo nano /etc/systemd/system/ollama.service.d/override.conf

# Cambiar:
#   Environment="OLLAMA_HOST=0.0.0.0"
# A:
#   Environment="OLLAMA_HOST=127.0.0.1"

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

#### Paso 2 — Instalar proxy Caddy con autenticación (DGX)

```bash
sudo apt install -y caddy

# Generar hash de contraseña
HASH=$(caddy hash-password -plaintext "tu_contraseña_segura")

# Crear Caddyfile
sudo tee /etc/caddy/Caddyfile > /dev/null <<EOF
:11435 {
  basicauth {
    mloco $HASH
  }
  reverse_proxy 127.0.0.1:11434
}
EOF

sudo systemctl enable --now caddy
```

#### Paso 3 — Actualizar referencias en UM890

```bash
# En ~/.continue/config.yaml
# Cambiar:  apiBase: http://100.64.129.87:11434
# A:        apiBase: http://100.64.129.87:11435
# (con autenticación configurada en el cliente)
```

#### Verificación

```bash
# Debe rechazar sin credenciales
curl http://localhost:11435/api/tags
# → 401 Unauthorized ✅

# Debe funcionar con credenciales
curl -u mloco:tu_contraseña_segura http://localhost:11435/api/tags
# → {"models": [...]} ✅

# Ollama no debe escuchar en 0.0.0.0
netstat -tlnp | grep 11434
# → 127.0.0.1:11434 ✅
```

- [ ] Ollama escucha solo en `127.0.0.1:11434`
- [ ] Caddy proxy corriendo en `:11435` con auth básica
- [ ] Acceso remoto al puerto 11434 rechazado

---

### C2 — OpenClaw con Auth Deshabilitada

**Severidad**: `CRÍTICO` | **Máquina**: UM890 | **Puerto**: 18789

**Riesgo**: Control completo del agente IA sin credenciales desde la red local.

#### Paso 1 — Backup y edición de openclaw.json

```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.backup-$(date +%s)
nano ~/.openclaw/openclaw.json
```

**Cambiar en el bloque `controlUi`:**

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

**Cambiar en el bloque `gateway`:**

```json
"gateway": {
  "bind": "loopback"
}
```

#### Paso 2 — Reiniciar el servicio

```bash
systemctl --user restart openclaw-gateway
sleep 3
systemctl --user status openclaw-gateway
```

#### Paso 3 — Acceso remoto desde otro dispositivo (si necesario)

```bash
# Usar túnel SSH en lugar de exposición directa
ssh -L 18789:127.0.0.1:18789 mloco@IP_UM890
# Luego abrir: http://localhost:18789
```

#### Verificación

```bash
jq .controlUi.allowInsecureAuth ~/.openclaw/openclaw.json
# → false ✅

jq .gateway.bind ~/.openclaw/openclaw.json
# → "loopback" ✅
```

- [ ] `allowInsecureAuth` = false
- [ ] `dangerouslyDisableDeviceAuth` = false
- [ ] `dangerouslyAllowHostHeaderOriginFallback` = false
- [ ] `bind` = "loopback"
- [ ] Servicio reiniciado sin errores

---

### C3 — Instalación curl | sh sin Verificación

**Severidad**: `CRÍTICO` | **Máquina**: DGX + UM890

**Riesgo**: MITM, CDN comprometido o DNS envenenado permite ejecución de código arbitrario con privilegios root.

#### Ollama — Descargar y verificar antes de ejecutar

```bash
curl -fsSL https://ollama.com/install.sh -o /tmp/ollama-install.sh

# Comparar el hash con el publicado en ollama.com/download
sha256sum /tmp/ollama-install.sh

# SOLO si el hash coincide:
bash /tmp/ollama-install.sh
```

#### Tailscale — Instalar desde APT con GPG verificado

```bash
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg \
  -o /tmp/ts.gpg

# Verificar fingerprint en tailscale.com/download
gpg --show-keys /tmp/ts.gpg

sudo mv /tmp/ts.gpg /usr/share/keyrings/tailscale-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] \
  https://pkgs.tailscale.com/stable/ubuntu noble main" | \
  sudo tee /etc/apt/sources.list.d/tailscale.list

sudo apt update && sudo apt install -y tailscale
```

#### Node.js — Usar repositorio oficial con GPG

```bash
# Alternativa: usar nvm en lugar de curl | sh directo
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh \
  -o /tmp/nvm-install.sh

# Inspeccionar el script antes de ejecutar
less /tmp/nvm-install.sh

# Si parece correcto:
bash /tmp/nvm-install.sh
```

#### Verificación

- [ ] Ollama descargado y hash verificado antes de ejecutar
- [ ] Tailscale instalado desde APT con clave GPG
- [ ] Node.js instalado con script inspeccionado manualmente

---

### C4 — Open WebUI Expuesto en Red

**Severidad**: `CRÍTICO` | **Máquina**: DGX + UM890 | **Puerto**: 3000

**Riesgo**: `--network=host` elimina aislamiento de red. El primer visitante puede crear la cuenta de administrador.

#### Paso 1 — Detener contenedor actual

```bash
docker stop open-webui
docker rm open-webui
```

#### Paso 2 — Relanzar con puerto vinculado a localhost y versión fija

```bash
# Ver última versión estable en:
# https://github.com/open-webui/open-webui/releases

docker run -d \
  --name open-webui \
  -p 127.0.0.1:3000:8080 \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:v0.5.20
```

#### Paso 3 — Crear cuenta admin inmediatamente

```bash
# Esperar que inicie
sleep 15

# Abrir en navegador local y registrar el primer usuario (será admin)
xdg-open http://localhost:3000
```

#### Verificación

```bash
docker port open-webui
# → 8080/tcp → 127.0.0.1:3000 ✅

docker inspect open-webui | grep -i '"Image"'
# → ghcr.io/open-webui/open-webui:v0.5.20 ✅ (no :main)
```

- [ ] Puerto vinculado a `127.0.0.1:3000` (no 0.0.0.0)
- [ ] Imagen con versión semántica fija (no `:main`)
- [ ] Cuenta admin creada inmediatamente tras el despliegue
- [ ] Acceso remoto al puerto 3000 rechazado

---

## Fase 2 — Altos

> ⚠️ Resolver antes de añadir usuarios adicionales o exponer a internet.

---

### A1 — Secure Boot Deshabilitado

**Severidad**: `ALTO` | **Máquina**: UM890 PRO

**Riesgo**: Sin Secure Boot, un bootkit puede instalarse antes del SO y ser invisible al sistema operativo.

#### Opción A — Reactivar Secure Boot con MOK

```bash
# Generar clave MOK
sudo openssl req -new -x509 -newkey rsa:2048 \
  -keyout /root/mok.key \
  -out /root/mok.crt \
  -days 3650 \
  -subj '/CN=MOK signing key/' \
  -nodes

# Registrar la clave
sudo mokutil --import /root/mok.crt

# Reiniciar y aceptar en el menú azul (MokManager)
sudo reboot

# Verificar tras reinicio
sudo mokutil --list-enrolled
bootctl status | grep -i secure
```

#### Opción B — Cifrado LUKS en próxima instalación

Si Secure Boot no puede reactivarse, habilitar LUKS completo en la próxima instalación de Ubuntu. Ubuntu 26.04 lo ofrece en el instalador.

#### Verificación

```bash
bootctl status | grep "Secure Boot"
# → Secure Boot: enabled ✅
```

- [ ] Secure Boot activo **O** LUKS configurado como compensación

---

### A2 — Token Telegram en Texto Plano

**Severidad**: `ALTO` | **Máquina**: DGX + UM890

**Riesgo**: Cualquier proceso con acceso al home puede leer y exfiltrar el token del bot.

#### Paso 1 — Crear archivo de credenciales protegido

```bash
touch ~/.credentials
chmod 600 ~/.credentials

# Añadir el token (obtener desde @BotFather en Telegram)
echo 'OPENCLAW_TELEGRAM_BOT_TOKEN=tu_token_aqui' >> ~/.credentials
```

#### Paso 2 — Reemplazar token en openclaw.json por variable

```bash
nano ~/.openclaw/openclaw.json
# Cambiar:  "botToken": "123456:ABCdef..."
# A:        "botToken": "${OPENCLAW_TELEGRAM_BOT_TOKEN}"
```

#### Paso 3 — Inyectar variable desde systemd

```bash
nano ~/.config/systemd/user/openclaw-gateway.service
# Añadir bajo [Service]:
# EnvironmentFile=%h/.credentials
```

#### Paso 4 — Asegurar permisos

```bash
chmod 700 ~/.openclaw
chmod 600 ~/.openclaw/openclaw.json
chmod 600 ~/.credentials
```

#### Paso 5 — Reiniciar y verificar

```bash
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway
systemctl --user status openclaw-gateway
```

#### Verificación

```bash
grep "botToken" ~/.openclaw/openclaw.json
# → "botToken": "${OPENCLAW_TELEGRAM_BOT_TOKEN}" ✅ (no el token real)

ls -la ~/.credentials
# → -rw------- mloco mloco ✅
```

- [ ] Token NO visible en JSON
- [ ] `~/.credentials` con permisos 600
- [ ] `~/.openclaw/` con permisos 700
- [ ] Servicio reiniciado correctamente

---

### A3 — Credenciales Google OAuth sin Protección

**Severidad**: `ALTO` | **Máquina**: DGX

**Riesgo**: `client_secret.json` en el home otorga acceso OAuth a Gmail, Drive, Calendar, Contacts y Sheets.

#### Paso 1 — Mover a directorio protegido

```bash
mkdir -p ~/.config/gog
chmod 700 ~/.config/gog

mv ~/client_secret.json ~/.config/gog/client_secret.json
chmod 600 ~/.config/gog/client_secret.json

# Verificar
ls -la ~/.config/gog/client_secret.json
# → -rw------- mloco mloco ✅
```

#### Paso 2 — Re-autenticar con la nueva ruta

```bash
gog auth credentials ~/.config/gog/client_secret.json
# Seguir el flujo en el navegador
```

#### Paso 3 — Verificar tokens guardados

```bash
gog auth list --check
# → tu.correo@gmail.com  ✓ ✅
```

#### Paso 4 — Eliminar client_secret.json

```bash
# SOLO si los tokens están en verde ✓
rm ~/.config/gog/client_secret.json

# Guardar una copia offline segura (USB cifrada)
# NO mantener copia en disco local sin cifrar
```

#### Verificación

```bash
ls ~/client_secret.json 2>&1
# → No existe ✅

gog auth list --check
# → ✓ ✅
```

- [ ] `client_secret.json` eliminado del home y del directorio `~/.config/gog`
- [ ] Tokens de autenticación presentes y válidos
- [ ] Copia offline guardada en lugar seguro

---

### A4 — Agente IA con Acceso Completo sin Confirmación

**Severidad**: `ALTO` | **Máquina**: DGX

**Riesgo**: Prompt injection en cualquier email o documento puede provocar envío de correos maliciosos, borrado de archivos o exfiltración de datos.

#### Paso 1 — Reducir scopes OAuth en Google Cloud

```
1. Ir a: https://console.cloud.google.com/apis/credentials
2. APIs y servicios → Pantalla de consentimiento OAuth → Editar app
3. Sección "Permisos (Scopes)"
4. Quitar scopes de escritura
5. Mantener SOLO scopes readonly:
   - .../auth/gmail.readonly
   - .../auth/calendar.readonly
   - .../auth/drive.readonly
```

#### Paso 2 — Crear cuenta de Google separada para el agente

```bash
# Crear: agente-ia@gmail.com (cuenta dedicada, sin datos personales)
# Características obligatorias:
# - Contraseña larga y única
# - 2FA habilitado
# - No vinculada a cuenta personal

# En Google Cloud: reasignar OAuth a esta cuenta
# Solo compartir documentos/calendarios específicos necesarios
```

#### Paso 3 — Verificar accesos periódicamente

```
Revisar mensualmente: https://myaccount.google.com/permissions
```

#### Verificación

- [ ] Scopes reducidos a readonly en Google Cloud Console
- [ ] Cuenta separada creada y vinculada a OpenClaw
- [ ] 2FA habilitado en cuenta del agente

---

### A5 — Usuario en Grupo Docker

**Severidad**: `ALTO` | **Máquina**: DGX

**Riesgo**: El grupo `docker` es equivalente a root. Permite montar `/etc/shadow` y escalar privilegios trivialmente.

#### Paso 1 — Verificar pertenencia actual

```bash
id mloco | grep docker
getent group docker
```

#### Paso 2 — Instalar dependencias para modo rootless

```bash
sudo apt install -y uidmap dbus-user-session
```

#### Paso 3 — Salir del grupo docker

```bash
sudo gpasswd -d mloco docker
```

#### Paso 4 — Configurar Docker rootless

```bash
dockerd-rootless-setuptool.sh install

# Añadir al ~/.bashrc
echo 'export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock' >> ~/.bashrc
source ~/.bashrc
```

#### Paso 5 — Verificar (después de logout/login)

```bash
# Logout y login
# Luego:
docker ps
# → funciona sin sudo ✅

# Verificar que no hay acceso a archivos del host
docker run --rm -v /etc:/mnt alpine cat /mnt/shadow 2>&1
# → Permission denied ✅
```

#### Verificación

```bash
id mloco | grep docker
# → no debe aparecer "docker" ✅
```

- [ ] Usuario fuera del grupo `docker`
- [ ] Docker rootless funciona sin sudo
- [ ] Acceso a `/etc/shadow` desde contenedor denegado

---

### A6 — Symlink Global de `gog`

**Severidad**: `ALTO` | **Máquina**: DGX

**Riesgo**: Si el binario en `~/.local/bin/gog` es reemplazado, cualquier usuario que ejecute `gog` ejecutará código malicioso.

#### Paso 1 — Verificar estado actual

```bash
ls -la /usr/local/bin/gog
# Si muestra "→" es un symlink ⚠️
```

#### Paso 2 — Reemplazar symlink por binario real

```bash
sudo rm /usr/local/bin/gog
sudo cp ~/.local/bin/gog /usr/local/bin/gog
sudo chown root:root /usr/local/bin/gog
sudo chmod 755 /usr/local/bin/gog
```

#### Paso 3 — Crear script de actualización

```bash
cat > ~/update-gog.sh <<'EOF'
#!/bin/bash
# Actualizar gog y copiar a /usr/local/bin
npm install -g gog
sudo cp ~/.local/bin/gog /usr/local/bin/gog
sudo chown root:root /usr/local/bin/gog
sudo chmod 755 /usr/local/bin/gog
echo "✅ gog actualizado"
EOF
chmod +x ~/update-gog.sh
```

#### Verificación

```bash
ls -la /usr/local/bin/gog
# → -rwxr-xr-x root root ... (sin "→") ✅

file /usr/local/bin/gog
# → ELF 64-bit LSB executable ✅
```

- [ ] `/usr/local/bin/gog` NO es un symlink
- [ ] Propietario root:root con permisos 755
- [ ] Script `~/update-gog.sh` creado para futuras actualizaciones

---

## Fase 3 — Medios

> 🔵 Abordar para mejorar la postura de seguridad general.

---

### M1 — Open WebUI con Tag `:main`

**Severidad**: `MEDIO` | **Máquina**: DGX + UM890

**Ya resuelto en C4** al fijar la imagen a `v0.5.20`. Solo verificar:

```bash
docker inspect open-webui | grep '"Image"'
# → ghcr.io/open-webui/open-webui:v0.5.20 ✅
```

- [ ] Imagen con versión semántica fija (confirmado en C4)

---

### M2 — Bot Telegram Antes del Pairing

**Severidad**: `MEDIO` | **Máquina**: UM890

**Riesgo**: Hasta completar el pairing, el bot responde a cualquier usuario revelando información del sistema.

#### Paso 1 — Obtener tu ID de Telegram

```
En Telegram, escribir a @userinfobot
Te dará tu User ID numérico (ej: 987654321)
```

#### Paso 2 — Configurar ownerAllowFrom en openclaw.json

```bash
nano ~/.openclaw/openclaw.json
```

```json
"commands": {
  "ownerAllowFrom": ["telegram:987654321"],
  "enabled": true
}
```

#### Paso 3 — Activar Privacy Mode en BotFather

```
En Telegram, escribir a @BotFather:
/mybots
→ Seleccionar tu bot
→ Bot Settings
→ Group Privacy
→ Enable (Turn on)
```

#### Paso 4 — Completar el pairing inmediatamente

```bash
systemctl --user restart openclaw-gateway
# Abrir Telegram, escribir al bot: /start
# Seguir el flujo de pairing
```

#### Verificación

```bash
grep "ownerAllowFrom" ~/.openclaw/openclaw.json
# → "ownerAllowFrom": ["telegram:987654321"] ✅
```

- [ ] `ownerAllowFrom` configurado con ID numérico
- [ ] Privacy Mode activo en BotFather
- [ ] Pairing completado

---

### M3 — Memoria del Agente en Texto Plano

**Severidad**: `MEDIO` | **Máquina**: DGX + UM890

**Riesgo**: Sin cifrado de disco, `~/.memoria/memory.md` es accesible arrancando desde USB aunque tenga chmod 600.

#### Paso 1 — Instalar gocryptfs

```bash
sudo apt install -y gocryptfs
```

#### Paso 2 — Crear vault cifrado

```bash
mkdir -p ~/.memoria-vault
gocryptfs -init ~/.memoria-vault
# Ingresar contraseña (diferente a la del sistema)
```

#### Paso 3 — Montar y migrar datos

```bash
mkdir -p ~/.memoria-mount
gocryptfs ~/.memoria-vault ~/.memoria-mount

# Migrar archivos existentes
cp -r ~/.memoria/* ~/.memoria-mount/ 2>/dev/null || true

# Reemplazar el directorio plano por el mountpoint
fusermount -u ~/.memoria-mount
rmdir ~/.memoria-mount

# Montar directamente en ~/.memoria
fusermount -u ~/.memoria 2>/dev/null || true
gocryptfs ~/.memoria-vault ~/.memoria
```

#### Paso 4 — Automontaje al iniciar sesión

```bash
# Añadir a ~/.bashrc
echo 'gocryptfs ~/.memoria-vault ~/.memoria 2>/dev/null || true' >> ~/.bashrc
```

#### Verificación

```bash
mount | grep memoria
# → gocryptfs on /home/mloco/.memoria type fuse.gocryptfs ✅
```

- [ ] `~/.memoria-vault` inicializado con gocryptfs
- [ ] `~/.memoria` es un mountpoint cifrado
- [ ] Automontaje configurado en `~/.bashrc`

---

### M4 — OpenClaw desde npm sin Verificación

**Severidad**: `MEDIO` | **Máquina**: DGX + UM890

**Riesgo**: Incidente de supply chain en el ecosistema npm podría comprometer el agente IA con acceso al filesystem y servicios externos.

#### Paso 1 — Auditar paquete actual

```bash
npm list -g openclaw

# Ver información del mantenedor
npm info openclaw | head -40

# Verificar en: https://www.npmjs.com/package/openclaw
```

#### Paso 2 — Ejecutar auditoría de seguridad

```bash
npm audit

# Si hay vulnerabilidades HIGH o CRITICAL:
npm audit fix
```

#### Paso 3 — Crear script de auditoría periódica

```bash
cat > ~/check-npm.sh <<'EOF'
#!/bin/bash
echo "=== Auditoría npm $(date) ==="
npm audit
echo ""
echo "=== Info openclaw ==="
npm info openclaw | grep -E "name|version|license|author"
echo ""
echo "Verificar mantenedor en: https://www.npmjs.com/package/openclaw"
EOF

chmod +x ~/check-npm.sh
```

#### Verificación

```bash
npm audit 2>&1 | grep -E "found [0-9]+"
# → found 0 vulnerabilities ✅
```

- [ ] `npm audit` ejecutado sin HIGH/CRITICAL
- [ ] Mantenedor del paquete verificado en npmjs.com
- [ ] Script de auditoría periódica creado

---

### M5 — Sin Tailscale ACLs

**Severidad**: `MEDIO` | **Máquina**: Tailscale Admin Console

**Riesgo**: Cualquier dispositivo que se una a la tailnet tiene acceso sin restricciones al servidor de inferencia del DGX.

#### Paso 1 — Obtener IPs Tailscale actuales

```bash
# DGX
tailscale ip -4    # Anotar → ej: 100.64.129.87

# UM890
tailscale ip -4    # Anotar → ej: 100.64.X.Y
```

#### Paso 2 — Configurar ACLs en panel de Tailscale

```
1. Ir a: https://login.tailscale.com/admin/acls
2. Reemplazar contenido con:
```

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["100.64.X.Y"],
      "dst": ["100.64.129.87:11434", "100.64.129.87:11435"]
    },
    {
      "action": "accept",
      "src": ["100.64.X.Y"],
      "dst": ["100.64.129.87:22"]
    },
    {
      "action": "accept",
      "src": ["autogroup:member"],
      "dst": ["autogroup:member:22"]
    }
  ]
}
```

> Sustituir `100.64.X.Y` por la IP Tailscale real del UM890.

#### Paso 3 — Verificar

```bash
# En UM890 (debe funcionar)
curl http://100.64.129.87:11435/api/tags -u mloco:pass
# → {"models": [...]} ✅

# En DGX (acceso a UM890 que no sea SSH debe fallar)
curl http://100.64.X.Y:18789 2>&1 | grep -i refused
# → Connection refused ✅
```

- [ ] ACLs configuradas en consola Tailscale
- [ ] UM890 accede a puertos 11434/11435 en DGX
- [ ] Otros dispositivos de la tailnet bloqueados

---

## Fase 4 — Informativos

> ℹ️ Mejoras que reducen superficie de ataque sin ser urgentes.

---

### I1 — App Google Cloud en Modo Externo

**Severidad**: `INFO` | **Máquina**: Google Cloud Console

**Riesgo**: App OAuth pública permite que cualquier cuenta de Google inicie el flujo de autorización.

#### Cambiar a modo Testing

```
1. Ir a: https://console.cloud.google.com/apis/credentials
2. APIs y servicios → Pantalla de consentimiento OAuth
3. Estado de publicación → "Testing"
4. Añadir correo en "Usuarios de prueba"
```

> Los tokens en modo Testing **no expiran**. El límite de 7 días solo aplica a apps no verificadas en modo Producción.

#### Verificación

```bash
gog auth list --check
# → ✓ (tokens válidos) ✅
```

- [ ] App en modo Testing
- [ ] Correo añadido como usuario de prueba

---

### I2 — Monitoreo de openclaw-gateway

**Severidad**: `INFO` | **Máquina**: UM890

**Riesgo**: Agente activo 24/7 sin visibilidad → actividad maliciosa puede pasar desapercibida.

#### Paso 1 — Revisar logs

```bash
# Último día
journalctl --user -u openclaw-gateway --since '1 day ago' --no-pager

# Buscar errores
journalctl --user -u openclaw-gateway --since '7 days ago' | grep -i error

# Buscar acciones ejecutadas
journalctl --user -u openclaw-gateway --since '24 hours ago' | \
  grep -i 'request\|tool\|exec'
```

#### Paso 2 — Crear script de alertas

```bash
cat > ~/monitor-openclaw.sh <<'EOF'
#!/bin/bash
echo "=== Monitor OpenClaw $(date) ==="

PATTERNS=("exec_shell" "write.*file" "DELETE.*request" "error.*auth")

for pattern in "${PATTERNS[@]}"; do
  COUNT=$(journalctl --user -u openclaw-gateway --since '1 hour ago' | \
    grep -ic "$pattern" 2>/dev/null || echo 0)

  if [ "$COUNT" -gt 0 ]; then
    echo "⚠️  ALERTA: '$pattern' detectado ($COUNT veces)"
    journalctl --user -u openclaw-gateway --since '1 hour ago' | \
      grep -i "$pattern" | tail -3
  fi
done

echo "=== Fin del reporte ==="
EOF

chmod +x ~/monitor-openclaw.sh
```

#### Verificación

```bash
loginctl user-status mloco | grep Linger
# → Linger: yes ✅

~/monitor-openclaw.sh
# → Sin alertas ✅
```

- [ ] Logs revisados sin actividad sospechosa
- [ ] Script de monitoreo creado en `~/monitor-openclaw.sh`

---

### I3 — OLLAMA_DEBUG en Producción

**Severidad**: `INFO` | **Máquina**: DGX + UM890

**Riesgo**: Nivel `INFO` puede incluir fragmentos de prompts en logs accesibles al grupo `systemd-journal`.

#### Cambiar nivel de debug

```bash
sudo nano /etc/systemd/system/ollama.service.d/override.conf

# Cambiar:
#   Environment="OLLAMA_DEBUG=INFO"
# A:
#   Environment="OLLAMA_DEBUG=WARNING"

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

#### Verificar acceso a logs

```bash
# Ver quién tiene acceso a journalctl
getent group systemd-journal
```

#### Verificación

```bash
sudo systemctl show ollama | grep OLLAMA_DEBUG
# → OLLAMA_DEBUG=WARNING ✅
```

- [ ] `OLLAMA_DEBUG=WARNING` en DGX
- [ ] `OLLAMA_DEBUG=WARNING` en UM890

---

### I4 — IPs Hardcodeadas

**Severidad**: `INFO` | **Máquina**: UM890

**Riesgo**: Si el DGX cambia de IP Tailscale, todas las configuraciones dejan de funcionar.

#### Paso 1 — Obtener hostname MagicDNS

```bash
# En DGX
tailscale status | grep $(hostname)
# → spark-be9d [100.64.129.87] ...
# Usar: spark-be9d
```

#### Paso 2 — Reemplazar IPs en archivos de configuración

```bash
# En UM890
OLD_IP="100.64.129.87"
NEW_HOST="spark-be9d"

# Continue.dev
sed -i "s/$OLD_IP/$NEW_HOST/g" ~/.continue/config.yaml

# Archivo de credenciales
sed -i "s/$OLD_IP/$NEW_HOST/g" ~/.credentials

# Scripts propios
find ~/scripts -name "*.sh" -exec sed -i "s/$OLD_IP/$NEW_HOST/g" {} \; 2>/dev/null
```

#### Paso 3 — Verificar resolución MagicDNS

```bash
ping -c 2 spark-be9d
# → Debe responder ✅

curl http://spark-be9d:11435/api/tags -u mloco:pass
# → {"models": [...]} ✅
```

#### Verificación

```bash
grep -r "100\.64\.129\.87" ~/.continue/ ~/.credentials 2>/dev/null
# → Sin resultados ✅
```

- [ ] Hostnames MagicDNS usados en lugar de IPs
- [ ] `ping spark-be9d` resuelve correctamente
- [ ] No quedan IPs hardcodeadas en configs

---

## Checklist Final

### 🔥 Críticos

- [ ] **C1** Ollama escucha solo en `127.0.0.1:11434`
- [ ] **C1** Caddy proxy en `:11435` con autenticación básica
- [ ] **C2** `allowInsecureAuth` = false en openclaw.json
- [ ] **C2** `bind` = "loopback" en openclaw.json
- [ ] **C3** Instaladores verificados con SHA256 / GPG antes de ejecutar
- [ ] **C4** Open WebUI: `-p 127.0.0.1:3000:8080` (sin `--network=host`)
- [ ] **C4** Open WebUI: versión fija `v0.5.20` (no `:main`)
- [ ] **C4** Cuenta admin creada inmediatamente

### 🟠 Altos

- [ ] **A1** Secure Boot activo con MOK, o LUKS habilitado
- [ ] **A2** Token Telegram en `~/.credentials` (no en JSON)
- [ ] **A2** `EnvironmentFile` configurado en el servicio systemd
- [ ] **A3** `client_secret.json` eliminado tras autenticación
- [ ] **A3** Permisos `chmod 700 ~/.config/gog`
- [ ] **A4** Scopes OAuth reducidos a readonly
- [ ] **A4** Cuenta de Google separada para el agente
- [ ] **A5** Docker rootless activado
- [ ] **A5** Usuario fuera del grupo `docker`
- [ ] **A6** `/usr/local/bin/gog` es binario (no symlink), propietario root

### 🟡 Medios

- [ ] **M1** Open WebUI con versión semántica fija (confirmado en C4)
- [ ] **M2** `ownerAllowFrom` con ID numérico de Telegram
- [ ] **M2** Privacy Mode activo en BotFather
- [ ] **M3** `~/.memoria` cifrado con gocryptfs
- [ ] **M4** `npm audit` sin HIGH/CRITICAL
- [ ] **M5** Tailscale ACLs configuradas

### 🔵 Informativos

- [ ] **I1** App Google Cloud en modo Testing
- [ ] **I2** Script `~/monitor-openclaw.sh` creado y probado
- [ ] **I3** `OLLAMA_DEBUG=WARNING` en ambas máquinas
- [ ] **I4** Hostnames MagicDNS en lugar de IPs en todas las configs

---

## Timeline

| Día | Fase | Tareas | Tiempo estimado |
|-----|------|--------|-----------------|
| 1 | P0 + C1 + C2 | Preparación + Bloquear Ollama + OpenClaw | 3–4h |
| 1–2 | C3 + C4 | Verificar instaladores + Open WebUI | 2–3h |
| 2–3 | A1–A3 | Secure Boot + Credenciales | 2–3h |
| 3–4 | A4–A6 | Google OAuth + Docker rootless + gog | 2–3h |
| 4–5 | M1–M5 | Ajustes medios + Tailscale ACLs | 2–3h |
| 5–7 | I1–I4 | Informativos + Monitoreo | 1–2h |

**Total**: 12–18 horas distribuidas en 5–7 días

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| OpenClaw no inicia tras editar JSON | Sintaxis JSON inválida | `jq . ~/.openclaw/openclaw.json` para validar |
| Ollama sigue en 0.0.0.0 tras cambio | Override no cargado | `sudo systemctl status ollama` → verificar el path del override |
| Caddy falla con "puerto en uso" | Proceso en el 11435 | `sudo lsof -i :11435` → matar conflicto |
| Docker rootless no funciona | Linger no activo | `sudo loginctl enable-linger mloco` + logout/login |
| Tailscale ACL bloquea acceso legítimo | IP incorrecta en ACL | `tailscale ip` → actualizar ACL con IP real |
| gocryptfs se desmonta al logout | No está en .bashrc | Añadir línea de montaje a `~/.bashrc` |
| `gog auth list` falla tras mover credenciales | Ruta no actualizada | `gog auth credentials ~/.config/gog/client_secret.json` |

---

## Referencias

- Guía de hallazgos original: [guia-remediacion-seguridad.md](guia-remediacion-seguridad.md)
- Releases Open WebUI: https://github.com/open-webui/open-webui/releases
- Docker Rootless: https://docs.docker.com/engine/security/rootless/
- Tailscale ACL Syntax: https://tailscale.com/kb/1337/acl-syntax/
- gocryptfs Docs: https://github.com/rfjakob/gocryptfs
- npm Audit: https://docs.npmjs.com/cli/v10/commands/npm-audit

---

*Plan creado: 19 de mayo de 2026*  
*Basado en: Guía de Remediación de Seguridad — DGX Spark + UM890 PRO*  
*Stack: DGX OS 7.4 · Ubuntu 26.04 LTS · Ollama 0.23+ · OpenClaw 2026.x · Tailscale · ROCm · Vulkan RADV PHOENIX*

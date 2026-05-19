# Guía Unificada: DGX Spark (Servidor) + UM890 PRO (Cliente)
## Stack completo de IA local con Ollama · OpenClaw · Telegram · Open WebUI

> **Arquitectura:** El DGX Spark actúa como servidor central de inferencia (modelos 120B + stack completo). El UM890 PRO actúa como cliente inteligente con su propio stack local (modelos 9–33B) que puede consumir los modelos del DGX remotamente cuando lo necesita.

---

## Índice

**PARTE I — DGX SPARK (Servidor)**
1. [Hardware y requisitos previos](#1-hardware-y-requisitos-previos)
2. [Primer encendido y configuración inicial](#2-primer-encendido-y-configuración-inicial-oobe)
3. [Acceso remoto con NVIDIA Sync](#3-acceso-remoto-con-nvidia-sync)
4. [Actualización del sistema](#4-actualización-del-sistema)
5. [Docker + NVIDIA Container Runtime](#5-configuración-de-docker--nvidia-container-runtime)
6. [Ollama en el DGX Spark](#6-ollama-en-el-dgx-spark)
7. [Modelos 120B](#7-descarga-de-los-modelos-120b)
8. [OpenClaw en el DGX Spark](#8-openclaw-en-el-dgx-spark)
9. [Bot de Telegram — DGX](#9-bot-de-telegram--dgx-spark)
10. [Open WebUI — DGX](#10-open-webui--dgx-spark)
11. [Exponer Ollama a la red](#11-exponer-ollama-a-la-red-local)
12. [Tailscale — acceso seguro desde cualquier red](#12-tailscale--acceso-seguro-desde-cualquier-red)
13. [Google Workspace (gog)](#13-acceso-a-google-workspace-desde-el-agente-gog)
14. [Verificación y gestión del stack DGX](#14-verificación-y-gestión-del-stack-dgx)

**PARTE II — UM890 PRO (Cliente)**
15. [Hardware y especificaciones](#15-hardware-y-especificaciones-del-um890-pro)
16. [Configuración de BIOS v1.05](#16-configuración-de-bios-v105)
17. [Instalación de Ubuntu 26.04](#17-instalación-de-ubuntu-2604)
18. [Driver AMD y ROCm](#18-driver-amd-y-rocm)
19. [Ollama en el UM890 + Modelos locales](#19-ollama-en-el-um890--modelos-locales)
20. [OpenClaw en el UM890 — modo dual](#20-openclaw-en-el-um890--modo-dual-local--dgx)
21. [Bot de Telegram — UM890](#21-bot-de-telegram--um890)
22. [Open WebUI — UM890](#22-open-webui--um890)
23. [Conectar el UM890 al DGX Spark](#23-conectar-el-um890-al-dgx-spark)
24. [MEMORIA — Memoria persistente en ambas máquinas](#24-memoria--memoria-persistente-en-ambas-máquinas)
25. [Asistente de voz multilingüe — UM890](#25-asistente-de-voz-multilingüe--um890)
26. [Troubleshooting unificado](#26-troubleshooting-unificado)
27. [Referencia rápida de comandos](#27-referencia-rápida-de-comandos)

---

## Arquitectura Final

```
┌─────────────────────────────────────────────────────────────────┐
│                    DGX SPARK — SERVIDOR                          │
│               NVIDIA GB10 Grace Blackwell · 128 GB              │
│                                                                   │
│  🦞 OpenClaw Gateway :18789 ────── Telegram Bot #1              │
│       ├── nemotron-3-super:120b  → primario (87 GB)             │
│       └── gpt-oss:120b           → alternativo (65 GB)          │
│                                                                   │
│  🤖 Ollama :11434 (OLLAMA_HOST=0.0.0.0) ← escucha en red       │
│  🖥️  Open WebUI :3000                                           │
│  🔑 Tailscale → <DGX_TAILSCALE_IP> (WireGuard cifrado)                 │
│  📧 gog — Google Workspace (Gmail, Drive, Calendar...)          │
│  🧠 MEMORIA → ~/.memoria/memory.md (memoria persistente)        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Tailscale / LAN
              ┌────────────▼────────────────────────┐
              │   Red Privada (LAN o tailnet)         │
              │  Cifrada · Sin puertos abiertos       │
              └──────────────┬──────────────────────-┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                    UM890 PRO — CLIENTE                            │
│          AMD Ryzen 9 8945HS · Radeon 780M · 32 GB DDR5          │
│                   Ubuntu 26.04 LTS "Resolute Raccoon"            │
│                                                                   │
│  🦞 OpenClaw Gateway :18789 ────── Telegram Bot #2              │
│       ├── [LOCAL]  qwen35-es  → chat rápido (primario)          │
│       ├── [LOCAL]  gemma4-es  → visión, multimodal              │
│       ├── [LOCAL]  qwen36-es  → código y razonamiento           │
│       ├── [LOCAL]  nemotron3:33b → agéntico local               │
│       └── [REMOTO] nemotron-3-super:120b @ DGX → tareas grandes │
│                                                                   │
│  🤖 Ollama :11434 — Vulkan — RADV PHOENIX 23.4 GiB             │
│  🧠 MEMORIA → ~/.memoria/memory.md (memoria persistente)        │
│  🖥️  Open WebUI :3000                                           │
│  🔑 Tailscale → 100.64.0.X (misma tailnet que el DGX)          │
└─────────────────────────────────────────────────────────────────┘
```

---

# PARTE I — DGX SPARK (Servidor)

---

## 1. Hardware y requisitos previos

### Especificaciones del DGX Spark

| Componente | Detalle |
|---|---|
| Superchip | NVIDIA GB10 Grace Blackwell |
| CPU | 20 núcleos ARM (Grace) |
| Memoria unificada | 128 GB LPDDR5x (CPU + GPU comparten el mismo pool) |
| Almacenamiento | 4 TB NVMe SSD |
| Red | ConnectX-7, hasta 200 Gbps |
| OS preinstalado | DGX OS 7.x (Ubuntu 24.04 LTS base) |
| Driver NVIDIA | 580.x |
| CUDA | 13.0.x |
| AI Performance | 1 PetaFLOP (FP4) |

### Lo que necesitas antes de empezar

- Cable Ethernet (recomendado para la descarga de ~150 GB de modelos)
- Monitor HDMI o acceso SSH desde otro equipo en la misma red
- Cuenta de Telegram para crear el bot del DGX
- Tiempo estimado: ~45 minutos activos + 30–60 minutos de descarga de modelos

---

## 2. Primer encendido y configuración inicial (OOBE)

### 2.1 Conexión física

1. Usa **únicamente el adaptador de corriente incluido** — otro adaptador reduce el rendimiento máximo.
2. Conecta un cable Ethernet.
3. Conecta monitor HDMI, teclado y ratón USB (o configura remotamente en el paso 3).
4. Pulsa el botón de encendido.

### 2.2 Asistente de primera configuración (OOBE)

**a) Idioma y teclado** — selecciona tu idioma e idioma del teclado.

**b) Red** — conecta a tu red o confirma que el Ethernet fue detectado. El hostname por defecto está en el sticker de la caja: `spark-be9d.local`

**c) Usuario administrador**
- Nombre de usuario (ej. `mloco`)
- Contraseña segura — necesaria para `sudo` y SSH

**d) SSH** — el sistema activa SSH automáticamente. Desde otro equipo:
```bash
ssh mloco@spark-be9d.local
```

**e) Finalizar** — el sistema reinicia. El DGX Dashboard queda disponible en `http://spark-be9d.local`

> El hostname exacto (`spark-be9d`) está impreso en la guía rápida de la caja y en el sticker inferior del dispositivo.

### 2.3 Verificar el estado del sistema

```bash
head -n 2 /etc/os-release  # → Ubuntu 24.04
nvidia-smi                  # → NVIDIA GB10, driver 580.x
nvcc --version              # → CUDA 13.0.x
docker info --format '{{.ServerVersion}}'  # → 28.x o superior
```

---

## 3. Acceso remoto con NVIDIA Sync

NVIDIA Sync es la app oficial de escritorio (macOS / Windows) que gestiona automáticamente el túnel SSH al DGX Spark.

### 3.1 Instalación

Descarga desde: https://www.nvidia.com/en-us/products/workstations/dgx-spark/

### 3.2 Conectar el Spark

1. Abre NVIDIA Sync → **Add Spark**
2. Ingresa el hostname (`spark-be9d.local`) o la IP local
3. Ingresa usuario y contraseña del paso 2.2c
4. NVIDIA Sync configura autenticación por clave SSH automáticamente

### 3.3 Aplicaciones disponibles

- **Terminal** con conexión SSH directa
- **DGX Dashboard** (gestión del sistema, JupyterLab)
- Dashboard de OpenClaw accesible apuntando al puerto `18789`

---

## 4. Actualización del sistema

> **Método oficial de NVIDIA: siempre usa el DGX Dashboard para las actualizaciones.** Garantiza la cadena probada para DGX OS, drivers, CUDA y firmware del GB10.

### 4.1 Actualizar vía DGX Dashboard (recomendado)

1. Abre el DGX Dashboard:
   - **Local:** Apps → DGX Dashboard
   - **SSH tunnel manual:** `ssh -L 11000:localhost:11000 mloco@spark-be9d.local` → `http://localhost:11000`
2. Busca **Updates / System Updates** → **Check for Updates** → **Apply Updates**
3. El sistema reiniciará si es necesario

### 4.2 Dependencias adicionales

```bash
sudo apt install -y \
  git curl wget \
  build-essential \
  ca-certificates \
  python3 python3-pip
```

---

## 5. Configuración de Docker + NVIDIA Container Runtime

### 5.1 Registrar el runtime de NVIDIA

```bash
sudo nvidia-ctk runtime configure --runtime=docker
```

### 5.2 Configurar el modo cgroup (específico para DGX Spark)

```bash
sudo python3 -c "
import json, os
path = '/etc/docker/daemon.json'
d = json.load(open(path)) if os.path.exists(path) else {}
d['default-cgroupns-mode'] = 'host'
json.dump(d, open(path, 'w'), indent=2)
"
```

### 5.3 Añadir tu usuario al grupo docker

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### 5.4 Reiniciar Docker y verificar

```bash
sudo systemctl restart docker

# Verificar que la GPU es visible desde un contenedor
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

---

## 6. Ollama en el DGX Spark

Ollama se instala **directamente en el host** (no como contenedor), para aprovechar al máximo la memoria unificada del GB10.

### 6.1 Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

El instalador detecta automáticamente la arquitectura ARM64 y el GPU Blackwell.

### 6.2 Habilitar el inicio automático

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
```

### 6.3 Verificar que Ollama está corriendo

```bash
curl http://localhost:11434
# Respuesta esperada: "Ollama is running"

sudo systemctl status ollama
```

---

## 7. Descarga de los modelos 120B

Con 128 GB de memoria unificada, el DGX Spark puede cargar completamente ambos modelos de 120B.

### 7.1 Nemotron 3 Super 120B

Modelo principal, optimizado para razonamiento multi-paso y uso de herramientas:

```bash
ollama pull nemotron-3-super:120b
```

**Tamaño:** ~87 GB | **Tiempo estimado:** 15–30 min

### 7.2 GPT-OSS 120B

Modelo alternativo con cuantización MXFP4, optimizado para el GB10:

```bash
ollama pull gpt-oss:120b
```

**Tamaño:** ~65 GB | **Tiempo estimado:** 10–20 min

### 7.3 Modelo de embeddings (para VS Code / Continue.dev)

```bash
ollama pull nomic-embed-text
```

### 7.4 Pre-cargar los modelos en memoria

Elimina la latencia de cold-start:

```bash
ollama run nemotron-3-super:120b
# Cuando aparezca >>> escribe /bye y Enter

ollama run gpt-oss:120b
# Cuando aparezca >>> escribe /bye y Enter
```

### 7.5 Verificar modelos disponibles

```bash
ollama list
```

Salida esperada:
```
NAME                        ID              SIZE
nemotron-3-super:120b       95acc78b3ffd    86 GB
gpt-oss:120b                a97757631e2b    65 GB
nomic-embed-text            ...             274 MB
```

---

## 8. OpenClaw en el DGX Spark

### 8.1 Prerrequisito: Node.js

```bash
node --version

# Si no está instalado:
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

### 8.2 Configurar npm sin sudo

```bash
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# Verificar
npm config get prefix
# → /home/mloco/.npm-global
```

### 8.3 Instalar OpenClaw

```bash
npm install -g openclaw
openclaw --version
```

### 8.4 Onboarding

```bash
openclaw onboard
```

El wizard pedirá en orden:

1. **Proveedor de inferencia** → selecciona **Ollama** → URL por defecto `http://127.0.0.1:11434/v1`
2. **Modelo principal** → selecciona `nemotron-3-super:120b`
3. **Canales de mensajería** → omitir por ahora (`n`)
4. **Búsqueda web y fetch** → `Y`

### 8.5 Configuración avanzada (ambos modelos 120B)

```bash
nano ~/.openclaw/config.json
```

```json
{
  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://127.0.0.1:11434/v1",
        "apiKey": "ollama-local",
        "api": "openai-completions",
        "models": [
          {
            "id": "nemotron-3-super:120b",
            "name": "Nemotron 3 Super 120B",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 8192
          },
          {
            "id": "gpt-oss:120b",
            "name": "GPT-OSS 120B",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 8192
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "ollama/nemotron-3-super:120b"
      },
      "maxConcurrent": 4,
      "subagents": {
        "maxConcurrent": 8
      }
    }
  },
  "tools": {
    "web": {
      "search": { "enabled": true },
      "fetch": { "enabled": true }
    }
  }
}
```

```bash
openclaw gateway restart
```

### 8.6 Arrancar el gateway como servicio

```bash
openclaw gateway start --background
openclaw gateway status
```

---

## 9. Bot de Telegram — DGX Spark

### 9.1 Crear el bot con @BotFather

1. Abre Telegram → busca `@BotFather`
2. Envía `/newbot`
3. Asigna nombre (ej. `Mi Asistente DGX`) y username (termina en `bot`)
4. Guarda el **token API** que te entrega

### 9.2 Conectar Telegram a OpenClaw

```bash
openclaw configure --section channels
```

1. Selecciona **Telegram**
2. Ingresa el bot token del @BotFather
3. Selecciona **Finished**

### 9.3 Emparejar tu cuenta

1. Abre Telegram → busca tu bot → envía cualquier mensaje
2. El bot responde con:
   ```
   OpenClaw: access not configured.
   Your Telegram user id: 123456789
   Pairing code: XXXX-YYYY
   ```
3. Ingresa el código en el Web UI: `http://127.0.0.1:18789`

> **Latencia esperada:** los modelos de 120B toman **30–90 segundos** por respuesta. Es completamente normal.

---

## 10. Open WebUI — DGX Spark

```bash
# Crear volumen primero
docker volume create open-webui

docker run -d \
  --name open-webui \
  --network=host \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Acceder en: **http://localhost:3000**

> Todos los modelos aparecen automáticamente desde Ollama.

---

## 11. Exponer Ollama a la red local

Para que el UM890 y otros equipos puedan consumir los modelos del DGX Spark.

```bash
# Crear el directorio de override de systemd
sudo mkdir -p /etc/systemd/system/ollama.service.d

# Escuchar en todas las interfaces
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n' | \
  sudo tee /etc/systemd/system/ollama.service.d/override.conf

# Aplicar cambios
sudo systemctl daemon-reload
sudo systemctl restart ollama

# Verificar
curl http://0.0.0.0:11434
# → "Ollama is running"

# Obtener la IP local del Spark
hostname -I | awk '{print $1}'
# Ejemplo: 192.168.1.42
```

---

## 12. Tailscale — Acceso seguro desde cualquier red

Tailscale crea una red privada cifrada (WireGuard) entre todos tus dispositivos. Funciona desde cualquier red sin abrir puertos en el router.

### 12.1 Crear cuenta de Tailscale

Ve a https://tailscale.com y crea una cuenta gratuita (hasta 100 dispositivos).

### 12.2 Instalar Tailscale en el DGX Spark

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | \
  sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg > /dev/null

curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | \
  sudo tee /etc/apt/sources.list.d/tailscale.list

sudo apt update && sudo apt install -y tailscale
```

### 12.3 Autenticar el DGX Spark

```bash
sudo tailscale up
# Visita la URL que muestra → Log in → Connect

sudo systemctl enable tailscaled
sudo systemctl start tailscaled

tailscale ip
# Ejemplo: <DGX_TAILSCALE_IP> (esta IP no cambia aunque cambies de red)
```

### 12.4 Habilitar MagicDNS (recomendado)

Activar en https://login.tailscale.com/admin/dns → **Enable MagicDNS**

Con MagicDNS puedes usar el hostname en lugar de la IP:
```bash
curl http://spark-be9d:11434
```

### 12.5 Comandos útiles de Tailscale

```bash
tailscale status          # Ver todos los dispositivos y sus IPs
tailscale ip              # IP de este dispositivo
tailscale ping 100.64.0.X # Probar conectividad
sudo tailscale up         # Reconectar / reautenticar
sudo tailscale down       # Desconectar
```

---

## 13. Acceso a Google Workspace desde el agente (gog)

`gog` es el CLI oficial de OpenClaw para Gmail, Calendar, Drive, Docs, Sheets y Contacts.

### 13.1 Qué puede hacer el agente con gog

- **Gmail:** leer, buscar, enviar, responder, archivar y eliminar emails
- **Calendar:** ver, crear, editar y eliminar eventos
- **Drive:** buscar, leer, subir y descargar archivos
- **Docs:** exportar y leer documentos
- **Sheets:** leer y escribir celdas y rangos
- **Contacts:** listar y buscar contactos

### 13.2 Parte 1 — Google Cloud: proyecto, APIs y credenciales OAuth

**Paso 1 — Crear el proyecto**
1. Ve a https://console.cloud.google.com
2. Selector de proyecto → **Nuevo proyecto** → nombre `openclaw-gog` → **Crear**

**Paso 2 — Habilitar APIs** (APIs y servicios → Biblioteca)

| API a habilitar |
|---|
| Gmail API |
| Google Calendar API |
| Google Drive API |
| Google Sheets API |
| Google Docs API |
| People API |

**Paso 3 — Pantalla de consentimiento OAuth**
1. APIs y servicios → Pantalla de consentimiento OAuth → Externo → Crear
2. Completa nombre de la app, email de soporte, email de contacto
3. En la sección Publicación: **Publicar app** (evita que los tokens expiren a los 7 días)

**Paso 4 — Crear credenciales OAuth**
1. APIs y servicios → Credenciales → + Crear credenciales → ID de cliente OAuth
2. Tipo: **Aplicación de escritorio** → Nombre: `gog-dgx-spark`
3. **Descargar JSON** → guarda en tu equipo local como `client_secret.json`

### 13.3 Parte 2 — Instalar gogcli en el DGX Spark

```bash
# Obtener la última versión
GOG_VERSION=$(curl -s https://api.github.com/repos/openclaw/gogcli/releases/latest \
  | grep tag_name | cut -d'"' -f4)

# Descargar el binario ARM64 Linux
curl -L "https://github.com/openclaw/gogcli/releases/download/${GOG_VERSION}/gogcli_${GOG_VERSION#v}_linux_arm64.tar.gz" \
  -o /tmp/gogcli.tar.gz

mkdir -p ~/.local/bin
tar -xzf /tmp/gogcli.tar.gz -C /tmp
mv /tmp/gog ~/.local/bin/gog
chmod +x ~/.local/bin/gog

# Symlink global para OpenClaw
sudo ln -s /home/$(whoami)/.local/bin/gog /usr/local/bin/gog

gog --version  # ✅
```

### 13.4 Parte 3 — Autenticación OAuth (SSH tunnel)

El DGX Spark no tiene navegador, la autenticación se completa desde tu equipo local usando un túnel SSH.

**Copiar el JSON de credenciales al Spark** (desde tu equipo local):
```bash
scp ~/Downloads/client_secret_*.json mloco@spark-be9d.local:~/client_secret.json
```

**En el terminal del Spark:**
```bash
gog auth credentials ~/client_secret.json

gog auth add tu.correo@gmail.com \
  --services gmail,calendar,drive,contacts,sheets,docs
```

`gog` mostrará una URL y un puerto (ej. `44139`). **Anota el puerto.**

**Crear el túnel SSH desde tu equipo local** (nueva terminal):
```bash
ssh -L 44139:localhost:44139 mloco@spark-be9d.local
# Sustituye 44139 por el puerto real
```

**Autenticar en el navegador:** abre la URL de Google en tu navegador. Tras aceptar:
```
✓ Account tu.correo@gmail.com authenticated successfully
```

**Verificar:**
```bash
gog auth list --check
# → tu.correo@gmail.com  gmail,calendar,drive,contacts,sheets,docs  ✓
```

### 13.5 Parte 4 — Activar gog en OpenClaw

```bash
openclaw skills install gog
nano ~/.openclaw/config.json
# Cambiar "gog": { "enabled": true }

echo 'export GOG_ACCOUNT=tu.correo@gmail.com' >> ~/.bashrc
source ~/.bashrc

openclaw gateway restart
openclaw skills list | grep gog
# → ✓ ready  │ 🎮 gog │ Google Workspace CLI...
```

### 13.6 Comandos de gog

```bash
# Gmail
gog gmail search 'newer_than:7d' --max 10
gog gmail search 'is:unread' --max 20
gog gmail send --to a@b.com --subject "Hola" --body "Mensaje"

# Calendar
gog calendar events --today
gog calendar create <calendarId> --summary "Reunión"

# Drive
gog drive search "nombre del archivo" --max 10
gog drive download <fileId> --out /tmp/archivo

# Sheets
gog sheets get <sheetId> "Hoja1!A1:D10" --json

# Docs
gog docs export <docId> --format txt --out /tmp/doc.txt

# Auth
gog auth list --check
```

---

## 14. Verificación y gestión del stack DGX

### 14.1 Verificación completa

```bash
# Ollama
curl http://localhost:11434         # → "Ollama is running"
curl http://0.0.0.0:11434          # → accesible desde red
ollama list                         # → modelos disponibles
ollama ps                           # → modelos en ejecución

# OpenClaw
openclaw gateway status
openclaw tui                        # Abrir chat en terminal

# Docker / Open WebUI
docker ps | grep open-webui

# Tailscale
tailscale status
tailscale ip

# GPU
nvidia-smi

# gog
gog auth list --check
```

### 14.2 Comandos de gestión

```bash
# Ollama
sudo systemctl status ollama
sudo systemctl restart ollama
ollama pull <modelo>
ollama rm <modelo>
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches  # Liberar RAM

# OpenClaw
openclaw gateway start --background
openclaw gateway status
openclaw gateway restart
openclaw gateway stop
openclaw gateway logs
openclaw configure --section channels
npm update -g openclaw

# Sistema
nvidia-smi
free -h
df -h
```

### 14.3 Probar los modelos

```bash
openclaw agent --agent main --local -m "¿Qué modelos tienes disponibles?" --session-id test
ollama run nemotron-3-super:120b "Di hola en 5 idiomas"
ollama run gpt-oss:120b "Di hola en 5 idiomas"
```

---

# PARTE II — UM890 PRO (Cliente)

---

## 15. Hardware y especificaciones del UM890 PRO

### Hardware

| Componente | Especificación |
|---|---|
| **CPU** | AMD Ryzen 9 8945HS — 8C/16T, hasta 5.2 GHz, TDP 35–70W configurable |
| **iGPU** | AMD Radeon 780M — RDNA 3, 12 CUs @ 2800 MHz, gfx1103 |
| **RAM** | 32 GB DDR5-5600 — compartida CPU/GPU (**16 GB asignados a iGPU en BIOS**) |
| **SSD** | 1 TB NVMe PCIe 4.0 — ~7 GB/s |
| **NPU** | AMD XDNA — 16 TOPS |
| **BIOS** | American Megatrends v1.05 — 19/05/2025 |

### Rendimiento real con Vulkan en iGPU

> ⚠️ El backend Vulkan de Ollama tiene ~50% de eficiencia frente a ROCm optimizado. La 780M con DDR5-5600 tiene ~89 GB/s de ancho de banda compartido CPU/GPU.

| Modelo | Tamaño | Velocidad real | Limitante |
|---|---|---|---|
| **qwen3.5:9b** | ~6.6 GB | 6–8 tok/s | BW: 89 GB/s ÷ 6.6 GB |
| **gemma4:26b** | ~16 GB | 3–5 tok/s | BW: 89 GB/s ÷ 16 GB |
| **qwen3.6:27b** | ~17 GB | 3–5 tok/s | BW: 89 GB/s ÷ 17 GB |
| **nemotron3:33b** | ~28 GB | 2–3 tok/s | GPU+CPU split |

### Stack de modelos locales

| Modelo | Alias | Rol |
|---|---|---|
| 🖼️ **gemma4-es** (gemma4:26b) | `gemma` | Primario multimodal. Imágenes, visión, agente, tool calling |
| 🧠 **qwen36-es** (qwen3.6:27b) | `qwen` | Código y razonamiento. 77.2% SWE-bench |
| 🤖 **nemotron3:33b** | `nemotron` | Agéntico avanzado. GPU+CPU split |
| ⚡ **qwen35-es** (qwen3.5:9b) | `fast` | Chat rápido, respuestas inmediatas, Telegram |

### Novedades de Ubuntu 26.04 relevantes para IA

| Cambio | Impacto |
|---|---|
| **Kernel 7.0** | Mejor soporte AMD GPU |
| **ROCm en repos oficiales** | `sudo apt install rocm` — sin script externo |
| **dracut** reemplaza initramfs-tools | Comandos de initramfs cambian (ver sección 18) |
| **cgroup v2 exclusivo** | Sin impacto en Ollama |

---

## 16. Configuración de BIOS v1.05

> ⚠️ Menús verificados en **BIOS v1.05 (mayo 2025)**. Versiones anteriores pueden tener estructura diferente.

**Acceder:** Reinicia y presiona `Delete` repetidamente.

### 16.1 VRAM iGPU ← más importante

```
Advanced
  └── AMD CBS
        └── NBIO Common Options
              └── GFX Configuration
                    └── UMA Frame Buffer Size → 16G
```

> ⚠️ En v1.05 la opción está dentro de `GFX Configuration`, un nivel más profundo.

### 16.2 TDP del CPU

```
Advanced
  └── PowerLimit Setting
        └── Power Limit → Performance Mode (~70W)
```

> Performance Mode es crítico para nemotron3:33b en split GPU+CPU.

### 16.3 EXPO — DDR5 a velocidad completa

```
Advanced
  └── AMD CBS
        └── UMC Common Options
              └── EXPO Profile → Profile 1 (5600 MT/s)
```

> ⚠️ Sin EXPO la RAM corre a 4800 MT/s — el ancho de banda de la iGPU baja un 20% (89 GB/s vs 71 GB/s).

### 16.4 Secure Boot

```
Security
  └── Secure Boot → Disabled
```

### Resumen BIOS

| Qué cambiar | Ruta | Valor |
|---|---|---|
| **VRAM iGPU** | `Advanced → AMD CBS → NBIO Common Options → GFX Configuration → UMA Frame Buffer Size` | **16G** |
| **TDP CPU** | `Advanced → PowerLimit Setting` | **Performance Mode** |
| **EXPO RAM** | `Advanced → AMD CBS → UMC Common Options → EXPO Profile` | **Profile 1** |
| **Secure Boot** | `Security → Secure Boot` | **Disabled** |

---

## 17. Instalación de Ubuntu 26.04

### ISO y medio de instalación

```bash
wget https://releases.ubuntu.com/26.04/ubuntu-26.04-desktop-amd64.iso
sudo dd if=ubuntu-26.04-desktop-amd64.iso of=/dev/sdX bs=4M status=progress
```

**Particionado sugerido:**

| Partición | Tamaño | FS |
|---|---|---|
| EFI | 512 MB | FAT32 |
| swap | 4 GB | swap |
| / | Resto | btrfs |

### 17.1 Post-instalación base

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential git curl wget htop btop nvtop
uname -r   # → 7.0.x-xx-generic
```

### 17.2 CPU Governor — Servicio systemd

> ⚠️ En kernel 7.0 con `amd-pstate-epp`, `cpufrequtils` y `powerprofilesctl` no funcionan correctamente. El servicio systemd directo a sysfs es la solución estable.

```bash
sudo tee /etc/systemd/system/ai-performance.service << 'EOF'
[Unit]
Description=AI Performance Mode — CPU + GPU
After=multi-user.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c '\
  for f in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > $f; done; \
  for f in /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; do echo performance > $f; done; \
  for card in /sys/class/drm/card*/device/vendor; do \
    if [ "$(cat $card 2>/dev/null)" = "0x1002" ]; then \
      echo high > $(dirname $card)/power_dpm_force_performance_level; \
    fi; \
  done'

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ai-performance.service

# Verificar
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference  # → performance ✅
cat /sys/class/drm/card1/device/power_dpm_force_performance_level        # → high ✅
```

> El servicio detecta la GPU AMD por vendor ID `0x1002`. En el UM890 PRO la 780M está en `card1`, no en `card0`.

### 17.3 ZRAM

> ⚠️ Crítico para nemotron3:33b en split. ZRAM con zstd hace que el overflow sea 3–5x más rápido que swap en disco.

```bash
sudo apt install -y systemd-zram-generator

sudo tee /etc/systemd/zram-generator.conf << 'EOF'
[zram0]
zram-size = 8192
compression-algorithm = zstd
swap-priority = 100
fs-type = swap
EOF

sudo systemctl daemon-reload
sudo systemctl start systemd-zram-setup@zram0.service

zramctl  # → /dev/zram0  zstd  8G  [SWAP] ✅
```

> Si `zramctl` muestra 4G o lzo-rle: `sudo swapoff /dev/zram0` → `sudo systemctl stop systemd-zram-setup@zram0.service` → `sudo systemctl daemon-reload` → `sudo systemctl start systemd-zram-setup@zram0.service`

### 17.4 Parámetros del kernel

```bash
sudo tee -a /etc/sysctl.conf << 'EOF'
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.max_map_count = 2097152
vm.dirty_ratio = 20
vm.dirty_background_ratio = 5
EOF

sudo sysctl -p
```

---

## 18. Driver AMD y ROCm

### 18.1 ROCm en repos oficiales (gran novedad Ubuntu 26.04)

```bash
sudo apt install -y python3-setuptools python3-wheel
sudo usermod -aG render,video $USER
sudo apt install -y rocm

# Hacer logout/login o ejecutar en la misma sesión:
newgrp render

rocm-smi             # → Radeon 780M, temperatura ✅
rocminfo | grep gfx  # → gfx1103 ✅
```

### 18.2 amdgpu en Kernel 7.0

Con kernel 7.0, `amdgpu` puede cargar automáticamente. Verifica primero:

```bash
lsmod | grep amdgpu
```

Si no aparece:

```bash
sudo modprobe amdgpu
echo 'amdgpu' | sudo tee /etc/modules-load.d/amdgpu.conf

# dracut reemplaza initramfs-tools en Ubuntu 26.04
# NO usar update-initramfs — ese comando ya no existe
echo 'add_drivers+=" amdgpu "' | sudo tee /etc/dracut.conf.d/amdgpu.conf
sudo dracut --regenerate-all --force

sudo reboot
```

### 18.3 Variables de entorno AMD

```bash
cat >> ~/.bashrc << 'EOF'
export HSA_OVERRIDE_GFX_VERSION=11.0.3
export ROCR_VISIBLE_DEVICES=0
export HIP_VISIBLE_DEVICES=0
export OLLAMA_NUM_GPU=999
export OLLAMA_FLASH_ATTENTION=1
EOF
source ~/.bashrc
```

---

## 19. Ollama en el UM890 + Modelos locales

### 19.1 Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version   # → 0.23.x+ ✅
sudo systemctl enable --now ollama
```

### 19.2 Configurar backend Vulkan

> ⚠️ ROCm no soporta gfx1103 para inferencia en Ollama. El backend **Vulkan** es la solución estable y detecta 23.4 GiB disponibles.
> ⚠️ Usar `OLLAMA_VULKAN=1` (número). El valor `true` es ignorado silenciosamente.
> ⚠️ **No usar `OLLAMA_KV_CACHE_TYPE=q8_0`** — satura los ~7 GB de VRAM restantes y provoca swapping.

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d/

sudo tee /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="HSA_OVERRIDE_GFX_VERSION=11.0.3"
Environment="OLLAMA_NUM_GPU=999"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_VULKAN=1"
Environment="OLLAMA_DEBUG=INFO"
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

sudo systemctl daemon-reload && sudo systemctl restart ollama
sleep 3

# Verificar GPU detectada
sudo journalctl -u ollama --since "1 min ago" | grep -i 'vulkan\|inference'
# → library=Vulkan  name=Vulkan0
# → description="AMD Radeon 780M Graphics (RADV PHOENIX)"
# → total="23.4 GiB" ✅
```

### 19.3 Instalar modelos locales

```bash
ollama pull gemma4:26b        # ~16 GB — primario multimodal
ollama pull qwen3.6:27b       # ~17 GB — código y razonamiento
ollama pull nemotron3:33b     # ~28 GB — agéntico avanzado
ollama pull qwen3.5:9b        # ~6.6 GB — chat rápido

ollama list
```

### 19.4 Modelfiles sin thinking mode ← obligatorio

> ⚠️ Gemma4, Qwen3.6 y Qwen3.5 tienen thinking mode por defecto. Cada respuesta puede generar 500–1000 tokens de razonamiento antes de contestar. Los Modelfiles siguientes desactivan el thinking de forma efectiva.

| Modelfile | num_ctx | VRAM total |
|---|---|---|
| qwen35-es | 32768 | ~12.6 GB ✅ amplio |
| gemma4-es | 16384 | ~19 GB ✅ justo |
| qwen36-es | 16384 | ~20 GB ✅ justo |

```bash
# qwen3.5 sin thinking — chat rápido principal
cat > /tmp/Modelfile-qwen35 << 'EOF'
FROM qwen3.5:9b
SYSTEM "Eres un asistente personal inteligente. Responde SIEMPRE en español salvo que el usuario pida otro idioma. Sé conciso y directo."
PARAMETER num_ctx 32768
PARAMETER num_predict 1024
EOF
ollama create qwen35-es -f /tmp/Modelfile-qwen35

# gemma4 sin thinking — primario multimodal
cat > /tmp/Modelfile-gemma4 << 'EOF'
FROM gemma4:26b
SYSTEM "Eres un asistente personal inteligente. Responde SIEMPRE en español salvo que el usuario pida otro idioma. Sé conciso y directo."
PARAMETER num_ctx 16384
PARAMETER num_predict 1024
EOF
ollama create gemma4-es -f /tmp/Modelfile-gemma4

# qwen3.6 sin thinking — código y razonamiento
cat > /tmp/Modelfile-qwen36 << 'EOF'
FROM qwen3.6:27b
SYSTEM "Eres un asistente experto en código y razonamiento. Responde siempre en español."
PARAMETER num_ctx 16384
PARAMETER num_predict 1024
EOF
ollama create qwen36-es -f /tmp/Modelfile-qwen36

# Verificar
ollama list | grep '\-es'
# → gemma4-es  qwen35-es  qwen36-es  ✅
```

> `nemotron3:33b` no necesita Modelfile — es un modelo agéntico sin thinking mode problemático.

### 19.5 Test de velocidad

```bash
time ollama run qwen35-es 'Hola, ¿en qué GPU estás corriendo?'
ollama run qwen35-es --verbose 'Di hola en una frase.' 2>&1 | grep 'eval rate'
# → eval rate: 6–8 tok/s
```

---

## 20. OpenClaw en el UM890 — Modo dual (local + DGX)

En el UM890, OpenClaw puede usar tanto los modelos locales como los del DGX Spark de forma transparente.

### 20.1 Instalar Node.js y OpenClaw

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # → v24.x.x

sudo npm install -g pnpm
sudo npm install -g openclaw@latest

openclaw --version  # → OpenClaw 2026.x.x ✅
```

### 20.2 Configuración — `~/.openclaw/openclaw.json.template`

Esta configuración registra tanto los modelos locales como los del DGX Spark:

```bash
mkdir -p ~/Escritorio/Servidor-ia/agente_workspace
```

```json
{
  "agents": {
    "defaults": {
      "workspace": "/home/mloco/Escritorio/Servidor-ia/agente_workspace",
      "thinkingDefault": "off",
      "verboseDefault": "off",
      "systemPromptOverride": "Eres un asistente personal inteligente. Responde SIEMPRE en español, de forma clara y concisa. Nunca uses otro idioma a menos que el usuario lo pida explícitamente.",
      "models": {
        "ollama/qwen35-es":               { "alias": "fast" },
        "ollama/gemma4-es":               { "alias": "gemma" },
        "ollama/qwen36-es":               { "alias": "qwen" },
        "ollama/nemotron3:33b":           { "alias": "nemotron" },
        "dgx/nemotron-3-super:120b":      { "alias": "spark" },
        "dgx/gpt-oss:120b":              { "alias": "gpt120" }
      },
      "model": {
        "primary": "ollama/qwen35-es",
        "fallbacks": ["ollama/qwen35-es"]
      }
    }
  },
  "gateway": {
    "mode": "local",
    "auth": {
      "mode": "token",
      "token": "${OPENCLAW_GATEWAY_TOKEN}"
    },
    "port": 18789,
    "bind": "lan",
    "tailscale": { "mode": "off", "resetOnExit": false },
    "controlUi": {
      "allowInsecureAuth": true,
      "dangerouslyAllowHostHeaderOriginFallback": true,
      "dangerouslyDisableDeviceAuth": true,
      "allowedOrigins": [
        "http://${OPENCLAW_IP_LOCAL}:18789",
        "http://127.0.0.1:18789",
        "http://localhost:18789"
      ]
    }
  },
  "session": {
    "dmScope": "per-channel-peer",
    "maxHistoryTokens": 12000
  },
  "tools": { "profile": "coding" },
  "models": {
    "mode": "replace",
    "providers": {
      "ollama": {
        "baseUrl": "http://127.0.0.1:11434",
        "api": "ollama",
        "apiKey": "OLLAMA_API_KEY",
        "models": [
          {
            "id": "qwen35-es", "name": "qwen35-es",
            "reasoning": false, "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 32768, "maxTokens": 1024
          },
          {
            "id": "gemma4-es", "name": "gemma4-es",
            "reasoning": false, "input": ["text", "image"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 16384, "maxTokens": 1024
          },
          {
            "id": "qwen36-es", "name": "qwen36-es",
            "reasoning": false, "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 16384, "maxTokens": 1024
          },
          {
            "id": "nemotron3:33b", "name": "nemotron3:33b",
            "reasoning": true, "input": ["text", "image"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072, "maxTokens": 4096
          }
        ]
      },
      "dgx": {
        "baseUrl": "${DGX_OLLAMA_URL}",
        "api": "ollama",
        "apiKey": "ollama-local",
        "models": [
          {
            "id": "nemotron-3-super:120b",
            "name": "Nemotron 3 Super 120B (DGX Spark)",
            "reasoning": false, "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072, "maxTokens": 8192
          },
          {
            "id": "gpt-oss:120b",
            "name": "GPT-OSS 120B (DGX Spark)",
            "reasoning": false, "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072, "maxTokens": 8192
          }
        ]
      }
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "groups": { "*": { "requireMention": true } },
      "botToken": "${OPENCLAW_TELEGRAM_BOT_TOKEN}"
    }
  },
  "plugins": { "entries": { "ollama": { "enabled": true } } },
  "commands": {
    "ownerAllowFrom": ["telegram:${OPENCLAW_TELEGRAM_OWNER_ID}"]
  }
}
```

### 20.3 Onboarding e inicio

```bash
openclaw onboard --install-daemon
# Proveedor: Ollama | modelo: qwen35-es | canal: Telegram

# Iniciar el servicio 24/7
systemctl --user restart openclaw-gateway
sleep 5
journalctl --user -u openclaw-gateway --since "30 sec ago" | grep -i 'error\|ready\|telegram'
# → Telegram connected ✅
# → Gateway ready on :18789 ✅

# Activar al arranque
systemctl --user enable openclaw-gateway
sudo loginctl enable-linger $USER
```

### 20.4 Precedencia de credenciales Telegram

Para evitar duplicados, usa esta prioridad:

1. Variables de entorno (`OPENCLAW_TELEGRAM_*`, `TELEGRAM_*`).
2. `OPENCLAW_CONFIG_PATH` (si apunta a un JSON valido).
3. `~/.openclaw/openclaw.json` (o fallback `openclaw.json.novo`).

Mapeo recomendado:

- `channels.telegram.botToken` -> token del bot.
- `commands.ownerAllowFrom[0]` -> owner permitido (`telegram:123456` o `123456`).

El source of truth del runtime debe ser `~/.openclaw/openclaw.json` generado desde `.credentials` + template.

---

## 21. Bot de Telegram — UM890

El UM890 necesita su **propio bot de Telegram** (token distinto al del DGX).

### 21.1 Crear el bot

1. Telegram → **@BotFather** → `/newbot`
2. Nombre: ej. `Mi Asistente UM890`
3. Username: termina en `bot` (debe ser distinto al del DGX)
4. Copia el token → pégalo en `.credentials` como `OPENCLAW_TELEGRAM_BOT_TOKEN`

> ⚠️ El mismo token no puede usarse en dos instancias simultáneas.

### 21.2 Comandos desde Telegram en el UM890

| Comando | Modelo | Uso |
|---|---|---|
| `/model fast` | qwen35-es | **Por defecto.** Chat rápido, respuestas en 10–30s |
| `/model gemma` | gemma4-es | Imágenes, visión, multimodal |
| `/model qwen` | qwen36-es | Código complejo, análisis |
| `/model nemotron` | nemotron3:33b | Agéntico local avanzado |
| `/model spark` | nemotron-3-super:120b @ DGX | Tareas que requieren el 120B |
| `/model gpt120` | gpt-oss:120b @ DGX | Alternativa 120B en DGX |
| `/skills` | — | Ver skills activos |
| `/memory` | — | Ver contexto persistente |
| `/clear` | — | Limpiar historial |

### 21.3 Skill Telegram standalone (diagnostico local)

Si necesitas probar el adapter fuera del gateway:

```bash
cd ~/Escritorio/Servidor-ia/agente_workspace

# Webhook Flask
python -m skills.telegram.telegram_skill --serve

# Polling local (sin webhook publico)
python -m skills.telegram.telegram_skill --poll

# Un ciclo proactivo manual
python -m skills.telegram.telegram_skill --proactive-once
```

Comandos minimos de validacion en Telegram: `/start`, `/help`, `/status`, `/summary`, luego un mensaje normal y una media (voz/foto/documento).

---

## 22. Open WebUI — UM890

```bash
docker volume create open-webui

docker run -d \
  --name open-webui \
  --network=host \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Acceder en: **http://localhost:3000**

> Todos los modelos locales aparecen automáticamente. Para ver también los modelos del DGX, configura una conexión Ollama adicional apuntando a `http://<DGX_TAILSCALE_IP>:11434` en los ajustes de Open WebUI.

---

## 23. Conectar el UM890 al DGX Spark

### 23.1 Instalar Tailscale en el UM890

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | \
  sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg > /dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | \
  sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt update && sudo apt install -y tailscale
sudo tailscale up
# Autenticarse con la MISMA cuenta que el DGX Spark

sudo systemctl enable tailscaled
tailscale ip  # Anotar la IP del UM890
```

### 23.2 Verificar conectividad UM890 → DGX

```bash
# Desde el UM890
ping <DGX_TAILSCALE_IP>  # IP de Tailscale del DGX

curl http://<DGX_TAILSCALE_IP>:11434
# → "Ollama is running" ✅

# Ver modelos disponibles en el DGX
curl http://<DGX_TAILSCALE_IP>:11434/api/tags | python3 -m json.tool | grep name
```

### 23.3 VS Code + Continue.dev apuntando al DGX

Instala la extensión Continue en VS Code. Las versiones recientes usan `~/.continue/config.yaml` (no `config.json`):

```bash
cat > ~/.continue/config.yaml << 'EOF'
name: Local Config
version: 1.0.0
schema: v1

models:
  - name: Nemotron 3 Super 120B (DGX Spark)
    provider: ollama
    model: nemotron-3-super:120b
    apiBase: http://<DGX_TAILSCALE_IP>:11434

  - name: GPT-OSS 120B (DGX Spark)
    provider: ollama
    model: gpt-oss:120b
    apiBase: http://<DGX_TAILSCALE_IP>:11434

  - name: Qwen3.5 9B (UM890 Local)
    provider: ollama
    model: qwen35-es
    apiBase: http://127.0.0.1:11434

tabAutocompleteModel:
  name: Qwen3.5 9B (UM890 Local)
  provider: ollama
  model: qwen35-es
  apiBase: http://127.0.0.1:11434
EOF
```

> ⚠️ Continue usa `config.yaml` desde sus versiones recientes. El `config.json` es ignorado si existe un `config.yaml`.

| Atajo VS Code | Acción |
|---|---|
| `Ctrl+Alt+J` | Abrir chat Continue |
| Selecciona código → `Ctrl+L` | Explicar código |
| Selecciona código → `Ctrl+I` | Editar con instrucción |
| `Tab` al escribir código | Aceptar autocompletado |

---

## 24. MEMORIA — Memoria persistente en ambas máquinas

MEMORIA es un skill de OpenClaw que da al agente memoria persistente entre sesiones. Todo se almacena en un único archivo local `~/.memoria/memory.md` — sin cloud, sin API keys.

### 24.1 Instalación (igual en DGX y UM890)

```bash
openclaw skills install agent-memoria

mkdir -p ~/.memoria
chmod 700 ~/.memoria
touch ~/.memoria/memory.md
chmod 600 ~/.memoria/memory.md
echo ".memoria/" >> ~/.gitignore
echo "memoria.md" >> ~/.gitignore
```

**En el DGX Spark:**
```bash
openclaw gateway restart
```

**En el UM890:**
```bash
systemctl --user restart openclaw-gateway
```

Verificar que está activo:
```bash
openclaw skills list | grep memoria
# → ✓ ready  │ 📦 memoria │ ...
```

### 24.2 Onboarding — activación correcta

> ⚠️ El skill no se activa automáticamente al instalar. Hay que iniciarlo explícitamente desde Telegram.

**Paso 1** — Limpia el historial de la sesión actual:
```
/clear
```

**Paso 2** — Envía este mensaje al bot:
```
inicializa MEMORIA desde cero, hazme las 5 preguntas de onboarding
```

El agente hará las 5 preguntas:
1. ¿Cuál es tu nombre y a qué te dedicas?
2. ¿Qué es lo principal que estás construyendo o en lo que trabajas ahora?
3. ¿Cuál es tu stack tecnológico? (lenguajes, frameworks, herramientas)
4. ¿Cuál es tu mayor reto o bloqueo actual?
5. ¿Cómo prefieres que me comunique contigo?

Tras responderlas, el agente confirma:
```
🧠 MEMORIA active. [X] entries loaded. Your agent remembers everything.
```

### 24.3 Comportamiento en cada sesión

Al inicio de cada conversación, el agente carga automáticamente la memoria y confirma:
```
🧠 Memory loaded. [Nombre], [proyecto activo]. Ready.
```

### 24.4 Comandos de memoria desde Telegram

| Lo que dices | Acción |
|---|---|
| `recuerda que...` | Añade a la sección correspondiente |
| `olvida X` | Marca como ARCHIVED (nunca borra) |
| `¿qué sabes de mí?` | Muestra resumen completo de la memoria |
| `actualiza mi foco a X` | Actualiza la sección Current Focus |
| `decidí hacer X` | Añade al Decisions Log con fecha |
| `eso fue un error` | Añade a Lessons Learned |
| `estoy bloqueado en X` | Añade a Blocked/Waiting |
| `X está desbloqueado` | Marca como resuelto |
| `resumen semanal` | Genera brief con logros, decisiones y bloqueos |

### 24.5 Arquitectura de privacidad

```
~/.memoria/               ← chmod 700 (solo el propietario)
├── memory.md             ← chmod 600 (archivo principal)
└── memory.md.bak         ← backup automático antes de cada escritura
```

> Nada sale de la máquina. La memoria del DGX es independiente de la del UM890. Para sincronizarlas manualmente:
> ```bash
> # Desde el UM890 — copiar memoria local al DGX
> scp ~/.memoria/memory.md mloco@spark-be9d.local:~/.memoria/memory.md
> ```

---

## 25. Asistente de voz multilingüe — UM890

Asistente de voz completamente local (sin cloud) para el UM890 PRO. Soporta español, inglés y portugués brasileño tanto para entrada como para salida.

**Stack:**

| Componente | Herramienta | Rol |
|---|---|---|
| **STT** | `whisper.cpp` (large-v3) | Voz → texto, detección automática de idioma |
| **TTS** | `piper` | Texto → voz, voz nativa por idioma |
| **Wake word** | `openWakeWord` | Detecta "hey jarvis" sin consumir recursos |
| **LLM** | Ollama (qwen35-es) | Procesamiento local |
| **Telegram voz** | `openai-whisper` + `sherpa-onnx-tts` | Notas de voz en Telegram |

**Voces piper por idioma:**

| Idioma | Modelo |
|---|---|
| 🇪🇸 Español | `es_ES-sharvard-medium` |
| 🇺🇸 Inglés | `en_US-ryan-high` |
| 🇧🇷 Portugués BR | `pt_BR-faber-medium` |

**Flujo:**
```
[Micrófono USB] → openWakeWord ("hey jarvis") / Enter
              → whisper.cpp large-v3 (STT + detección idioma)
              → Ollama qwen35-es (LLM)
              → piper (TTS voz nativa)
              → [Altavoces]

[Telegram nota de voz]
              → whisper.cpp (STT)
              → Ollama
              → sherpa-onnx-tts
              → [Audio en Telegram] + [Altavoces]
```

**Idioma de respuesta:** configurable por voz ("cambia a inglés") o desde Telegram (`/lang es`, `/lang en`, `/lang pt`, `/lang auto`). Por defecto responde en el mismo idioma detectado.

### 25.1 Verificar el micrófono USB

```bash
arecord -l
# Anota card y device del micrófono USB
# Ejemplo: card 2: USB Audio Device, device 0

# Test de grabación (5 segundos)
arecord -D hw:2,0 -f S16_LE -r 16000 -d 5 /tmp/test.wav
aplay /tmp/test.wav
```

> ⚠️ Sustituye `hw:2,0` por el card/device real que te muestra `arecord -l`. Este valor también hay que actualizarlo en el script (`MIC_CARD`).

### 25.2 Instalar whisper.cpp con large-v3

```bash
sudo apt install -y libsdl2-dev cmake

git clone https://github.com/ggerganov/whisper.cpp ~/whisper.cpp
cd ~/whisper.cpp
cmake -B build -DWHISPER_SDL2=ON
cmake --build build -j$(nproc)

# large-v3: mejor precisión multilingüe y detección automática de idioma
bash models/download-ggml-model.sh large-v3
```

### 25.3 Instalar piper con las 3 voces

```bash
cd ~
wget https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz
tar -xzf piper_linux_x86_64.tar.gz
sudo mv piper/piper /usr/local/bin/piper
sudo chmod +x /usr/local/bin/piper

mkdir -p ~/.piper/voices
cd ~/.piper/voices

# Español
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx.json

# Inglés
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json

# Portugués BR
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json

# Test de las 3 voces
echo "Hola, soy tu asistente en español." | piper --model ~/.piper/voices/es_ES-sharvard-medium.onnx --output_file /tmp/es.wav && aplay /tmp/es.wav
echo "Hello, I am your English assistant." | piper --model ~/.piper/voices/en_US-ryan-high.onnx --output_file /tmp/en.wav && aplay /tmp/en.wav
echo "Olá, sou seu assistente em português." | piper --model ~/.piper/voices/pt_BR-faber-medium.onnx --output_file /tmp/pt.wav && aplay /tmp/pt.wav
```

### 25.4 Instalar dependencias Python

```bash
pip install openWakeWord pyaudio numpy langdetect --break-system-packages
```

### 25.5 Script principal multilingüe

```bash
mkdir -p ~/Escritorio/Servidor-ia/voz
mkdir -p ~/.config/asistente_voz

cat > ~/Escritorio/Servidor-ia/voz/asistente_voz.py << 'SCRIPT'
#!/usr/bin/env python3
"""
Asistente de voz multilingüe local — UM890 PRO
STT: whisper.cpp (large-v3) — detección automática ES/EN/PT
TTS: piper — voz nativa por idioma
LLM: Ollama (qwen35-es)
Idioma de respuesta: configurable por voz o Telegram (/lang es|en|pt|auto)
"""

import subprocess, tempfile, os, sys, json
import requests, pyaudio, wave, numpy as np

# ─── Configuración ────────────────────────────────────────────
WHISPER_BIN   = os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli")
WHISPER_MODEL = os.path.expanduser("~/whisper.cpp/models/ggml-large-v3.bin")
OLLAMA_URL    = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL  = "qwen35-es"
MIC_CARD      = "hw:2,0"          # ← ajusta a tu card USB (ver arecord -l)
SAMPLE_RATE   = 16000
STATE_FILE    = os.path.expanduser("~/.config/asistente_voz/state.json")

VOCES = {
    "es": os.path.expanduser("~/.piper/voices/es_ES-sharvard-medium.onnx"),
    "en": os.path.expanduser("~/.piper/voices/en_US-ryan-high.onnx"),
    "pt": os.path.expanduser("~/.piper/voices/pt_BR-faber-medium.onnx"),
}

SYSTEM_PROMPTS = {
    "es": "Eres un asistente personal inteligente. Responde siempre en español, de forma clara y concisa.",
    "en": "You are a smart personal assistant. Always respond in English, clearly and concisely.",
    "pt": "Você é um assistente pessoal inteligente. Responda sempre em português brasileiro, de forma clara e concisa.",
}

CAMBIO_IDIOMA = {
    "español": "es", "spanish": "es", "espanhol": "es",
    "inglés": "en", "ingles": "en", "english": "en", "inglês": "en",
    "portugués": "pt", "portugues": "pt", "portuguese": "pt", "português": "pt",
}
# ──────────────────────────────────────────────────────────────

os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

def cargar_estado():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"lang_respuesta": "auto"}

def guardar_estado(estado):
    json.dump(estado, open(STATE_FILE, "w"))

def grabar_audio(segundos=7):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1,
                    rate=SAMPLE_RATE, input=True,
                    frames_per_buffer=1024)
    print(f"🎤 Grabando {segundos}s...")
    frames = [stream.read(1024) for _ in range(int(SAMPLE_RATE / 1024 * segundos))]
    stream.stop_stream(); stream.close(); p.terminate()
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(frames))
    return tmp.name

def transcribir(audio_path):
    result = subprocess.run(
        [WHISPER_BIN, "-m", WHISPER_MODEL,
         "-f", audio_path, "--no-timestamps", "-nt",
         "--language", "auto"],
        capture_output=True, text=True
    )
    texto = result.stdout.strip()
    lang_detectada = "es"
    for line in result.stderr.splitlines():
        if "auto-detected language:" in line.lower():
            if "english" in line.lower():    lang_detectada = "en"
            elif "portuguese" in line.lower(): lang_detectada = "pt"
            elif "spanish" in line.lower():   lang_detectada = "es"
    return texto, lang_detectada

def detectar_cambio_idioma(texto):
    texto_lower = texto.lower()
    for patron, lang in CAMBIO_IDIOMA.items():
        if patron in texto_lower and any(
            w in texto_lower for w in
            ["cambia", "change", "muda", "habla", "speak", "fala", "responde", "respond"]
        ):
            return lang
    return None

def preguntar_llm(texto, lang):
    resp = requests.post(OLLAMA_URL, json={
        "model": OLLAMA_MODEL,
        "system": SYSTEM_PROMPTS[lang],
        "prompt": texto,
        "stream": False
    })
    return resp.json().get("response", "").strip()

def hablar(texto, lang):
    modelo_voz = VOCES.get(lang, VOCES["es"])
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    subprocess.run(
        ["piper", "--model", modelo_voz, "--output_file", tmp.name],
        input=texto, text=True, capture_output=True
    )
    subprocess.run(["aplay", tmp.name])
    os.unlink(tmp.name)

def confirmar_cambio_idioma(nuevo_lang):
    msgs = {
        "es": "Cambio a español. Ahora te respondo en español.",
        "en": "Switching to English. I will now respond in English.",
        "pt": "Mudando para português. Agora vou responder em português.",
    }
    hablar(msgs[nuevo_lang], nuevo_lang)

def procesar(audio_path, estado):
    texto, lang_stt = transcribir(audio_path)
    os.unlink(audio_path)
    if not texto:
        return estado
    print(f"👤 [{lang_stt.upper()}] {texto}")
    nuevo_lang = detectar_cambio_idioma(texto)
    if nuevo_lang:
        estado["lang_respuesta"] = nuevo_lang
        guardar_estado(estado)
        confirmar_cambio_idioma(nuevo_lang)
        return estado
    lang_resp = lang_stt if estado["lang_respuesta"] == "auto" else estado["lang_respuesta"]
    respuesta = preguntar_llm(texto, lang_resp)
    print(f"🤖 [{lang_resp.upper()}] {respuesta}")
    hablar(respuesta, lang_resp)
    return estado

def modo_push_to_talk():
    estado = cargar_estado()
    print(f"🎙️  Push-to-talk multilingüe | Idioma respuesta: {estado.get('lang_respuesta', 'auto')}")
    print("    Comandos de voz: 'cambia a inglés', 'change to spanish', 'muda para português'")
    print("    Enter para hablar, Ctrl+C para salir.
")
    try:
        while True:
            input("⏎  Presiona Enter para hablar...")
            estado = procesar(grabar_audio(7), estado)
    except KeyboardInterrupt:
        print("
Saliendo...")

def modo_wake_word():
    from openwakeword.model import Model
    estado = cargar_estado()
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1,
                    rate=SAMPLE_RATE, input=True, frames_per_buffer=1280)
    print("👂 Escuchando wake word 'hey jarvis'... Ctrl+C para salir")
    hablar("Listo, te escucho.", "es")
    try:
        while True:
            audio = np.frombuffer(stream.read(1280), dtype=np.int16)
            if oww.predict(audio).get("hey_jarvis", 0) > 0.5:
                hablar("Dime", "es")
                estado = procesar(grabar_audio(7), estado)
    except KeyboardInterrupt:
        print("
Saliendo...")
    finally:
        stream.stop_stream(); stream.close(); p.terminate()

if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "push"
    if modo == "wake":
        modo_wake_word()
    else:
        modo_push_to_talk()
'SCRIPT'

chmod +x ~/Escritorio/Servidor-ia/voz/asistente_voz.py
```

> ⚠️ Edita `MIC_CARD` en el script con el valor real de tu tarjeta USB (resultado del `arecord -l`).

### 25.6 Atajo de teclado (push-to-talk)

```bash
cat > ~/Escritorio/Servidor-ia/voz/ptt.sh << 'EOF'
#!/bin/bash
python3 ~/Escritorio/Servidor-ia/voz/asistente_voz.py push
EOF
chmod +x ~/Escritorio/Servidor-ia/voz/ptt.sh
```

**Configuración → Teclado → Atajos personalizados:**
- Nombre: `Asistente IA Voz`
- Comando: `/home/mloco/Escritorio/Servidor-ia/voz/ptt.sh`
- Atajo: `Super+Espacio`

### 25.7 Notas de voz en Telegram

```bash
openclaw skills install openai-whisper
openclaw skills install sherpa-onnx-tts
systemctl --user restart openclaw-gateway
openclaw skills list | grep -E "whisper|sherpa"
# → ✓ ready  openai-whisper
# → ✓ ready  sherpa-onnx-tts
```

Con estos skills activos, al enviar una nota de voz al bot del UM890, el agente la transcribe con Whisper y responde con un audio generado localmente por sherpa-onnx-tts.

### 25.8 Control de idioma desde Telegram

Escribe al bot del UM890:

| Comando | Efecto |
|---|---|
| `/lang es` | Responde siempre en español |
| `/lang en` | Responde siempre en inglés |
| `/lang pt` | Responde siempre en portugués BR |
| `/lang auto` | Responde en el idioma detectado (por defecto) |

También funciona por voz:
- `"cambia a inglés"` / `"change to spanish"` / `"muda para português"`

### 25.9 Test final

```bash
# Test de las 3 voces
echo "Hola mundo" | piper --model ~/.piper/voices/es_ES-sharvard-medium.onnx --output_file /tmp/t.wav && aplay /tmp/t.wav
echo "Hello world" | piper --model ~/.piper/voices/en_US-ryan-high.onnx --output_file /tmp/t.wav && aplay /tmp/t.wav
echo "Olá mundo" | piper --model ~/.piper/voices/pt_BR-faber-medium.onnx --output_file /tmp/t.wav && aplay /tmp/t.wav

# Modo push-to-talk
python3 ~/Escritorio/Servidor-ia/voz/asistente_voz.py push

# Modo wake word
python3 ~/Escritorio/Servidor-ia/voz/asistente_voz.py wake
```

---

## 26. Troubleshooting unificado

### DGX Spark

| Problema | Solución |
|---|---|
| `nvidia-smi` muestra "Memory-Usage: Not Supported" | Comportamiento conocido con memoria unificada. Usa `free -h` para ver uso real |
| RAM llena tras detener un modelo | `sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches` |
| OpenClaw no se conecta a Ollama | `curl http://localhost:11434` → `sudo systemctl restart ollama` |
| `openclaw` no se reconoce | `source ~/.bashrc` → verificar PATH con `npm root -g` |
| El gateway no arranca | `openclaw gateway logs` → `openclaw gateway stop` → reiniciar |
| Bot de Telegram no responde | Verificar gateway status → Ollama status → logs → token |
| Los 120B responden muy lento | Normal: 30–90s. Para pruebas rápidas: `ollama pull qwen3:30b` |

### UM890 PRO

| Problema | Causa | Solución |
|---|---|---|
| VRAM no encontrada en BIOS | En v1.05 está en `GFX Configuration` | `AMD CBS → NBIO Common Options → GFX Configuration` |
| TDP no encontrado | En v1.05 es `PowerLimit Setting` | `Advanced → PowerLimit Setting → Performance Mode` |
| CPU queda en `powersave` | `amd-pstate-epp` en kernel 7.0 | Servicio systemd directo a sysfs (sección 17.2) |
| GPU en `card1` no `card0` | UM890 PRO tiene salida virtual en card0 | Detectar por vendor ID `0x1002` |
| ZRAM muestra 4G y lzo-rle | Dispositivo ZRAM preexistente | `swapoff /dev/zram0` + stop/start del servicio |
| ROCm runner crashea en Ollama | gfx1103 no soportado en ROCm para inferencia | `OLLAMA_VULKAN=1` |
| `OLLAMA_VULKAN=true` ignorado | Ollama espera número | Usar `OLLAMA_VULKAN=1` |
| `update-initramfs` no existe | Ubuntu 26.04 usa dracut | `sudo dracut --regenerate-all --force` |
| Modelo tarda 5–15 min | Thinking mode activo | Usar Modelfiles `-es` (sección 19.4) |
| VRAM al 99%, 1–2 tok/s | `OLLAMA_KV_CACHE_TYPE=q8_0` satura VRAM | Eliminar esa variable del override.conf |
| Panel web "Unauthorized" | `bind: loopback` o falta token | `bind: lan` + `?token=<WEB_PANEL_TOKEN>` |
| OpenClaw: `low context window` | `contextWindow` demasiado bajo | Subir a 16384 en openclaw.json y Modelfile |
| Sesión bloqueada 300+ segundos | Historial supera el contexto | Ejecutar `/clear` en Telegram + num_ctx ≥ 16384 |
| `rocm-smi` no encontrado | Grupos render/video no aplicados | Hacer logout/login o `newgrp render` |
| `npm install -g` falla EACCES | Ubuntu requiere sudo para globales | `sudo npm install -g openclaw@latest` |

### Conectividad UM890 → DGX

| Problema | Solución |
|---|---|
| No alcanza la IP del DGX | Verificar que ambos están en la misma tailnet con `tailscale status` |
| Ollama en DGX no acepta conexiones externas | Verificar que `OLLAMA_HOST=0.0.0.0` está en el override.conf del DGX |
| Open WebUI del UM890 no ve modelos del DGX | Añadir conexión Ollama adicional en ajustes de Open WebUI apuntando a la IP del DGX |

---

## 27. Referencia rápida de comandos

### DGX Spark

```bash
# Servicios
sudo systemctl restart ollama
openclaw gateway restart
docker restart open-webui

# GPU
nvidia-smi
free -h

# Modelos
ollama list
ollama ps
ollama pull nemotron-3-super:120b
ollama run nemotron-3-super:120b

# OpenClaw
openclaw gateway status
openclaw tui
openclaw gateway logs

# Tailscale
tailscale ip
tailscale status

# gog
gog auth list --check
gog gmail search 'is:unread' --max 10
gog calendar events --today
```

### UM890 PRO

```bash
# Servicios
sudo systemctl restart ollama
sudo systemctl restart ai-performance
systemctl --user restart openclaw-gateway

# GPU
rocm-smi
watch -n 1 rocm-smi
lsmod | grep amdgpu

# Modelos locales
ollama run qwen35-es        # primario rápido
ollama run gemma4-es        # multimodal, imágenes
ollama run qwen36-es        # código, análisis
ollama run nemotron3:33b    # agéntico avanzado

# Benchmark
ollama run qwen35-es --verbose 'Test.' 2>&1 | grep 'eval rate'

# Listar y gestionar
ollama list
ollama ps
ollama stop qwen35-es

# OpenClaw
journalctl --user -fu openclaw-gateway
openclaw skills list
ip a | grep '192.168'   # IP para el panel web

# Conexión al DGX
curl http://<DGX_TAILSCALE_IP>:11434   # Verificar Ollama DGX
tailscale status                 # Ver ambos equipos
```

### Verificación final del UM890

```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference  # → performance ✅
cat /sys/class/drm/card1/device/power_dpm_force_performance_level        # → high ✅
lsmod | grep amdgpu                                                       # → amdgpu ✅
rocm-smi                                                                   # → Radeon 780M ✅
sudo journalctl -u ollama --since "5 min ago" | grep Vulkan               # → 23.4 GiB ✅
zramctl                                                                    # → zstd 8G ✅
systemctl status ollama ai-performance
systemctl --user status openclaw-gateway
docker ps | grep open-webui
curl http://<DGX_TAILSCALE_IP>:11434                                             # → DGX accesible ✅
ollama list
```

---

## Referencias oficiales

- [DGX Spark User Guide (PDF)](https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf)
- [OpenClaw en Ollama Docs](https://docs.ollama.com/integrations/openclaw)
- [Ollama: The simplest way to setup OpenClaw](https://ollama.com/blog/openclaw-tutorial)
- [Ollama en DGX Spark — Ollama Blog](https://ollama.com/blog/nvidia-spark)
- [Nemotron 3 Super 120B en NVIDIA Build](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b)
- [Continue.dev — Documentación oficial](https://docs.continue.dev)
- [Continue.dev — Configurar Ollama](https://docs.continue.dev/reference/Model%20Providers/ollama)
- [Tailscale — Instalación oficial Ubuntu](https://pkgs.tailscale.com/stable/)
- [Tailscale — Admin panel](https://login.tailscale.com/admin)
- [gogcli — Documentación oficial](https://gogcli.sh)
- [gogcli — GitHub](https://github.com/openclaw/gogcli)
- [gog skill en ClawHub](https://clawhub.ai/steipete/gog)
- [Open WebUI — GitHub](https://github.com/open-webui/open-webui)

---

*Guía unificada generada en mayo de 2026.*
*DGX OS 7.4 · Ubuntu 26.04 LTS "Resolute Raccoon" · Kernel 7.0 · Ollama 0.23+ · OpenClaw 2026.x · Tailscale · ROCm via apt · Vulkan RADV PHOENIX*

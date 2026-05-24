# Guía Completa: DGX Spark → Ollama → Nemotron 3 Super 120B + GPT-OSS 120B → OpenClaw → Telegram

> **Referencia oficial:** Esta guía sigue el [DGX Spark User Guide](https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf) de NVIDIA y la documentación oficial de [OpenClaw en Ollama](https://docs.ollama.com/integrations/openclaw).

---

## Índice

1. [Hardware y requisitos previos](#1-hardware-y-requisitos-previos)
2. [Primer encendido y configuración inicial (OOBE)](#2-primer-encendido-y-configuración-inicial-oobe)
3. [Acceso remoto con NVIDIA Sync](#3-acceso-remoto-con-nvidia-sync)
4. [Actualización del sistema](#4-actualización-del-sistema)
5. [Configuración de Docker + NVIDIA Container Runtime](#5-configuración-de-docker--nvidia-container-runtime)
6. [Instalación y configuración de Ollama](#6-instalación-y-configuración-de-ollama)
7. [Descarga de los modelos 120B](#7-descarga-de-los-modelos-120b)
8. [Instalación y configuración de OpenClaw](#8-instalación-y-configuración-de-openclaw)
9. [Configuración del bot de Telegram](#9-configuración-del-bot-de-telegram)
10. [Verificación y pruebas](#10-verificación-y-pruebas)
11. [Gestión del stack (comandos útiles)](#11-gestión-del-stack-comandos-útiles)
12. [Troubleshooting](#12-troubleshooting)
13. [Acceso remoto desde otro equipo](#13-acceso-remoto-usar-los-modelos-del-dgx-spark-desde-otro-equipo)
    - 13.1 [Preparación en el DGX Spark](#131-preparación-en-el-dgx-spark-obligatorio-para-ambas-opciones)
    - 13.2 [Opción A — OpenClaw en el equipo remoto](#opción-a--openclaw-en-el-equipo-remoto)
    - 13.3 [Opción B — VS Code con Continue.dev](#opción-b--vs-code-con-continuedev)
    - 13.4 [Acceso seguro con Tailscale](#132-acceso-seguro-desde-cualquier-lugar-con-tailscale)
    - 13.5 [Arquitectura ampliada con Tailscale](#133-arquitectura-ampliada-con-tailscale)
14. [Acceso a Google Workspace desde el agente (gog)](#14-acceso-a-google-workspace-desde-el-agente-gog)
    - 14.1 [Google Cloud: proyecto, APIs y credenciales OAuth](#parte-1--google-cloud-proyecto-apis-y-credenciales-oauth)
    - 14.2 [Instalar gogcli en el DGX Spark](#parte-2--instalar-gogcli-en-el-dgx-spark)
    - 14.3 [Autenticación OAuth via SSH tunnel](#parte-3--autenticación-oauth-ssh-tunnel)
    - 14.4 [Activar el skill gog en OpenClaw](#parte-4--activar-el-skill-gog-en-openclaw)
    - 14.5 [Usar gog desde el agente](#parte-5--usar-gog-desde-el-agente)

---

## 1. Hardware y requisitos previos

### Especificaciones del DGX Spark

| Componente | Detalle |
|---|---|
| Superchip | NVIDIA GB10 Grace Blackwell |
| CPU | 20 núcleos ARM (Grace) |
| Memoria unificada | 128 GB LPDDR5x (CPU + GPU comparten el mismo pool) |
| Almacenamiento | 4 TB NVMe SSD (Founders Edition) |
| Red | ConnectX-7, hasta 200 Gbps |
| OS preinstalado | DGX OS 7.x (Ubuntu 24.04 LTS base) |
| Driver NVIDIA | 580.x |
| CUDA | 13.0.x |
| AI Performance | 1 PetaFLOP (FP4) |

### Lo que necesitas antes de empezar

- Cable Ethernet (muy recomendado para la descarga de ~150 GB de modelos)
- Monitor HDMI **o** acceso SSH desde otro equipo en la misma red
- Cuenta de Telegram para crear el bot
- Tiempo estimado: ~45 minutos activos + 30-60 minutos de descarga de modelos

---

## 2. Primer encendido y configuración inicial (OOBE)

### 2.1 Conexión física

1. Usa **únicamente el adaptador de corriente incluido** — otro adaptador reduce el rendimiento máximo.
2. Conecta un cable Ethernet o, si prefieres Wi-Fi, tenlo a mano durante el setup.
3. Conecta monitor HDMI, teclado y ratón USB (o configura todo remotamente en el paso 3).
4. Pulsa el botón de encendido.

### 2.2 Asistente de primera configuración (OOBE)

Al primer arranque el DGX Spark lanza automáticamente el asistente de configuración:

**a) Idioma y teclado**
Selecciona tu idioma e idioma del teclado.

**b) Red**
Conecta a tu red Wi-Fi o confirma que el Ethernet fue detectado. El hostname por defecto está en el sticker de la caja: `spark-XXXX.local`

**c) Usuario administrador**
- Nombre de usuario (ej. `manoel`)
- Contraseña segura — guárdala, es necesaria para `sudo` y para SSH

**d) SSH**
El sistema activa SSH automáticamente. Desde otro equipo en tu red puedes conectarte con:
```bash
ssh manoel@spark-XXXX.local
```

**e) Finalizar**
El sistema reinicia. El DGX Dashboard queda disponible en: `http://spark-XXXX.local`

> El hostname exacto (`spark-XXXX`) está impreso en la guía rápida incluida en la caja y en el sticker inferior del dispositivo.

### 2.3 Verificar el estado del sistema

Abre una terminal (local o SSH) y ejecuta:

```bash
# Versión del OS
head -n 2 /etc/os-release
# Esperado: Ubuntu 24.04

# GPU y driver
nvidia-smi
# Esperado: NVIDIA GB10, driver 580.x

# CUDA
nvcc --version
# Esperado: 13.0.x

# Docker (preinstalado)
docker info --format '{{.ServerVersion}}'
# Esperado: 28.x o superior
```

---

## 3. Acceso remoto con NVIDIA Sync

NVIDIA Sync es la app oficial de escritorio (macOS / Windows) que gestiona automáticamente el túnel SSH al DGX Spark.

### 3.1 Instalación

Descarga desde: https://www.nvidia.com/en-us/products/workstations/dgx-spark/

### 3.2 Conectar el Spark

1. Abre NVIDIA Sync → **Add Spark**
2. Ingresa el hostname (`spark-XXXX.local`) o la IP local
3. Ingresa usuario y contraseña del paso 2.2c
4. NVIDIA Sync configura autenticación por clave SSH automáticamente

### 3.3 Aplicaciones disponibles desde NVIDIA Sync

- **Terminal** con conexión SSH directa
- **DGX Dashboard** (gestión del sistema, JupyterLab)
- Puedes añadir el Dashboard de OpenClaw manualmente apuntando al puerto `18789`

---

## 4. Actualización del sistema

> **Método oficial recomendado por NVIDIA: siempre usa el DGX Dashboard para las actualizaciones del sistema.** El Dashboard garantiza la cadena de actualización probada y certificada para DGX OS, drivers, CUDA y firmware del GB10.

### 4.1 Actualizar vía DGX Dashboard (recomendado)

1. Abre el DGX Dashboard en tu navegador:
   - **Local:** Haz clic en "Show Apps" (esquina inferior izquierda del escritorio Ubuntu) → DGX Dashboard
   - **Remoto vía NVIDIA Sync:** Haz clic en el botón "DGX Dashboard" dentro de NVIDIA Sync
   - **Remoto vía SSH tunnel manual:** ejecuta en tu equipo `ssh -L 11000:localhost:11000 manoel@spark-XXXX.local` y abre `http://localhost:11000`

2. En el Dashboard, busca la sección **Updates / System Updates**
3. Haz clic en **Check for Updates**
4. Si hay actualizaciones disponibles, haz clic en **Apply Updates**
5. El sistema reiniciará automáticamente si es necesario

> Asegúrate de tener fuente de alimentación estable durante la actualización y de no tener cargas de trabajo activas.

### 4.2 Instalar dependencias adicionales (solo paquetes de usuario)

Una vez que el sistema esté actualizado vía Dashboard, instala las herramientas de desarrollo que necesitará el stack. Estas **no afectan al OS base ni a los drivers**:

```bash
sudo apt install -y \
  git curl wget \
  build-essential \
  ca-certificates \
  python3 python3-pip
```

> `apt dist-upgrade` está reservado para usuarios avanzados o cuando el Dashboard no está disponible. Para uso normal, el Dashboard es siempre la vía correcta y más segura.

---

## 5. Configuración de Docker + NVIDIA Container Runtime

El DGX Spark incluye Docker preinstalado, pero requiere configuración adicional para que los contenedores accedan correctamente a la GPU.

### 5.1 Registrar el runtime de NVIDIA con Docker

```bash
sudo nvidia-ctk runtime configure --runtime=docker
```

### 5.2 Configurar el modo cgroup (específico para DGX Spark)

Este ajuste es necesario para la arquitectura de memoria unificada del GB10:

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

Hazlo **antes** de reiniciar Docker, para que el nuevo grupo quede activo en el mismo paso:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

> Si intentas usar `docker` antes de este paso verás el error `permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock`. Es normal — simplemente ejecuta los dos comandos de arriba y continúa.

### 5.4 Reiniciar Docker y verificar

```bash
sudo systemctl restart docker

# Verificar que la GPU es visible desde un contenedor
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

Deberías ver la GPU GB10 en la salida de `nvidia-smi` dentro del contenedor.

---

## 6. Instalación y configuración de Ollama

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

**Tamaño:** ~87 GB | **Tiempo estimado:** 15-30 min

### 7.2 GPT-OSS 120B

Modelo alternativo con cuantización MXFP4, optimizado para el GB10:

```bash
ollama pull gpt-oss:120b
```

**Tamaño:** ~65 GB | **Tiempo estimado:** 10-20 min

### 7.3 Pre-cargar los modelos en memoria

Elimina la latencia de cold-start en la primera interacción:

```bash
# Pre-cargar Nemotron
ollama run nemotron-3-super:120b
# Cuando aparezca el prompt >>> escribe /bye y Enter

# Pre-cargar GPT-OSS
ollama run gpt-oss:120b
# Cuando aparezca el prompt >>> escribe /bye y Enter
```

### 7.4 Verificar modelos disponibles

```bash
ollama list
```

Salida esperada:
```
NAME                        ID              SIZE      MODIFIED
nemotron-3-super:120b       95acc78b3ffd    86 GB     hace X min
gpt-oss:120b                a97757631e2b    65 GB     hace X min
```

### 7.5 Nota: RAM tras detener un modelo

El DGX Spark puede mantener la RAM llena al detener modelos (comportamiento conocido). Para liberarla:

```bash
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

---

## 8. Instalación y configuración de OpenClaw

OpenClaw se instala directamente vía `npm` **sin sudo**, en el directorio del usuario. Esto evita conflictos de permisos con el sistema y es la práctica recomendada para herramientas de desarrollo.

### 8.1 Prerrequisito: Node.js

OpenClaw requiere Node.js 22.x. Instálalo con `sudo` (es un paquete del sistema, no una herramienta de usuario):

```bash
# Verificar si ya existe
node --version

# Si no está instalado:
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

### 8.2 Configurar npm para instalaciones de usuario (sin sudo)

Este paso configura npm para instalar paquetes globales en tu directorio personal, evitando la necesidad de `sudo` y cualquier conflicto con el sistema:

```bash
# Crear directorio de globales del usuario
mkdir -p ~/.npm-global

# Apuntar npm a ese directorio
npm config set prefix '~/.npm-global'

# Añadir al PATH
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

Verificar que quedó bien configurado:

```bash
npm config get prefix
# Debe mostrar: /home/manoel/.npm-global
```

### 8.3 Instalar OpenClaw

```bash
npm install -g openclaw
```

Verificar la instalación:

```bash
openclaw --version
```

### 8.4 Onboarding: conectar OpenClaw con Ollama

```bash
openclaw onboard
```

El wizard interactivo te pedirá en orden:

**1 — Proveedor de inferencia**
Selecciona **Ollama** de la lista y confirma la URL por defecto:
```
Ollama base URL: http://127.0.0.1:11434/v1
```
Presiona Enter para aceptar. OpenClaw testea la conexión automáticamente.

**2 — Modelo principal**
El wizard lista los modelos disponibles en tu Ollama. Selecciona:
```
nemotron-3-super:120b
```

> OpenClaw requiere un context window de al menos 64k tokens. Ambos modelos de 120B tienen 128k — ideales para esta tarea.

**3 — Canales de mensajería**
Por ahora puedes omitir este paso (se configura en la sección 9):
```
Configure channels? [Y/n]: n
```

**4 — Búsqueda web y fetch**
Activa el plugin integrado:
```
Enable web search and fetch? [Y/n]: Y
```

**5 — Finalizar**
El wizard confirma la configuración y muestra:
```
✓ OpenClaw setup complete
✓ Gateway running at http://127.0.0.1:18789
✓ Ready to chat
```

### 8.5 Arrancar el gateway

```bash
openclaw gateway start
```

Para abrirlo en background y continuar usando el terminal:

```bash
openclaw gateway start --background
```

Verificar que está activo:

```bash
openclaw gateway status
```

### 8.6 Configuración avanzada vía JSON (opcional)

Para registrar ambos modelos y poder alternar entre ellos desde el Web UI:

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

Tras editar, reinicia el gateway:

```bash
openclaw gateway restart
```

---

## 9. Configuración del bot de Telegram

### 9.1 Crear el bot con @BotFather

1. Abre Telegram y busca `@BotFather`
2. Envía el comando `/newbot`
3. Asigna un **nombre** (ej. `Mi Asistente DGX`)
4. Asigna un **username** (debe terminar en `bot`, ej. `mi_dgx_spark_bot`)
5. @BotFather te entrega el **token API**:
   ```
   1234567890:ABCdefGhIJKlmNOpQRSTuvWXyz
   ```
6. Guarda este token de forma segura.

### 9.2 Conectar Telegram a OpenClaw

```bash
openclaw configure --section channels
```

El wizard interactivo te pedirá:

1. Selecciona **Telegram** de la lista de plataformas
2. Ingresa el **bot token** obtenido del @BotFather
3. Selecciona **Finished** para guardar la configuración

El gateway se reinicia automáticamente con Telegram activo.

### 9.3 Emparejar tu cuenta de Telegram con el bot

1. Abre Telegram y busca tu bot por el username que configuraste
2. Envía cualquier mensaje al bot
3. El bot responde con un **código de emparejamiento**:
   ```
   OpenClaw: access not configured.
   Your Telegram user id: 123456789
   Pairing code: XXXX-YYYY
   ```
4. Ingresa ese código en el Web UI de OpenClaw: `http://127.0.0.1:18789`
5. Después del emparejamiento, envía un nuevo mensaje. Recibirás una respuesta generada por el modelo.

> **Latencia esperada:** Los modelos de 120B en inferencia local toman **30-90 segundos** por respuesta. Esto es completamente normal.

### 9.4 Acceder al Web UI de OpenClaw

**Localmente (o mediante NVIDIA Sync):**
```
http://127.0.0.1:18789
```

**Desde otro equipo en la misma red, por SSH tunnel:**

En tu equipo remoto:
```bash
ssh -L 18789:127.0.0.1:18789 manoel@<IP-del-Spark>
```

Luego abre en el navegador: `http://127.0.0.1:18789`

---

## 10. Verificación y pruebas

### 10.1 Verificar el gateway

```bash
openclaw gateway status
```

### 10.2 Probar el agente desde el TUI

```bash
openclaw tui
```

Escribe un mensaje y espera la respuesta. Presiona `Ctrl+C` para salir.

### 10.3 Probar en modo no-interactivo

```bash
openclaw agent --agent main --local -m "¿Qué modelos tienes disponibles?" --session-id test
```

### 10.4 Verificar Telegram

Envía un mensaje al bot desde Telegram. Tras ~30-90 segundos, el bot responderá.

### 10.5 Probar los modelos directamente en Ollama

```bash
ollama ps                          # Ver modelos en ejecución
ollama run nemotron-3-super:120b "Di hola en 5 idiomas"
ollama run gpt-oss:120b "Di hola en 5 idiomas"
```

---

## 11. Gestión del stack (comandos útiles)

### Ollama

```bash
sudo systemctl status ollama       # Estado del servicio
sudo systemctl restart ollama      # Reiniciar
sudo systemctl stop ollama         # Detener
ollama list                        # Modelos descargados
ollama ps                          # Modelos en ejecución
ollama pull <modelo>               # Descargar modelo
ollama rm <modelo>                 # Eliminar modelo

# Liberar RAM tras detener modelos
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

### OpenClaw

```bash
openclaw onboard               # Reconfigurar proveedor y modelo
openclaw tui                   # Abrir interfaz de chat en terminal
openclaw gateway start         # Arrancar el gateway
openclaw gateway start --background  # Arrancar en background
openclaw gateway status        # Estado del gateway
openclaw gateway restart       # Reiniciar gateway
openclaw gateway stop          # Detener gateway
openclaw gateway logs          # Ver logs
openclaw configure --section channels   # Configurar Telegram/Slack/Discord
openclaw --version             # Versión instalada
npm update -g openclaw         # Actualizar OpenClaw
```

### Sistema

```bash
nvidia-smi                         # Estado GPU y drivers
free -h                            # Uso de memoria
df -h                              # Uso del disco
```

---

## 12. Troubleshooting

### OpenClaw no se conecta a Ollama

```bash
curl http://localhost:11434
sudo systemctl restart ollama
```

### RAM llena tras detener un modelo

```bash
sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches
```

### `openclaw` no se reconoce tras la instalación

```bash
source ~/.bashrc
# Verificar PATH de npm
npm root -g
```

### El gateway no arranca

```bash
openclaw gateway logs
openclaw gateway stop
ollama launch openclaw
```

### El bot de Telegram no responde

1. `openclaw gateway status` — verificar que el gateway está activo
2. `sudo systemctl status ollama` — verificar que Ollama corre
3. `openclaw gateway logs` — buscar errores
4. `openclaw configure --section channels` — reverificar el token

### `nvidia-smi` muestra "Memory-Usage: Not Supported"

Comportamiento conocido con la memoria unificada del DGX Spark. El sistema funciona correctamente. Usa `free -h` para ver el uso real.

### Los modelos de 120B responden muy lento

Es normal: 30-90 segundos por respuesta. Para pruebas rápidas usa un modelo más pequeño:

```bash
ollama pull qwen3:30b
ollama launch openclaw --model qwen3:30b
```

---

## 13. Acceso remoto: usar los modelos del DGX Spark desde otro equipo

El DGX Spark actúa como **servidor de inferencia**. Cualquier equipo en tu red local puede consumir los modelos via la API de Ollama sin necesidad de tener GPU ni modelos descargados localmente.

### 13.1 Preparación en el DGX Spark (obligatorio para ambas opciones)

Primero configura Ollama para aceptar conexiones externas:

```bash
# Crear el directorio de override de systemd
sudo mkdir -p /etc/systemd/system/ollama.service.d

# Configurar OLLAMA_HOST para escuchar en todas las interfaces
printf '[Service]\nEnvironment="OLLAMA_HOST=0.0.0.0"\n' | \
  sudo tee /etc/systemd/system/ollama.service.d/override.conf

# Aplicar cambios y reiniciar Ollama
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

Verificar que está escuchando correctamente:

```bash
curl http://0.0.0.0:11434
# Respuesta esperada: "Ollama is running"
```

Obtener la IP local del Spark (la necesitarás en el equipo remoto):

```bash
hostname -I | awk '{print $1}'
# Ejemplo de salida: 192.168.1.42
```

> A partir de aquí, todos los pasos siguientes se ejecutan en el **equipo remoto**, no en el Spark.

---

### Opción A — OpenClaw en el equipo remoto

El equipo remoto instala OpenClaw pero **no necesita Ollama ni los modelos** — la inferencia ocurre completamente en el DGX Spark.

#### A.1 Instalar Node.js en el equipo remoto

**macOS:**
```bash
brew install node
```

**Ubuntu/Debian:**
```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

**Windows:**
Descarga el instalador desde https://nodejs.org (versión LTS)

#### A.2 Configurar npm para instalaciones sin sudo (macOS/Linux)

```bash
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

En macOS con zsh:
```bash
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.zshrc
source ~/.zshrc
```

#### A.3 Instalar OpenClaw en el equipo remoto

```bash
npm install -g openclaw
openclaw --version
```

#### A.4 Onboarding apuntando al DGX Spark

```bash
openclaw onboard
```

Cuando el wizard pregunte la URL de Ollama, **cambia la URL por defecto** por la IP de tu Spark:

```
Ollama base URL: http://192.168.1.42:11434/v1
                              ↑
                   IP de tu DGX Spark
```

Selecciona el modelo:
```
Model: nemotron-3-super:120b
```

OpenClaw testea la conexión automáticamente. Si la conexión es exitosa, verás:
```
✓ Connected to Ollama at http://192.168.1.42:11434/v1
✓ Model nemotron-3-super:120b available
```

#### A.5 Arrancar el gateway en el equipo remoto

```bash
openclaw gateway start --background
```

Abre el Web UI en tu navegador:
```
http://127.0.0.1:18789
```

Desde aquí puedes chatear con los modelos del Spark exactamente igual que si fuera local — la inferencia ocurre en el DGX Spark y los resultados llegan por red.

#### A.6 Configurar Telegram en el equipo remoto (opcional)

Si quieres que el bot de Telegram de este equipo remoto también use los modelos del Spark:

```bash
openclaw configure --section channels
```

Sigue el mismo proceso que en la sección 9. Puedes usar el mismo bot de Telegram o crear uno nuevo con @BotFather.

> **Nota:** Si tienes OpenClaw corriendo tanto en el Spark como en el equipo remoto, cada instancia necesita su propio bot de Telegram (dos tokens distintos). Un mismo token no puede usarse en dos instancias simultáneas.

---

### Opción B — VS Code con Continue.dev

Continue.dev es la extensión open source más popular para usar modelos locales como asistente de código en VS Code. Se conecta directamente a la API de Ollama del Spark.

#### B.1 Instalar VS Code en el equipo remoto

Descarga desde: https://code.visualstudio.com

#### B.2 Instalar la extensión Continue.dev

1. Abre VS Code
2. Ve a **Extensions** (`Ctrl+Shift+X` / `Cmd+Shift+X`)
3. Busca `Continue`
4. Instala la extensión de **Continue.dev** (el autor es `Continue`)
5. Reinicia VS Code cuando lo pida

#### B.3 Abrir la configuración de Continue

Una vez instalada, aparece el icono de Continue en la barra lateral izquierda. Haz clic en él y luego:

1. Haz clic en el icono de **engranaje** (⚙) en la esquina inferior derecha del panel de Continue
2. Se abre el archivo `~/.continue/config.json`

#### B.4 Configurar Ollama apuntando al DGX Spark

Reemplaza el contenido del `config.json` con esta configuración:

```json
{
  "models": [
    {
      "title": "Nemotron 3 Super 120B (DGX Spark)",
      "provider": "ollama",
      "model": "nemotron-3-super:120b",
      "apiBase": "http://192.168.1.42:11434"
    },
    {
      "title": "GPT-OSS 120B (DGX Spark)",
      "provider": "ollama",
      "model": "gpt-oss:120b",
      "apiBase": "http://192.168.1.42:11434"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Nemotron 3 Super 120B (DGX Spark)",
    "provider": "ollama",
    "model": "nemotron-3-super:120b",
    "apiBase": "http://192.168.1.42:11434"
  },
  "embeddingsProvider": {
    "provider": "ollama",
    "model": "nomic-embed-text",
    "apiBase": "http://192.168.1.42:11434"
  },
  "contextProviders": [
    { "name": "code" },
    { "name": "docs" },
    { "name": "diff" },
    { "name": "terminal" },
    { "name": "problems" },
    { "name": "folder" },
    { "name": "codebase" }
  ],
  "slashCommands": [
    { "name": "edit", "description": "Edit selected code" },
    { "name": "comment", "description": "Write comments for the code" },
    { "name": "share", "description": "Export the current chat session" },
    { "name": "cmd", "description": "Generate a shell command" }
  ]
}
```

> Sustituye `192.168.1.42` por la IP real de tu DGX Spark en todos los campos `apiBase`.

Guarda el archivo (`Ctrl+S` / `Cmd+S`).

#### B.5 Instalar el modelo de embeddings en el Spark

El `config.json` anterior usa `nomic-embed-text` para la funcionalidad de búsqueda en el codebase. Descárgalo en el Spark:

```bash
# Ejecutar en el DGX Spark
ollama pull nomic-embed-text
```

#### B.6 Verificar la conexión en VS Code

1. Abre el panel de Continue (`Ctrl+Alt+J` / `Cmd+Alt+J`)
2. En el desplegable superior, selecciona **Nemotron 3 Super 120B (DGX Spark)**
3. Escribe un mensaje de prueba y envía
4. Tras 30-90 segundos verás la respuesta generada por el Spark

#### B.7 Usar Continue.dev en VS Code

Las funciones principales:

| Acción | Atajo |
|---|---|
| Abrir chat | `Ctrl+Alt+J` / `Cmd+Alt+J` |
| Explicar código seleccionado | Selecciona código → `Ctrl+L` / `Cmd+L` |
| Editar código con instrucción | Selecciona código → `Ctrl+I` / `Cmd+I` |
| Autocompletar (inline) | Escribe código → `Tab` para aceptar sugerencia |
| Buscar en el codebase | En el chat escribe `@codebase` + tu pregunta |

---

### 13.2 Acceso seguro desde cualquier lugar con Tailscale

Tailscale crea una red privada cifrada (basada en WireGuard) entre todos tus dispositivos. Una vez configurado, el DGX Spark y el equipo remoto se ven entre sí **directamente**, sin abrir puertos en el router ni configurar IP pública. Funciona también detrás de CGNAT.

#### Paso 1 — Crear una cuenta de Tailscale

Ve a https://tailscale.com y crea una cuenta gratuita. Puedes autenticarte con Google, Microsoft o GitHub.

El plan gratuito soporta hasta 100 dispositivos — más que suficiente para este uso.

#### Paso 2 — Instalar Tailscale en el DGX Spark

Ejecuta estos comandos en el DGX Spark (siguiendo el repositorio oficial para Ubuntu 24.04 Noble):

```bash
# Añadir la clave GPG oficial de Tailscale
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | \
  sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg > /dev/null

# Añadir el repositorio oficial de Tailscale
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | \
  sudo tee /etc/apt/sources.list.d/tailscale.list

# Instalar Tailscale
sudo apt update && sudo apt install -y tailscale
```

#### Paso 3 — Autenticar el DGX Spark en tu red Tailscale

```bash
sudo tailscale up
```

El terminal mostrará una URL para autenticar el dispositivo:

```
To authenticate, visit:
https://login.tailscale.com/a/XXXXXXXXXXXXXXX
```

Abre esa URL en tu navegador, inicia sesión en tu cuenta de Tailscale y haz clic en **Connect**. El Spark quedará registrado en tu red privada (tailnet).

#### Paso 4 — Habilitar inicio automático

```bash
sudo systemctl enable tailscaled
sudo systemctl start tailscaled
```

#### Paso 5 — Obtener la IP de Tailscale del DGX Spark

```bash
tailscale ip
# Ejemplo de salida: 100.64.0.12
```

Esta IP (siempre en el rango `100.x.x.x`) es la dirección permanente del Spark dentro de tu tailnet. No cambia aunque cambies de red.

También puedes ver todos tus dispositivos y sus IPs en: https://login.tailscale.com/admin/machines

#### Paso 6 — Instalar Tailscale en el equipo remoto

**macOS:**
```bash
brew install tailscale
sudo tailscale up
```
O descarga la app desde https://tailscale.com/download/mac

**Windows:**
Descarga el instalador desde https://tailscale.com/download/windows y sigue el asistente. Al finalizar, haz clic en **Log in** en el icono de la bandeja del sistema.

**Linux (Ubuntu/Debian):**
```bash
# Mismo proceso que en el Spark (ajusta el codename si no es noble)
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg | \
  sudo tee /usr/share/keyrings/tailscale-archive-keyring.gpg > /dev/null
curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list | \
  sudo tee /etc/apt/sources.list.d/tailscale.list
sudo apt update && sudo apt install -y tailscale
sudo tailscale up
```

**iOS / Android:**
Instala la app de Tailscale desde la App Store o Google Play e inicia sesión con tu cuenta.

En todos los casos, autentícate con la **misma cuenta** que usaste en el Spark. El dispositivo quedará visible en el admin panel de Tailscale.

#### Paso 7 — Verificar la conectividad entre equipos

Desde el equipo remoto, prueba que puede alcanzar el Spark por su IP de Tailscale:

```bash
ping 100.64.0.12
# Sustituve 100.64.0.12 por la IP real de tu Spark
```

Y prueba que Ollama es accesible:

```bash
curl http://100.64.0.12:11434
# Respuesta esperada: "Ollama is running"
```

#### Paso 8 — Usar la IP de Tailscale en OpenClaw y Continue.dev

Ahora sustituye la IP local (`192.168.1.42`) por la IP de Tailscale del Spark (`100.64.0.12`) en todas las configuraciones:

**OpenClaw remoto** — durante el onboarding:
```
Ollama base URL: http://100.64.0.12:11434/v1
```

**Continue.dev** — en `~/.continue/config.json`:
```json
"apiBase": "http://100.64.0.12:11434"
```

Con la IP de Tailscale funciona desde cualquier red — tu casa, la oficina, una cafetería — sin tocar el router ni abrir puertos.

#### Paso 9 — Habilitar MagicDNS (opcional pero recomendado)

Tailscale ofrece MagicDNS, que asigna nombres de host a tus dispositivos para no tener que recordar IPs. Actívalo en https://login.tailscale.com/admin/dns → **Enable MagicDNS**.

Con MagicDNS activado, puedes usar el hostname del Spark en lugar de su IP:

```bash
curl http://spark-be9d:11434
```

Y en los archivos de configuración:
```json
"apiBase": "http://spark-be9d:11434"
```

#### Comandos útiles de Tailscale

```bash
tailscale status           # Ver todos los dispositivos conectados y sus IPs
tailscale ip               # IP de Tailscale de este dispositivo
tailscale ping 100.64.0.12 # Probar conectividad con otro dispositivo
sudo tailscale up          # Reconectar / reautenticar
sudo tailscale down        # Desconectar de la tailnet
tailscale logout           # Cerrar sesión y eliminar el dispositivo de la tailnet
```

---

### 13.3 Arquitectura ampliada con Tailscale

```
┌──────────────────────────────────────────────────────────────┐
│                      DGX Spark (Host)                        │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐  │
│   │           OpenClaw Gateway  :18789                    │  │
│   │     (Web UI · TUI · Telegram · Slack · Discord)      │  │
│   └──────────────────────┬───────────────────────────────┘  │
│                           │                                   │
│   ┌──────────────────────▼───────────────────────────────┐  │
│   │      Ollama  :11434  (OLLAMA_HOST=0.0.0.0)           │  │
│   │                                                       │  │
│   │   • nemotron-3-super:120b   (~87 GB)                 │  │
│   │   • gpt-oss:120b            (~65 GB)                 │  │
│   │   • nomic-embed-text        (~274 MB)                │  │
│   └──────────────────────┬───────────────────────────────┘  │
│                           │                                   │
│   ┌──────────────────────▼───────────────────────────────┐  │
│   │     GB10 Grace Blackwell — 128 GB Unified Memory      │  │
│   └──────────────────────────────────────────────────────┘  │
│                                                              │
│   ┌──────────────────────────────────────────────────────┐  │
│   │   Tailscale  →  IP: 100.64.0.12  (cifrado WireGuard) │  │
│   └──────────────────────────────────────────────────────┘  │
└──────────────────────────┬───────────────────────────────────┘
                           │
              ┌────────────▼────────────────────────┐
              │         Red Tailscale (tailnet)       │
              │   Cifrada · Sin abrir puertos ·        │
              │   Funciona desde cualquier red         │
              └──┬──────────────┬────────────────┬────┘
                 │              │                │
    ┌────────────▼───┐ ┌────────▼──────┐ ┌──────▼───────────┐
    │  Telegram Bot  │ │ OpenClaw       │ │ VS Code          │
    │  (cualquier    │ │ remoto         │ │ + Continue.dev   │
    │  dispositivo)  │ │ (otro equipo)  │ │ (otro equipo)    │
    └────────────────┘ └───────────────┘ └──────────────────┘
```

---

## 14. Acceso a Google Workspace desde el agente (gog)

`gog` es el CLI oficial de OpenClaw para Gmail, Calendar, Drive, Docs, Sheets y Contacts. Usa OAuth2 — más robusto y seguro que App Passwords — y es el método recomendado para dar al agente acceso completo a Google Workspace.

### 14.1 Qué puede hacer el agente con gog

- **Gmail:** leer, buscar, enviar, responder, reenviar, archivar y eliminar emails
- **Calendar:** ver, crear, editar y eliminar eventos
- **Drive:** buscar, leer, subir y descargar archivos
- **Docs:** exportar y leer documentos
- **Sheets:** leer y escribir celdas, rangos y hojas
- **Contacts:** listar y buscar contactos

---

## Parte 1 — Google Cloud: proyecto, APIs y credenciales OAuth

### Paso 1 — Crear el proyecto en Google Cloud

1. Ve a https://console.cloud.google.com
2. Haz clic en el selector de proyecto (arriba a la izquierda) → **Nuevo proyecto**
3. Nombre del proyecto: `openclaw-gog`
4. Haz clic en **Crear**
5. Asegúrate de que el proyecto `openclaw-gog` está seleccionado en el selector superior

### Paso 2 — Habilitar las APIs necesarias

Ve a **APIs y servicios → Biblioteca** y habilita cada una de estas APIs (busca el nombre, haz clic y pulsa **Habilitar**):

| API |
|---|
| Gmail API |
| Google Calendar API |
| Google Drive API |
| Google Sheets API |
| Google Docs API |
| People API |

### Paso 3 — Configurar la pantalla de consentimiento OAuth

1. Ve a **APIs y servicios → Pantalla de consentimiento de OAuth**
2. Tipo de usuario: **Externo** → **Crear**
3. Rellena los campos obligatorios:
   - Nombre de la app: `OpenClaw DGX Spark`
   - Email de soporte: tu correo
   - Email de contacto del desarrollador: tu correo
4. Haz clic en **Guardar y continuar** en cada paso hasta finalizar
5. En la sección **Publicación**, haz clic en **Publicar app** y confirma

> Si la app queda en modo "Externo + Pruebas", los tokens OAuth expiran a los 7 días. Publicarla permite tokens de larga duración.

### Paso 4 — Crear las credenciales OAuth

1. Ve a **APIs y servicios → Credenciales** → **+ Crear credenciales** → **ID de cliente OAuth**
2. Tipo de aplicación: **Aplicación de escritorio**
3. Nombre: `gog-dgx-spark`
4. Haz clic en **Crear**
5. Haz clic en **Descargar JSON** — el archivo se llama `client_secret_XXXX.json`
6. Guárdalo en tu equipo local

---

## Parte 2 — Instalar gogcli en el DGX Spark

### Paso 5 — Descargar el binario ARM64 Linux

```bash
# Obtener la última versión disponible
GOG_VERSION=$(curl -s https://api.github.com/repos/openclaw/gogcli/releases/latest \
  | grep tag_name | cut -d'"' -f4)

# Descargar el binario ARM64 Linux
curl -L "https://github.com/openclaw/gogcli/releases/download/${GOG_VERSION}/gogcli_${GOG_VERSION#v}_linux_arm64.tar.gz" \
  -o /tmp/gogcli.tar.gz

# Extraer e instalar en el directorio del usuario
mkdir -p ~/.local/bin
tar -xzf /tmp/gogcli.tar.gz -C /tmp
mv /tmp/gog ~/.local/bin/gog
chmod +x ~/.local/bin/gog

# Verificar
gog --version
```

### Paso 6 — Symlink para que el gateway de OpenClaw encuentre el binario

```bash
sudo ln -s /home/$(whoami)/.local/bin/gog /usr/local/bin/gog

# Verificar
ls -la /usr/local/bin/gog
```

---

## Parte 3 — Autenticación OAuth (SSH tunnel)

El DGX Spark no tiene navegador, por lo que la autenticación OAuth se completa desde tu equipo local usando un túnel SSH.

### Paso 7 — Copiar el JSON de credenciales al Spark

Desde tu equipo local (donde descargaste el archivo):

```bash
scp ~/Downloads/client_secret_*.json manoel@spark-be9d.local:~/client_secret.json
```

### Paso 8 — Configurar las credenciales en gog

En el terminal del Spark:

```bash
gog auth credentials ~/client_secret.json
```

### Paso 9 — Iniciar la autenticación OAuth

```bash
gog auth add tu.correo@gmail.com \
  --services gmail,calendar,drive,contacts,sheets,docs
```

`gog` muestra una URL larga y el puerto local que usa para recibir el callback OAuth:

```
Open this URL in your browser to authenticate:
https://accounts.google.com/o/oauth2/auth?...&redirect_uri=http://127.0.0.1:44139/oauth2/callback&...

Listening on port 44139 for OAuth callback...
```

> **Anota el puerto** — en este ejemplo es `44139`, pero puede variar en cada ejecución.

### Paso 10 — Crear el túnel SSH desde tu equipo local

**Importante:** mantén el terminal del Spark activo. Abre una **nueva terminal en tu equipo local** y ejecuta, usando el puerto que mostró `gog`:

```bash
ssh -L 44139:localhost:44139 manoel@spark-be9d.local
```

> Sustituye `44139` por el puerto real que mostró `gog` en tu caso.

### Paso 11 — Autenticar en el navegador

Con el túnel activo, abre la URL de Google del paso 9 en el navegador de tu equipo local. Inicia sesión con tu cuenta Google y acepta todos los permisos.

Google redirige automáticamente a `http://127.0.0.1:44139/oauth2/callback?...` — el túnel SSH reenvía ese callback al Spark. En el terminal del Spark verás:

```
✓ Account tu.correo@gmail.com authenticated successfully
```

### Paso 12 — Verificar la autenticación

```bash
gog auth list --check
```

Salida esperada:
```
tu.correo@gmail.com  gmail,calendar,drive,contacts,sheets,docs  ✓
```

### Paso 13 — Prueba rápida desde la terminal

```bash
# Ver emails recientes
gog gmail search 'newer_than:7d' --max 5

# Ver eventos de hoy
gog calendar events --today
```

---

## Parte 4 — Activar el skill gog en OpenClaw

### Paso 14 — Instalar el skill desde ClawHub

```bash
openclaw skills install gog
```

### Paso 15 — Habilitar en el config

```bash
nano ~/.openclaw/config.json
```

Cambia la entrada de `gog` a `true`:

```json
"gog": {
  "enabled": true
}
```

### Paso 16 — Configurar el account por defecto

Para que el agente no tenga que especificar la cuenta en cada comando:

```bash
echo 'export GOG_ACCOUNT=tu.correo@gmail.com' >> ~/.bashrc
source ~/.bashrc
```

### Paso 17 — Reiniciar el gateway y verificar

```bash
openclaw gateway restart
openclaw skills list | grep gog
```

Salida esperada:
```
✓ ready  │ 🎮 gog  │ Google Workspace CLI for Gmail, Calendar, Drive, Contacts, Sheets, and Docs.
```

---

## Parte 5 — Usar gog desde el agente

```bash
openclaw tui
```

Ejemplos de comandos:

```
¿Qué emails importantes tengo sin leer esta semana?
```
```
Envía un email a nombre@ejemplo.com diciéndole que la reunión es mañana a las 10
```
```
¿Qué tengo en el calendario para hoy?
```
```
Crea un evento el viernes a las 15:00 llamado "Revisión del proyecto"
```
```
Busca el documento "informe Q1" en mi Drive y dime qué contiene
```
```
Muéstrame los valores de la hoja "Presupuesto 2026" en mi Sheets
```

### Comandos útiles de gog

```bash
# Gmail
gog gmail search 'newer_than:7d' --max 10          # Buscar emails recientes
gog gmail search 'is:unread' --max 20               # Emails sin leer
gog gmail messages search "from:boss" --max 5       # Por remitente
gog gmail get <messageId> --sanitize-content --json # Leer email por ID
gog gmail send --to a@b.com --subject "Hi" --body "Hello"  # Enviar email
gog gmail send --to a@b.com --subject "Hi" --body-file ./msg.txt  # Desde archivo

# Calendar
gog calendar events --today                         # Eventos de hoy
gog calendar events <calendarId> --from <iso> --to <iso>  # Rango de fechas
gog calendar create <calendarId> --summary "Título" # Crear evento

# Drive
gog drive search "nombre del archivo" --max 10      # Buscar archivos
gog drive download <fileId> --out /tmp/archivo      # Descargar archivo

# Sheets
gog sheets get <sheetId> "Hoja1!A1:D10" --json     # Leer rango
gog sheets update <sheetId> "Hoja1!A1" --values-json '[["valor"]]'  # Escribir

# Docs
gog docs export <docId> --format txt --out /tmp/doc.txt  # Exportar doc

# Contacts
gog contacts list --max 20                          # Listar contactos

# Auth
gog auth list --check                               # Ver cuentas activas
gog auth list                                       # Ver cuentas y servicios
```

---

> ⚠️ **Seguridad:** Conectar OpenClaw a tu cuenta Google implica que el agente puede leer y enviar emails, gestionar tu calendario y acceder a tus archivos de Drive. Asegúrate de que el acceso al DGX Spark está protegido y considera usar una cuenta Google dedicada si quieres limitar el riesgo.

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

---

*Guía generada en mayo de 2026. Versiones de referencia: DGX OS 7.4, Ollama 0.20+, OpenClaw 2026.x*

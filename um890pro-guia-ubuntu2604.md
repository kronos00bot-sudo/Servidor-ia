# UM890 PRO — Guía IA en Linux 2026 · Ubuntu 26.04 LTS 🦝

> **Ryzen 9 8945HS · Radeon 780M RDNA3 · 32 GB DDR5 · 1 TB NVMe**  
> Ubuntu 26.04 LTS "Resolute Raccoon" · Kernel 7.0 · ROCm nativo · Vulkan · Ollama 0.23+  
> Stack: gemma4:26b 🖼️ · qwen3.6:27b 🧠 · nemotron3:33b 🤖 · qwen3.5:9b ⚡ · OpenClaw 🦞 · Open WebUI

> ✅ **Guía basada en instalación real** — menús de BIOS verificados en v1.05, lecciones aprendidas de sesión de configuración real documentadas.

---

## Índice

1. [Especificaciones y Arquitectura](#1-especificaciones-y-arquitectura)
2. [Configuración de BIOS v1.05](#2-configuración-de-bios-v105)
3. [Instalación de Ubuntu 26.04](#3-instalación-de-ubuntu-2604)
4. [Driver AMD y ROCm](#4-driver-amd-y-rocm)
5. [Ollama + Modelos de IA](#5-ollama--modelos-de-ia)
6. [OpenClaw — Agente Personal 24/7](#6-openclaw--agente-personal-247)
7. [Open WebUI — Interfaz Visual](#7-open-webui--interfaz-visual)
8. [Optimizaciones Finales y Referencia](#8-optimizaciones-finales-y-referencia)

---

## 1. Especificaciones y Arquitectura

### Hardware del UM890 PRO

| Componente | Especificación |
|---|---|
| **CPU** | AMD Ryzen 9 8945HS — 8C/16T, hasta 5.2 GHz, TDP 35–70W configurable |
| **iGPU** | AMD Radeon 780M — RDNA 3, 12 CUs @ 2800 MHz, gfx1103 |
| **RAM** | 32 GB DDR5-5600 — compartida CPU/GPU (**16 GB asignados a iGPU en BIOS**) |
| **SSD** | 1 TB NVMe PCIe 4.0 — ~7 GB/s |
| **NPU** | AMD XDNA — 16 TOPS |
| **BIOS** | American Megatrends v1.05 — 19/05/2025 |

```bash
sudo dmidecode -t 0 | grep -E 'Version|Release Date|Vendor'
# → Version: 1.05 · Release Date: 05/19/2025
```

### Novedades de Ubuntu 26.04 relevantes para IA

| Cambio | Impacto |
|---|---|
| **Kernel 7.0** | Mejor soporte AMD GPU — amdgpu puede cargar automáticamente |
| **ROCm en repos oficiales** | `sudo apt install rocm` — sin script externo de AMD |
| **dracut** reemplaza initramfs-tools | Comandos de initramfs cambian (ver sección 4) |
| **cgroup v2 exclusivo** | Cgroup v1 eliminado — sin impacto en Ollama |
| **/tmp como tmpfs** | Sin impacto en el stack de IA |

### Rendimiento Real con Vulkan en iGPU

> ⚠️ **Expectativas realistas.** El backend Vulkan de Ollama tiene ~50% de eficiencia frente a ROCm optimizado. La 780M con DDR5-5600 tiene ~89 GB/s de ancho de banda compartido CPU/GPU. El rendimiento de generación está limitado por la física del hardware:

| Modelo | Tamaño | Velocidad real | Limitante |
|---|---|---|---|
| **qwen3.5:9b** | ~6.6 GB | 6–8 tok/s | BW: 89 GB/s ÷ 6.6 GB |
| **gemma4:26b** | ~16 GB | 3–5 tok/s | BW: 89 GB/s ÷ 16 GB |
| **qwen3.6:27b** | ~17 GB | 3–5 tok/s | BW: 89 GB/s ÷ 17 GB |
| **nemotron3:33b** | ~28 GB | 2–3 tok/s | GPU+CPU split |

> 💡 El prefill (velocidad de procesamiento del prompt) es 2–3x más rápido. Para uso en agente y Telegram, 6–8 tok/s del modelo de 9b es perfectamente usable.

### Stack de Modelos

| Modelo | Tag Ollama | Alias | Rol |
|---|---|---|---|
| 🖼️ **gemma4:26b** | `gemma4:26b` | `gemma` | **Primario multimodal.** Imágenes, visión, agente, tool calling. Google DeepMind. |
| 🧠 **qwen3.6:27b** | `qwen3.6:27b` | `qwen` | **Código y razonamiento.** 77.2% SWE-bench. Mejor modelo denso de código. |
| 🤖 **nemotron3:33b** | `nemotron3:33b` | `nemotron` | **Agéntico avanzado.** Multimodal, tool-use, GPU+CPU split. |
| ⚡ **qwen3.5:9b** | `qwen3.5:9b` | `fast` | **Primario de velocidad.** Chat rápido, respuestas inmediatas, Telegram. |

> ⚠️ **Thinking mode.** Gemma4, Qwen3.6 y Qwen3.5 tienen thinking mode. En uso normal el agente puede tardar varios minutos si el thinking se activa. Se crean versiones sin thinking via Modelfile (ver sección 5.4).

### Arquitectura Final

```
┌──────────────────────────────────────────────────────────────────┐
│                          UM890 PRO                                │
│             Ubuntu 26.04 LTS "Resolute Raccoon"                   │
│                                                                   │
│  🦞 OpenClaw ──── Telegram Bot / Panel Web :18789                │
│       ├── gemma4:26b-nothin  → imágenes, visión, agentes         │
│       ├── qwen3.6:27b-nothin → código, razonamiento              │
│       ├── nemotron3:33b      → agéntico avanzado                 │
│       └── qwen3.5:9b-nothin  → chat rápido (primario Telegram)   │
│                                                                   │
│  🤖 Ollama 0.23+ — Vulkan — RADV PHOENIX 23.4 GiB               │
│  🖥️  Open WebUI ─────── http://localhost:3000                    │
│                                                                   │
│  🟢 BIOS: 16GB VRAM + Performance Mode + EXPO DDR5-5600          │
│  🟢 Kernel 7.0 — amdgpu nativo — Radeon 780M gfx1103            │
│  🟢 ROCm vía apt — `sudo apt install rocm`                       │
│  🟢 OLLAMA_VULKAN=1 — 23.4 GiB detectados                       │
│  🟢 ai-performance.service — CPU EPP + GPU high                  │
│  🟢 ZRAM 8GB zstd                                                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. Configuración de BIOS v1.05

> ⚠️ Menús verificados en **BIOS v1.05 (mayo 2025)**. Versiones anteriores pueden tener estructura diferente.

**Acceder:** Reinicia y presiona `Delete` repetidamente. Menús: **Main · Advanced · Security · Boot · Save & Exit**.

### 2.1 VRAM iGPU ← más importante

```
Advanced
  └── AMD CBS
        └── NBIO Common Options
              └── GFX Configuration
                    └── UMA Frame Buffer Size → 16G
```

> ⚠️ En v1.05 la opción está dentro de `GFX Configuration`, un nivel más profundo. No está directamente en `NBIO Common Options`.

### 2.2 TDP del CPU

```
Advanced
  └── PowerLimit Setting     ← menú directo en v1.05
        └── Power Limit → Performance Mode   (~70W)
```

> 💡 Performance Mode es crítico para `nemotron3:33b` en split GPU+CPU.

### 2.3 EXPO — DDR5 a velocidad completa

```
Advanced
  └── AMD CBS
        └── UMC Common Options
              └── EXPO Profile → Profile 1 (5600 MT/s)
```

> ⚠️ **Crítico.** Sin EXPO la RAM corre a 4800 MT/s y el ancho de banda de la iGPU baja un 20%. A 89 GB/s vs 71 GB/s, `nemotron3:33b` pierde 0.5–1 tok/s.

### 2.4 Secure Boot

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

## 3. Instalación de Ubuntu 26.04

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

> 💡 Ubuntu 26.04 requiere mínimo 6 GB RAM (cumplido) y 25 GB de disco. TPM-based full disk encryption está habilitado por defecto en la instalación — desactívalo si no lo necesitas para simplificar el arranque.

### 3.1 Post-instalación base

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y build-essential git curl wget
sudo apt install -y htop btop nvtop
uname -r   # → 7.0.x-xx-generic
```

> 💡 Ubuntu 26.04 incluye Python 3.14, GCC 15.2 y Node.js más reciente en los repos. No es necesario añadir PPAs externos para la mayoría de dependencias.

### 3.2 CPU Governor — Servicio systemd

> ⚠️ En kernel 7.0 con `amd-pstate-epp`, `cpufrequtils` y `powerprofilesctl` siguen sin funcionar correctamente con sudo. El servicio systemd directo a sysfs es la solución estable.

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
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
# → performance ✅
cat /sys/class/drm/card1/device/power_dpm_force_performance_level
# → high ✅
```

> 💡 El servicio detecta la GPU AMD por vendor ID `0x1002`. En el UM890 PRO la 780M está en `card1`, no en `card0` (card0 es la salida virtual).

### 3.3 ZRAM

> ⚠️ **Crítico para nemotron3:33b en split.** Los ~28 GB del modelo usan GPU + RAM. ZRAM con zstd hace que el overflow sea 3–5x más rápido que el swap en disco.

> ⚠️ En Ubuntu 26.04, `systemd-zram-generator` está disponible en repos. No instalar `zram-config` — son incompatibles.

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

zramctl
# → /dev/zram0  zstd  8G  [SWAP] ✅
```

> ⚠️ **Problema real:** Si Ubuntu 26.04 ya tenía un dispositivo ZRAM activo al instalar `systemd-zram-generator`, el nuevo servicio puede arrancar con la config antigua (4G, lzo-rle) en lugar de la nueva (8G, zstd). Solución:

```bash
# Si zramctl muestra 4G o lzo-rle en lugar de 8G/zstd:
sudo swapoff /dev/zram0
sudo systemctl stop systemd-zram-setup@zram0.service
sudo systemctl daemon-reload
sudo systemctl start systemd-zram-setup@zram0.service
zramctl   # → /dev/zram0  zstd  8G  [SWAP] ✅
```

### 3.4 Parámetros del kernel

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

## 4. Driver AMD y ROCm

### 4.1 Gran novedad de Ubuntu 26.04: ROCm en repos oficiales

Ubuntu 26.04 incluye ROCm en los repositorios oficiales de Canonical. La instalación es ahora trivial:

```bash
sudo apt install -y python3-setuptools python3-wheel
sudo usermod -aG render,video $USER
sudo apt install -y rocm
```

> ⚠️ La versión de ROCm en los repos de Ubuntu puede estar algunos meses por detrás de la última de AMD. Para uso con Ollama/Vulkan esto no es relevante — Ollama gestiona su propio backend. ROCm via apt es suficiente para tener las herramientas de monitorización (`rocm-smi`, `rocminfo`).

Verificar:

```bash
# Hacer logout/login para que los grupos render/video tengan efecto
# o ejecutar en la misma sesión:
newgrp render

rocm-smi
# → Radeon 780M, temperatura, MCLK ✅
rocminfo | grep gfx
# → gfx1103 ✅
```

### 4.2 amdgpu en Kernel 7.0

Con kernel 7.0 y mejor soporte AMD nativo, `amdgpu` puede cargar automáticamente al arranque. Verifica primero:

```bash
lsmod | grep amdgpu
```

Si ya aparece, no necesitas hacer nada. Si no aparece, aplica el mecanismo de carga:

```bash
# Cargar ahora
sudo modprobe amdgpu

# Persistencia en arranque
echo 'amdgpu' | sudo tee /etc/modules-load.d/amdgpu.conf

# dracut (reemplaza initramfs-tools en Ubuntu 26.04)
# NO usar update-initramfs — ese comando ya no existe
echo 'add_drivers+=" amdgpu "' | sudo tee /etc/dracut.conf.d/amdgpu.conf
sudo dracut --regenerate-all --force

# Servicio de respaldo
sudo tee /etc/systemd/system/load-amdgpu.service << 'EOF'
[Unit]
Description=Load amdgpu module
DefaultDependencies=no
Before=multi-user.target

[Service]
Type=oneshot
ExecStart=/sbin/modprobe amdgpu
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable load-amdgpu.service
sudo reboot
```

> ⚠️ **Cambio importante vs Ubuntu 24.04:** El comando `update-initramfs` ya no existe. Ubuntu 26.04 usa `dracut`. El comando equivalente es `sudo dracut --regenerate-all --force`.

### 4.3 Verificar tras reboot

```bash
lsmod | grep amdgpu   # → amdgpu  [tamaño]  [usos] ✅
rocm-smi              # → Radeon 780M, ~35°C ✅
rocminfo | grep gfx   # → gfx1103 ✅
```

### 4.4 Variables de entorno

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

## 5. Ollama + Modelos de IA

### 5.1 Instalar Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version   # → 0.23.x+ ✅
sudo systemctl enable --now ollama
```

### 5.2 Configurar backend Vulkan

> ⚠️ ROCm sigue sin soportar gfx1103 para inferencia en Ollama. El backend **Vulkan** es la solución estable y detecta 23.4 GiB disponibles.

> ⚠️ Usar `OLLAMA_VULKAN=1` (número). El valor `true` o `"true"` es ignorado silenciosamente.

> ⚠️ **No usar `OLLAMA_KV_CACHE_TYPE=q8_0`.** Con modelos de 16–17 GB, este parámetro satura los ~7 GB de VRAM restantes y provoca swapping constante, reduciendo la velocidad a 1–2 tok/s.

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
# → total="23.4 GiB"  available="23.3 GiB" ✅
```

### 5.3 Instalar modelos

```bash
# Primario multimodal — visión + tool calling (Google DeepMind)
ollama pull gemma4:26b        # ~16 GB — GPU+CPU split o 100% GPU según VRAM libre

# Código y razonamiento denso — 77.2% SWE-bench
ollama pull qwen3.6:27b       # ~17 GB — GPU+CPU split

# Agéntico avanzado — MoE, tool-use
ollama pull nemotron3:33b     # ~28 GB — GPU+CPU split

# Chat rápido — primario para Telegram
ollama pull qwen3.5:9b        # ~6.6 GB — 100% GPU

ollama list
# → gemma4:26b      ~16 GB ✅
# → qwen3.6:27b     ~17 GB ✅
# → nemotron3:33b   ~28 GB ✅
# → qwen3.5:9b      ~6.6 GB ✅
```

### 5.4 Modelfiles sin thinking mode ← obligatorio

> ⚠️ **Problema crítico real.** Gemma4, Qwen3.6 y Qwen3.5 tienen thinking mode habilitado por defecto. Cada respuesta puede generar 500–1000 tokens de razonamiento interno antes de contestar. A 3–8 tok/s, esto equivale a 1–5 minutos de espera por mensaje. Los Modelfiles siguientes pre-rellenan el bloque `<think>` vacío, desactivando el thinking de forma efectiva.

**Contexto por modelo:** Para un agente con herramientas, historial y resultados de búsqueda, 16k es el mínimo práctico. 32k es el óptimo para el modelo de uso diario. Los modelos grandes están limitados por VRAM:

| Modelfile | num_ctx | KV cache | VRAM total | Margen |
|---|---|---|---|---|
| qwen35-es | **32768** | ~6 GB | ~12.6 GB | ✅ amplio |
| gemma4-es | **16384** | ~3 GB | ~19 GB | ✅ justo |
| qwen36-es | **16384** | ~3 GB | ~20 GB | ✅ justo |

> 💡 El JSON de OpenClaw tiene `maxHistoryTokens: 12000` como red de seguridad — trunca el historial antiguo antes de enviarlo a Ollama, evitando llegar al boundary de contexto donde el driver Vulkan crashea.

```bash
# Qwen3.5 sin thinking — chat rápido principal (32k — cabe bien en VRAM)
cat > /tmp/Modelfile-qwen35 << 'EOF'
FROM qwen3.5:9b
SYSTEM "Eres un asistente personal inteligente. Responde SIEMPRE en español salvo que el usuario pida otro idioma. Sé conciso y directo."
PARAMETER num_ctx 32768
PARAMETER num_predict 1024
EOF
ollama create qwen35-es -f /tmp/Modelfile-qwen35

# Gemma4 sin thinking — primario multimodal (16k — límite VRAM con ~16 GB de modelo)
cat > /tmp/Modelfile-gemma4 << 'EOF'
FROM gemma4:26b
SYSTEM "Eres un asistente personal inteligente. Responde SIEMPRE en español salvo que el usuario pida otro idioma. Sé conciso y directo."
PARAMETER num_ctx 16384
PARAMETER num_predict 1024
EOF
ollama create gemma4-es -f /tmp/Modelfile-gemma4

# Qwen3.6 sin thinking — código y razonamiento (16k — límite VRAM con ~17 GB de modelo)
cat > /tmp/Modelfile-qwen36 << 'EOF'
FROM qwen3.6:27b
SYSTEM "Eres un asistente experto en código y razonamiento. Responde siempre en español."
PARAMETER num_ctx 16384
PARAMETER num_predict 1024
EOF
ollama create qwen36-es -f /tmp/Modelfile-qwen36

# Verificar
ollama list | grep '\-es'
# → gemma4-es    ✅
# → qwen36-es    ✅
# → qwen35-es    ✅
```

> 💡 `nemotron3:33b` no necesita Modelfile — es un modelo de razonamiento agentico sin thinking mode problemático.

### 5.5 Test de velocidad

```bash
# Test qwen35-es (el más rápido)
time ollama run qwen35-es 'Hola, ¿en qué GPU estás corriendo?'
# → debería responder en 10–30 segundos

# Velocidad detallada
ollama run qwen35-es --verbose 'Di hola en una frase.' 2>&1 | grep 'eval rate'
# → eval rate: 6–8 tok/s
```

---

## 6. OpenClaw — Agente Personal 24/7

### 6.1 Instalar Node.js y OpenClaw

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
node --version   # → v24.x.x

# Siempre con sudo en Ubuntu
sudo npm install -g pnpm
sudo npm install -g openclaw@latest

openclaw --version   # → OpenClaw 2026.x.x ✅
```

### 6.2 Onboarding

```bash
openclaw onboard --install-daemon
# Wizard:
# → nombre del agente
# → proveedor: Ollama
# → modelo: qwen35-es  (el más rápido para el agente)
# → canal: Telegram
```

### 6.3 Crear Bot de Telegram

1. Telegram → **@BotFather** → `/newbot`
2. Elige nombre y username (termina en `bot`)
3. Copia el token: `123456789:AAFxxxx...`
4. Pégalo en el wizard de OpenClaw

> ⚠️ El token es una credencial. Si se expone, regenerar con `/revoke` en @BotFather.

### 6.4 Gestión segura de credenciales

> ⚠️ **OpenClaw standalone NO soporta** la sintaxis `openshell:resolve:env:` — eso es exclusivo de NemoClaw. La solución para externalizar credenciales es un sistema de plantilla + `envsubst` que inyecta los valores al arrancar el servicio.

**Estructura de archivos:**

```
~/.openclaw/
├── .credentials          ← credenciales reales (chmod 600, nunca en git)
├── openclaw.json.template ← plantilla con ${VARIABLES} (puede estar en git)
└── openclaw.json         ← generado automáticamente al arrancar (no editar)
```

**Paso 1 — Archivo de credenciales:**

```bash
cat > ~/.openclaw/.credentials << 'EOF'
OPENCLAW_GATEWAY_TOKEN=TU_TOKEN_GATEWAY
OPENCLAW_TELEGRAM_BOT_TOKEN=TU_BOT_TOKEN_TELEGRAM
OPENCLAW_TELEGRAM_OWNER_ID=TU_TELEGRAM_ID
OPENCLAW_IP_LOCAL=192.168.0.12
EOF

chmod 600 ~/.openclaw/.credentials
ls -la ~/.openclaw/.credentials
# → -rw------- 1 mloco mloco ... .credentials ✅
```

**Paso 2 — Script de arranque que inyecta credenciales:**

```bash
cat > ~/.openclaw/start-gateway.sh << 'EOF'
#!/bin/bash
set -e
source ~/.openclaw/.credentials
envsubst < ~/.openclaw/openclaw.json.template > ~/.openclaw/openclaw.json
exec openclaw gateway
EOF

chmod 700 ~/.openclaw/start-gateway.sh
```

**Paso 3 — Override del servicio para usar el script:**

```bash
mkdir -p ~/.config/systemd/user/openclaw-gateway.service.d/

cat > ~/.config/systemd/user/openclaw-gateway.service.d/credentials.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/home/mloco/.openclaw/start-gateway.sh
EOF

systemctl --user daemon-reload
```

### 6.5 Configuración — `~/.openclaw/openclaw.json.template`

> ⚠️ El archivo real es `openclaw.json`, no `config.json`. A partir de aquí se trabaja con la **plantilla** (`openclaw.json.template`). El `openclaw.json` se genera solo al arrancar el servicio.

```bash
mkdir -p ~/Escritorio/Servidor-ia/agente_workspace
```

Crear `~/.openclaw/openclaw.json.template` con este contenido — las variables `${...}` serán sustituidas automáticamente:

```json
{
  "agents": {
    "defaults": {
      "workspace": "/home/mloco/Escritorio/Servidor-ia/agente_workspace",
      "thinkingDefault": "off",
      "verboseDefault": "off",
      "systemPromptOverride": "Eres un asistente personal inteligente. Responde SIEMPRE en español, de forma clara y concisa. Nunca uses otro idioma a menos que el usuario lo pida explícitamente.",
      "models": {
        "ollama/qwen35-es":    { "alias": "fast" },
        "ollama/gemma4-es":    { "alias": "gemma" },
        "ollama/qwen36-es":    { "alias": "qwen" },
        "ollama/nemotron3:33b":{ "alias": "nemotron" }
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
    },
    "nodes": {
      "denyCommands": [
        "camera.snap", "camera.clip", "screen.record",
        "contacts.add", "calendar.add", "reminders.add",
        "sms.send", "sms.search"
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
      }
    }
  },
  "auth": {
    "profiles": {
      "ollama:default": { "provider": "ollama", "mode": "api_key" }
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

Permisos de la plantilla (no contiene secretos pero por consistencia):

```bash
chmod 600 ~/.openclaw/openclaw.json.template
```

### 6.6 Reiniciar y verificar

```bash
systemctl --user restart openclaw-gateway
sleep 5
journalctl --user -u openclaw-gateway --since "30 sec ago" | grep -i 'error\|ready\|telegram'
# → Telegram connected ✅
# → Gateway ready on :18789 ✅
```

### 6.7 Panel Web

```bash
ip a | grep '192.168'
# Acceder desde cualquier dispositivo en la red:
# http://TU_IP:18789/?token=TU_TOKEN
```

> ⚠️ Con `bind: loopback` el panel no es accesible desde la red. Usar `bind: lan`. El token va en la URL: `?token=TU_TOKEN`.

### 6.8 Comandos desde Telegram

| Comando | Modelo | Uso |
|---|---|---|
| `/model fast` | qwen35-es | **Por defecto.** Chat rápido, respuestas en 10–30s |
| `/model gemma` | gemma4-es | Imágenes, visión, multimodal |
| `/model qwen` | qwen36-es | Código complejo, análisis |
| `/model nemotron` | nemotron3:33b | Agéntico avanzado (lento, ~2 min) |
| `/skills` | — | Ver skills activos |
| `/memory` | — | Ver contexto persistente |
| `/clear` | — | Limpiar historial |

### 6.9 Servicio 24/7

```bash
systemctl --user enable openclaw-gateway
sudo loginctl enable-linger $USER
journalctl --user -fu openclaw-gateway   # logs en tiempo real
```

---

## 7. Open WebUI — Interfaz Visual

```bash
# Crear volumen primero (evita "external volume not found")
docker volume create open-webui

docker run -d \
  --name open-webui \
  --network=host \
  -v open-webui:/app/backend/data \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

Acceder en: **http://localhost:3000**

> 💡 Todos los modelos aparecen automáticamente desde Ollama. Puedes usar los Modelfiles (`gemma4-es`, `qwen35-es`, `qwen36-es`) o los modelos base directamente.

> ⚠️ Si usas docker-compose con `external: true`, crear el volumen manualmente antes: `docker volume create open-webui`.

---

## 8. Optimizaciones Finales y Referencia

### 8.1 Tabla de Problemas Reales y Soluciones

| Problema | Causa | Solución |
|---|---|---|
| VRAM no encontrada en BIOS | En v1.05 está en `GFX Configuration` | `AMD CBS → NBIO Common Options → GFX Configuration` |
| TDP no encontrado | En v1.05 es `PowerLimit Setting` en Advanced | `Advanced → PowerLimit Setting → Performance Mode` |
| CPU queda en `powersave` | `amd-pstate-epp` en kernel 7.0 | Servicio systemd directo a sysfs |
| GPU en `card1` no `card0` | UM890 PRO tiene salida virtual en card0 | Detectar por vendor ID `0x1002` |
| ZRAM no arranca | `zram-config` y `systemd-zram-generator` incompatibles | Solo `systemd-zram-generator` |
| ROCm runner crashea en Ollama | gfx1103 no soportado en ROCm para inferencia | `OLLAMA_VULKAN=1` |
| `OLLAMA_VULKAN=true` ignorado | Ollama espera número | Usar `OLLAMA_VULKAN=1` |
| `update-initramfs` no existe | Ubuntu 26.04 usa dracut | `sudo dracut --regenerate-all --force` |
| Modelo tarda 5–15 min en responder | Thinking mode activo generando tokens internos | Usar Modelfiles `-es` con `num_predict` limitado |
| VRAM al 99%, velocidad 1–2 tok/s | `OLLAMA_KV_CACHE_TYPE=q8_0` satura VRAM | Eliminar esa variable del override.conf |
| `npm install -g` falla EACCES | Ubuntu requiere sudo para globales | `sudo npm install -g openclaw@latest` |
| Panel web "Unauthorized" | `bind: loopback` + falta token en URL | `bind: lan` + `?token=TU_TOKEN` |
| `openclaw skill` no encontrado | Comando incorrecto | `openclaw skills list` (plural) |
| Modelo "not found" en OpenClaw | Nombre sin tag o nombre base sin Modelfile | Usar siempre nombre completo: `gemma4-es`, `qwen35-es` |
| Docker compose "external volume" | Volumen externo no existe | `docker volume create open-webui` antes de `compose up` |
| Gemma4 responde en inglés | Sin system prompt fijo | Usar `gemma4-es` (Modelfile con SYSTEM en español) |
| `rocm-smi` no encontrado | Grupos render/video no aplicados | Hacer logout/login o `newgrp render` |
| ZRAM muestra 4G y lzo-rle en vez de 8G y zstd | Dispositivo ZRAM preexistente ignora nueva config | `swapoff /dev/zram0` + `systemctl stop/start systemd-zram-setup@zram0` |
| OpenClaw: `low context window (warn<8000)` | `contextWindow` en openclaw.json demasiado bajo | Subir a 16384 en openclaw.json y en el Modelfile |
| Runner crash 500 + `signal arrived during cgo execution` | Bug Vulkan en ggml al truncar prompt exactamente en el límite de contexto | Subir `num_ctx` a 16384 para dar margen antes del truncation boundary |
| Sesión bloqueada (`stalled_agent_run` 300+ segundos) | Historial acumulado supera el contexto y provoca truncación | Ejecutar `/clear` en Telegram + mantener num_ctx ≥ 16384 |
| Gateway falla con `Invalid config` tras usar `openshell:resolve:env:` | Esa sintaxis es de NemoClaw, no de OpenClaw standalone | Usar sistema plantilla + `envsubst` (sección 6.4) |

### 8.2 Verificación Final

```bash
# CPU en performance
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
# → performance ✅

# GPU en high
cat /sys/class/drm/card1/device/power_dpm_force_performance_level
# → high ✅

# amdgpu cargado
lsmod | grep amdgpu   # → amdgpu  [tamaño]  [usos] ✅

# ROCm
rocm-smi   # → Radeon 780M, ~35°C ✅

# Vulkan activo en Ollama
sudo journalctl -u ollama --since "5 min ago" | grep Vulkan
# → library=Vulkan  total="23.4 GiB" ✅

# ZRAM
zramctl   # → /dev/zram0  zstd  8G  [SWAP] ✅

# Servicios
systemctl status ollama ai-performance
systemctl --user status openclaw-gateway
docker ps | grep open-webui

# Modelos
ollama list
# → gemma4-es     ✅
# → qwen35-es     ✅
# → qwen36-es     ✅
# → gemma4:26b    ✅
# → qwen3.6:27b   ✅
# → nemotron3:33b ✅
# → qwen3.5:9b    ✅
```

### 8.3 Benchmarks Reales

| Modelo | Modo | Velocidad real | VRAM |
|---|---|---|---|
| ⚡ **qwen35-es** (qwen3.5:9b) | 100% GPU Vulkan | 6–8 tok/s | ~6.6 GB / 23.4 GB |
| 🖼️ **gemma4-es** (gemma4:26b) | GPU+CPU | 3–5 tok/s | ~16 GB GPU + RAM |
| 🧠 **qwen36-es** (qwen3.6:27b) | GPU+CPU | 3–5 tok/s | ~17 GB GPU + RAM |
| 🤖 **nemotron3:33b** | GPU+CPU | 2–3 tok/s | ~23 GB GPU + ~5 GB RAM |

> 💡 El limitante no es software — es el ancho de banda de memoria del iGPU (~89 GB/s DDR5-5600 compartido). Velocidades multiplicadas por ~2x cuando AMD o Ollama mejoren el backend Vulkan para gfx1103.

### 8.4 Referencia Rápida

```bash
# Servicios
sudo systemctl restart ollama
sudo systemctl restart ai-performance
systemctl --user restart openclaw-gateway

# GPU
sudo modprobe amdgpu        # cargar si no está
rocm-smi                    # estado
watch -n 1 rocm-smi         # monitor en tiempo real

# Modelos (sin thinking)
ollama run qwen35-es        # primario rápido
ollama run gemma4-es        # multimodal, imágenes
ollama run qwen36-es        # código, análisis

# Modelos base (con thinking — lentos en agent, OK para test directo)
ollama run qwen3.5:9b
ollama run gemma4:26b
ollama run nemotron3:33b

# Benchmark
ollama run qwen35-es --verbose 'Test.' 2>&1 | grep 'eval rate'

# Listar y gestionar
ollama list
ollama ps       # modelos cargados en memoria
ollama stop qwen35-es   # descargar de memoria

# OpenClaw
journalctl --user -fu openclaw-gateway
openclaw skills list
ip a | grep '192.168'   # IP para el panel web

# ROCm
rocm-smi
rocminfo | grep gfx     # → gfx1103
```

---

*Ubuntu 26.04 LTS "Resolute Raccoon" · Kernel 7.0 · BIOS AMI v1.05 · ROCm via apt · Ollama 0.23+ · Vulkan RADV PHOENIX · OpenClaw 2026.x*  
*Mayo 2026 — Guía basada en instalación y pruebas reales en UM890 PRO*

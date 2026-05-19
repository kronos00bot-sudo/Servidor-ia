# Servidor-ia

Repositorio principal para automatización conversacional y procesamiento multimedia, con foco actual en moderación y operación por Telegram sobre una arquitectura híbrida UM890 + DGX.

## Estado actual del proyecto

- Canal activo y mantenido: Telegram.
- Skill principal: agente_workspace/skills/telegram.
- Flujo de moderación con aprobación humana habilitado.
- Integración de transcripción remota (Whisper en DGX) y generación LLM (UM890/DGX vía Ollama).
- Endurecimiento de seguridad aplicado en webhook y cliente HTTP.

## Objetivo funcional

El sistema recibe mensajes de Telegram (webhook o polling), procesa texto y audio, genera contexto de respuesta y, en modo moderación, envía una propuesta al chat privado de aprobación antes de publicar en el grupo origen.

Flujo resumido:

1. Entrada de update Telegram.
2. Normalización del mensaje.
3. Si hay audio/voz: descarga, conversión a WAV, transcripción.
4. En chat monitorizado: cola de aprobación con transcripción, traducción y borrador en inglés.
5. Aprobación/rechazo por comandos en chat privado.
6. Envío final al chat origen o descarte.

## Estructura del repositorio

- agente_workspace: núcleo de trabajo del agente y skills.
- agente_workspace/skills/telegram: implementación actual de Telegram.
- moderation-bot: datos operativos (estado, logs, media procesada) usados por la skill.
- voz: utilidades de asistente por voz local.

## Arquitectura de Telegram

Componentes principales:

- telegram_skill.py
  - Entrypoint CLI.
  - Modos: webhook, polling y ciclo proactivo.
- webhook/endpoint.py
  - Servidor Flask.
  - Endpoints de salud y webhook.
  - Validación por cabecera X-Telegram-Bot-Api-Secret-Token.
- poller.py
  - Cliente de long polling a getUpdates.
  - Persistencia de offset para continuidad.
- service.py
  - Orquestación central de cada update.
  - Lógica de moderación, encolado, aprobación y envío.
- core.py
  - Normalización del mensaje y respuestas base/comandos.
- media.py
  - Descarga de adjuntos desde Bot API.
  - Derivación hacia procesamiento por tipo.
- transcriber.py
  - Conversión con ffmpeg a WAV mono 16kHz.
  - STT remoto contra whisper-server.
- routing/task_router.py
  - Política de ruteo UM890/DGX por tipo de tarea.
- routing/remote_client.py
  - Cliente de inferencia para transcripción y generación.
- state.py
  - Estado persistente en JSON: offset, chats, pendientes de aprobación.
- proactive.py
  - Resúmenes proactivos cuando hay inactividad.
- utils/http_client.py
  - Reintentos, backoff y sanitización de URLs (redacción de token bot).

## Requisitos

Requisitos de sistema:

- Linux.
- Python 3.11+ (recomendado 3.14 en este entorno).
- ffmpeg y ffprobe accesibles en PATH o vía FFMPEG_BIN.

Dependencias Python usadas por la skill:

- flask
- requests
- python-dotenv
- pytest (para pruebas)

Si no existe un archivo de dependencias consolidado, instalar manualmente en un entorno virtual de la skill.

## Configuración

La skill soporta carga de configuración desde:

1. Variables de entorno.
2. OPENCLAW_CONFIG_PATH (openclaw.json).
3. ~/.openclaw/openclaw.json (y fallbacks).

Variables clave:

- OPENCLAW_TELEGRAM_BOT_TOKEN
- OPENCLAW_TELEGRAM_WEBHOOK_SECRET
- OPENCLAW_TELEGRAM_OWNER_ID
- OPENCLAW_TELEGRAM_APPROVAL_CHAT_ID
- OPENCLAW_TELEGRAM_MONITORED_CHAT_ID
- TELEGRAM_WEBHOOK_PORT
- TELEGRAM_WEBHOOK_BASE_PATH (default: /telegram/webhook)
- TELEGRAM_RATE_LIMIT_SECONDS
- TELEGRAM_PROACTIVE_INACTIVITY_HOURS
- TELEGRAM_PROACTIVE_MAX_CHATS_PER_CYCLE
- PROJECT_DIR (default: /home/mloco/Escritorio/Servidor-ia/moderation-bot)

Variables de servicios IA:

- DGX_WHISPER_URL (default: http://100.64.129.87:8765/inference)
- DGX_OLLAMA_URL (default: http://100.64.129.87:11434)
- LOCAL_OLLAMA_URL (default: http://127.0.0.1:11434)
- TIMEOUT_* para transcripción, chat, razonamiento, traducción y documentos.

## Instalación sugerida

Desde agente_workspace:

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m venv skills/telegram/.venv
source skills/telegram/.venv/bin/activate
pip install --upgrade pip
pip install flask requests python-dotenv pytest
```

## Ejecución

Desde agente_workspace:

### 1) Webhook Flask

```bash
source skills/telegram/.venv/bin/activate
python -m skills.telegram.telegram_skill --serve --host 0.0.0.0 --port 8085
```

Endpoints:

- GET /health
- GET /telegram/webhook
- POST /telegram/webhook

Para operar con webhook, el emisor debe enviar la cabecera:

- X-Telegram-Bot-Api-Secret-Token: valor exacto de OPENCLAW_TELEGRAM_WEBHOOK_SECRET.

### 2) Polling local

```bash
source skills/telegram/.venv/bin/activate
python -m skills.telegram.telegram_skill --poll --sleep 2
```

### 2.1) Operacion continua obligatoria (systemd user service)

Para produccion local, el poller NO debe depender de una terminal abierta.
Debe ejecutarse como servicio de usuario de systemd con reinicio automatico.

Crear archivo de entorno:

```bash
mkdir -p ~/.config/openclaw
cat > ~/.config/openclaw/telegram-poller.env << 'EOF'
OPENCLAW_TELEGRAM_MONITORED_CHAT_ID=-5289754689
OPENCLAW_TELEGRAM_APPROVAL_CHAT_ID=7434781236
TELEGRAM_RATE_LIMIT_SECONDS=1
PYTHONUNBUFFERED=1
EOF
```

Crear servicio:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/openclaw-telegram-poller.service << 'EOF'
[Unit]
Description=OpenClaw Telegram Poller (moderation)
After=network-online.target
Wants=network-online.target
StartLimitBurst=5
StartLimitIntervalSec=60

[Service]
Type=simple
WorkingDirectory=/home/mloco/Escritorio/Servidor-ia/agente_workspace
Environment=HOME=/home/mloco
Environment=PATH=/usr/bin:/home/mloco/.local/bin
EnvironmentFile=/home/mloco/.config/openclaw/telegram-poller.env
ExecStart=/home/mloco/Escritorio/Servidor-ia/agente_workspace/skills/telegram/.venv/bin/python -m skills.telegram.telegram_skill --poll --sleep 2
Restart=always
RestartSec=3
TimeoutStopSec=20
KillMode=control-group

[Install]
WantedBy=default.target
EOF
```

Activar y verificar:

```bash
systemctl --user daemon-reload
systemctl --user enable --now openclaw-telegram-poller.service
systemctl --user status openclaw-telegram-poller.service --no-pager
loginctl enable-linger "$USER"
```

Nota operativa:

- Ejecutar una sola instancia de poller por bot/token.
- Si hay dos instancias en paralelo, Telegram responde 409 Conflict en getUpdates.

### 3) Ciclo proactivo puntual

```bash
source skills/telegram/.venv/bin/activate
python -m skills.telegram.telegram_skill --proactive-once
```

### 4) Script de moderación

Existe el lanzador:

- agente_workspace/skills/telegram/start_moderation_poller.sh

Este script espera un archivo local .env.moderation en la carpeta de la skill (no versionado) para exportar credenciales y parámetros antes de iniciar el poller.

## Comandos de bot

Comandos generales:

- /start
- /help
- /status
- /summary

Comandos de moderación (chat privado de aprobación):

- /pending o /pendientes
- /approve <id> o /aprobar <id>
- /approve <id> <texto> o /aprobar <id> <texto>
- /reject <id> o /rechazar <id>

## Flujo de moderación recomendado

Configuración mínima:

- OPENCLAW_TELEGRAM_MONITORED_CHAT_ID = chat origen (grupo/supergrupo)
- OPENCLAW_TELEGRAM_APPROVAL_CHAT_ID = chat privado del aprobador

Resultado:

1. Mensaje del grupo entra en cola.
2. Se genera paquete de revisión con:
   - transcripción,
   - traducción al español,
   - borrador en inglés.
3. Aprobador ejecuta comando.
4. Si se aprueba, el bot publica en el chat origen.

## Persistencia y rutas de datos

Con PROJECT_DIR por defecto:

- moderation-bot/data/telegram_state.json
  - last_update_id
  - métricas por chat
  - pending_approvals
- moderation-bot/media/telegram
  - adjuntos descargados por chat
- moderation-bot/media/processed/audio_wav
  - WAV convertidos para STT
- moderation-bot/data/transcriptions
  - resultados JSON de transcripción
- moderation-bot/logs/telegram_skill.log
  - trazas rotadas del sistema

## Seguridad

Controles actualmente implementados:

- Validación obligatoria de cabecera secreta en webhook.
- Comparación de secreto con hmac.compare_digest.
- Errores de webhook hacia cliente sin detalles internos.
- Sanitización de URLs para evitar fuga de token bot en logs/excepciones.
- Separación de credenciales por entorno local (.env no versionado).

Buenas prácticas obligatorias:

- No versionar archivos con secretos.
- Rotar inmediatamente cualquier token expuesto.
- Usar push protegido y revisar alertas de secret scanning.
- Limitar el acceso al chat de aprobación.

## Pruebas

La suite actual cubre:

- configuración,
- cliente Telegram,
- webhook,
- media,
- estado,
- comportamiento proactivo.

Ejecutar desde agente_workspace:

```bash
source skills/telegram/.venv/bin/activate
pytest -q skills/telegram/tests
```

## Observabilidad y troubleshooting

Log principal:

- moderation-bot/logs/telegram_skill.log

Pistas rápidas:

- Webhook responde 403:
  - revisar cabecera X-Telegram-Bot-Api-Secret-Token y OPENCLAW_TELEGRAM_WEBHOOK_SECRET.
- Poller no procesa mensajes:
  - validar token del bot, conectividad a api.telegram.org y last_update_id en estado.
  - confirmar que el servicio `openclaw-telegram-poller.service` este `active (running)`.
  - revisar conflictos 409 si hubo mas de un poller ejecutandose a la vez.
- Audio sin transcripción:
  - validar ffmpeg/ffprobe,
  - revisar conectividad y timeout a DGX_WHISPER_URL,
  - inspeccionar transcriptions JSON para errores.
- Mensajes no llegan al grupo en moderación:
  - confirmar TELEGRAM_MONITORED_CHAT_ID y TELEGRAM_APPROVAL_CHAT_ID,
  - revisar estado pending_approvals y comandos de aprobación.

## Limitaciones actuales

- En modo Telegram-only, photo/document/video no generan análisis avanzado; quedan deshabilitados por diseño actual.
- El estado JSON guarda contenido textual de revisión (transcript y borrador) en claro.
- La operación depende de disponibilidad de servicios remotos DGX para varias rutas críticas.

## Roadmap sugerido

- Añadir archivo de dependencias formal para la skill de Telegram.
- Cifrar o minimizar datos sensibles guardados en estado.
- Incorporar métricas estructuradas (latencia, tasa de error por ruta).
- Automatizar CI para pruebas de la skill Telegram.
- Documentar despliegue productivo de webhook con reverse proxy TLS.

## Notas de legado

- **whatsapp-agent** y **whatsapp-agent-smoketest** retirados (mayo 2026). El pipeline
  de procesamiento de chats exportados de WhatsApp (parseo, STT, visión, traducción)
  fue completamente eliminado del repositorio. El canal activo y mantenido es Telegram.
- Los archivos de caché de audio con nomenclatura de origen WhatsApp que existían en
  `moderation-bot/media/` y `moderation-bot/data/transcriptions/` también fueron
  eliminados. No afectan al funcionamiento actual del bot de Telegram.

Se retiraron componentes de legado no alineados con el foco actual. El canal operativo vigente es Telegram.
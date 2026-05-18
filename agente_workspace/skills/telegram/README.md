# Telegram Adapter

Telegram es el adaptador proactivo de OpenClaw sobre el core compartido de WhatsApp.

## Ejecucion

Webhook:

```bash
python -m skills.telegram.telegram_skill --serve
```

Polling local:

```bash
python -m skills.telegram.telegram_skill --poll
```

Ciclo proactivo puntual:

```bash
python -m skills.telegram.telegram_skill --proactive-once
```

## Variables de entorno

- `OPENCLAW_TELEGRAM_BOT_TOKEN`
- `OPENCLAW_TELEGRAM_WEBHOOK_SECRET`
- `OPENCLAW_TELEGRAM_OWNER_ID`
- `OPENCLAW_TELEGRAM_APPROVAL_CHAT_ID`
- `OPENCLAW_TELEGRAM_MONITORED_CHAT_ID`
- `TELEGRAM_WEBHOOK_PORT`
- `TELEGRAM_RATE_LIMIT_SECONDS`
- `TELEGRAM_PROACTIVE_INACTIVITY_HOURS`
- `TELEGRAM_PROACTIVE_MAX_CHATS_PER_CYCLE`

Precedencia de configuracion del adapter:

1. Variables de entorno (`OPENCLAW_*`, `TELEGRAM_*`).
2. `OPENCLAW_CONFIG_PATH` (si apunta a un `openclaw.json` valido).
3. `~/.openclaw/openclaw.json` y fallback a `~/.openclaw/openclaw.json.novo`.

Mapeo desde `openclaw.json`:

- `channels.telegram.botToken` -> token del bot.
- `commands.ownerAllowFrom[0]` -> chat owner permitido (acepta `telegram:123456` o `123456`).

## Flujo de aprobacion para chat grupal

Objetivo: escuchar un chat grupal, enviar transcripcion+borrador al chat privado del owner, y solo publicar en el grupo cuando el owner aprueba.

Config minima:

- `OPENCLAW_TELEGRAM_MONITORED_CHAT_ID=-100...` (chat grupal origen)
- `OPENCLAW_TELEGRAM_APPROVAL_CHAT_ID=123456789` (chat privado para aprobar)

Comandos de aprobacion (en el chat privado):

- `/pending` -> lista pendientes
- `/approve <id>` -> envia el borrador en ingles al grupo
- `/approve <id> <texto_en_ingles>` -> envia texto editado
- `/reject <id> <motivo_opcional>` -> rechaza sin enviar

## Estado

- Guarda estado liviano por chat en `data/telegram_state.json`.
- Reutiliza ruteo, transcripcion, vision, documentos e interpretacion del core existente.
- Puede procesar media y emitir resúmenes proactivos cuando el chat queda inactivo.

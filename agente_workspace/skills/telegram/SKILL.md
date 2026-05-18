---
name: telegram
summary: Telegram proactive adapter for OpenClaw using the shared WhatsApp core.
applyTo: "skills/telegram/**"
---

# Telegram Skill

Telegram es el adaptador proactivo de OpenClaw sobre el core compartido de WhatsApp.

## Modos de ejecucion

- Webhook: `python -m skills.telegram.telegram_skill --serve`
- Polling local: `python -m skills.telegram.telegram_skill --poll`

## Variables de entorno

- `OPENCLAW_TELEGRAM_BOT_TOKEN`
- `OPENCLAW_TELEGRAM_WEBHOOK_SECRET`
- `OPENCLAW_TELEGRAM_OWNER_ID`
- `TELEGRAM_WEBHOOK_PORT`
- `TELEGRAM_RATE_LIMIT_SECONDS`

## Comportamiento actual

- Reutiliza `TaskRouter` y `RemoteClient` del core existente.
- Procesa texto, comandos y media basica.
- Guarda estado liviano por chat en `data/telegram_state.json`.
- Usa webhook o polling segun el contexto de despliegue.

## Comandos

- `/start`
- `/help`
- `/status`

## Notas

- El canal debe permanecer como adaptador fino; la logica de IA vive en el core compartido.
- Para media, el primer corte prioriza descarga y procesamiento local/remoto antes de acciones proactivas avanzadas.

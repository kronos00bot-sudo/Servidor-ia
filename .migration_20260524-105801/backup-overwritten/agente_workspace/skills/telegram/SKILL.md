---
name: telegram
summary: Telegram proactive skill for OpenClaw with dedicated routing and moderation flow.
applyTo: "skills/telegram/**"
---

# Telegram Skill

Telegram es la skill proactiva y de moderación de OpenClaw para Telegram.

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

- El canal debe permanecer enfocado en Telegram; la logica de IA vive en su propio core interno.
- Para media, el primer corte prioriza descarga y procesamiento local/remoto antes de acciones proactivas avanzadas.

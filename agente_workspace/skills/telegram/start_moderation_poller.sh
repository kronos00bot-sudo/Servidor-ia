#!/usr/bin/env bash
# Lanzador del poller de moderación Telegram
# Usa el bot de moderación (token separado del bot principal de OpenClaw)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV="$WORKSPACE_DIR/../agente_workspace/skills/whatsapp/.venv/bin/python"

# Cargar variables de entorno del bot de moderación
set -a
# shellcheck source=.env.moderation
source "$SCRIPT_DIR/.env.moderation"
set +a

echo "[moderation-poller] Iniciando con token ...${TELEGRAM_BOT_TOKEN: -6}"
echo "[moderation-poller] Owner/Approval chat: $TELEGRAM_APPROVAL_CHAT_ID"
echo "[moderation-poller] Monitored chat: ${TELEGRAM_MONITORED_CHAT_ID:-<modo revisión privada>}"

cd "$WORKSPACE_DIR"
exec "$VENV" -m skills.telegram.telegram_skill --poll

#!/usr/bin/env bash
# Lanzador del poller de moderación Telegram
# Usa el bot de moderación (token separado del bot principal de OpenClaw)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV="$WORKSPACE_DIR/skills/telegram/.venv/bin/python"

# Cargar variables de entorno del bot de moderación
set -a
# shellcheck source=.env.moderation
if [[ -f "$SCRIPT_DIR/.env.moderation" ]]; then
	source "$SCRIPT_DIR/.env.moderation"
else
	echo "[moderation-poller] ERROR: falta $SCRIPT_DIR/.env.moderation"
	exit 1
fi
set +a

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
	echo "[moderation-poller] ERROR: TELEGRAM_BOT_TOKEN no definido"
	exit 1
fi

echo "[moderation-poller] Iniciando bot de moderacion"
echo "[moderation-poller] Owner/Approval chat: $TELEGRAM_APPROVAL_CHAT_ID"
echo "[moderation-poller] Monitored chat: ${TELEGRAM_MONITORED_CHAT_ID:-<modo revisión privada>}"

cd "$WORKSPACE_DIR"
exec "$VENV" -m skills.telegram.telegram_skill --poll

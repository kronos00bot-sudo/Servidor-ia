---
name: whatsapp
description: "Procesamiento integral de exportes de WhatsApp (texto/audio/video/imagen/documentos), con ruteo UM890+DGX y webhook de Meta WhatsApp Business."
homepage: local
metadata:
	{
		"openclaw":
			{
				"emoji": "💬",
				"requires": { "bins": ["python3"] }
			}
	}
---

# WhatsApp Skill for OpenClaw (UM890 + DGX)

Este skill es parte del agente OpenClaw que corre en UM890.
No es un proyecto aislado: se integra con la estructura de OpenClaw y enruta tareas a DGX cuando corresponde.

## Scope

- Parseo de chat exportado de WhatsApp
- STT de audio/video
- Vision para imagenes y frames de video
- Resumen/interpetacion/traduccion por LLM
- Endpoint webhook para WhatsApp Business API

## Distributed routing

- UM890 local: vision, chat rapido, razonamiento moderado
- DGX remoto: whisper STT, razonamiento profundo, traduccion larga

## Installation

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace/skills/whatsapp
python3 -m pip install -r requirements.txt
python3 -m pip install -r requirements-dev.txt
```

## Runtime

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m skills.whatsapp.whatsapp_skill --chat /path/to/_chat.txt
```

## Uso desde el agente OpenClaw

En el chat del agente, puedes pedirle directamente tareas del skill con prompts como:

- "Procesa este chat de WhatsApp usando el skill whatsapp: /ruta/_chat.txt"
- "Ejecuta solo media (sin LLM) para PROJECT_DIR=/ruta/proyecto"
- "Reanuda el procesamiento de WhatsApp donde se quedó"
- "Levanta el webhook de WhatsApp Business con mi .env"

Si el agente no lo toma en la primera petición tras cambios de skill, reinicia la sesión del agente para forzar recarga de skills.

## Infrastructure validation

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m skills.whatsapp.utils.infrastructure
```

## Webhook

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m skills.whatsapp.webhook.endpoint
```

## Environment

Usar `.env` basado en `.env.example` dentro de `skills/whatsapp/` o en el `PROJECT_DIR` del runtime OpenClaw.

Variables clave:

- `PROJECT_DIR`
- `MACHINE_TYPE` (`um890` o `dgx`)
- `LOCAL_OLLAMA_URL`
- `DGX_OLLAMA_URL`
- `DGX_WHISPER_URL`
- `WHATSAPP_VERIFY_TOKEN`
- `WHATSAPP_APP_SECRET`
- `WHATSAPP_ACCESS_TOKEN`
- `WHATSAPP_PHONE_NUMBER_ID`

## Tests

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m pytest -q skills/whatsapp/tests
```

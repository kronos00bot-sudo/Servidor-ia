# WhatsApp Skill (OpenClaw UM890)

Este skill es una capacidad integrada del agente OpenClaw en UM890.
No es un proyecto aislado: usa el runtime de OpenClaw y enruta tareas entre UM890 y DGX.

## Arquitectura

- UM890 (local): chat rapido, vision y razonamiento moderado
- DGX (remoto): whisper STT y analisis profundo
- Router: decide destino por tipo/complejidad de tarea

## Uso rapido

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m skills.whatsapp.whatsapp_skill --chat /ruta/_chat.txt
```

## Verificacion de infraestructura

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m skills.whatsapp.utils.infrastructure
```

## Webhook Meta

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m skills.whatsapp.webhook.endpoint
```

### Endpoints

- GET /webhook: verificacion inicial de Meta
- POST /webhook: recepcion de eventos (valida HMAC si hay secreto)

## Testing

```bash
cd /home/mloco/Escritorio/Servidor-ia/agente_workspace
python3 -m pytest -q skills/whatsapp/tests
```

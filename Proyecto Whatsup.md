# Proyecto WhatsApp Skill para OpenClaw

## Plan de Implementación Detallado

**Última actualización**: 17 de mayo de 2026  
**Estado**: En Planificación  
**Responsable**: Manoel López  

---

## TL;DR Ejecutivo

Crear un **skill modular para OpenClaw** que procese mensajes de WhatsApp (chats, audios, imágenes, documentos) con:

1. **Arquitectura distribuida inteligente**:
   - **DGX Spark** (servidor): Modelos 120B + inferencia de mayor calidad, STT, traducción profunda
   - **UM890 PRO** (cliente): Modelos locales rápidos/medios para visión y chat, con fallback local de 33B
   
2. **TaskRouter**: Enruta cada tarea a la máquina óptima automáticamente usando la menor latencia posible
3. **Webhook Meta**: Captura mensajes en tiempo real
4. **Integración OpenClaw**: Memoria compartida, identidad (SOUL.md), herramientas (TOOLS.md)
5. **Estándares Production**: Testing >80%, logging rotativo, reintentos exponenciales, Docker

**Timeline**: 21-25 días | **Scope**: Skill modular, reutilizable, distribuido

---

## 🏗️ Arquitectura Física Real

### DGX Spark (Servidor Central)

| Aspecto | Detalles |
|---|---|
| **Hardware** | NVIDIA GB10 Grace Blackwell, 128 GB LPDDR5x, 20 cores ARM |
| **Ollama** | http://127.0.0.1:11434 |
| **Modelos** | nemotron-3-super:120b (87GB), gpt-oss:120b (65GB) |
| **STT** | whisper-server :8765 (Nvidia) |
| **OpenClaw Gateway** | :18789 |
| **Tailscale** | 100.64.129.87 (red privada) |
| **Rol** | Servidor de inferencia, análisis pesado, procesamiento STT |

### UM890 PRO (Cliente Inteligente)

| Aspecto | Detalles |
|---|---|
| **Hardware** | AMD Ryzen 9 8945HS, Radeon 780M (RDNA3), 32 GB DDR5 + 8GB ZRAM |
| **Ollama** | http://127.0.0.1:11434 (local) |
| **Modelos Locales** | qwen35-es (chat), **gemma4-es (visión)**, qwen36-es, nemotron3:33b |
| **Acceso DGX** | http://100.64.129.87:11434 vía Tailscale |
| **OpenClaw Gateway** | :18789 |
| **Tailscale** | 100.64.0.X (red privada) |
| **Rol** | Cliente inteligente, procesamiento local rápido, visión |

### Distribución de Tareas (TaskRouter)

| Tarea | Máquina | Modelo | Timeout | Rationale |
|---|---|---|---|---|
| **Transcripción STT** | DGX | whisper-server:8765 | 300s | Mejor rendimiento para audio y evita cargar UM890 |
| **Visión/Descripción imágenes/video** | UM890 | gemma4-es local | 60s | Latencia baja y procesamiento multimodal local |
| **Chat rápido / respuestas inmediatas** | UM890 | qwen35-es local | 120s | Mejor modelo local para velocidad y latencia corta |
| **Razonamiento moderado / código** | UM890 | qwen36-es local | 180s | Buen equilibrio entre velocidad y capacidad de análisis |
| **Agente complejo local / fallback sin DGX** | UM890 | nemotron3:33b local | 240s | Capacidad local avanzada cuando el DGX no está disponible |
| **Análisis profundo / traducción / resumen largo** | DGX | nemotron-3-super:120b | 600s | Calidad máxima y contexto extendido |
| **Fallback remoto alternativo** | DGX | gpt-oss:120b | 600s | Menor carga en DGX manteniendo calidad alta |

---

## 📋 8 Fases de Implementación

### **FASE 0: Entender OpenClaw + Validar Infraestructura** (1 día)

**Actividades**:
1. Leer estructura OpenClaw:
   - `/agente_workspace/AGENTS.md`, `MEMORY.md`, `TOOLS.md`, `SOUL.md`, `USER.md`
   - Estudiar skill existente: `/agente_workspace/skills/email/`
   
2. Validar infraestructura física:
   - Verificar DGX accesible en Tailscale (100.64.129.87:11434)
   - Verificar UM890 accesible localmente (127.0.0.1:11434)
   - Verificar whisper-server:8765 en DGX
   - Verificar modelos cargados en ambas máquinas

3. Entender:
   - Cómo OpenClaw maneja múltiples máquinas
   - Sistema de memoria compartida (MEMORY.md)
   - Distribución de carga en config.json

**Deliverables**:
- Documento de entendimiento de arquitectura OpenClaw
- Reporte de validación de conectividad DGX ↔ UM890

**Verificación**: ✅ DGX+UM890 comunicando, Tailscale funciona

---

### **FASE 1: Migrar Código y Crear TaskRouter** (2-3 días)

Mover código existente de `/whatsapp-agent/` a `/agente_workspace/skills/whatsapp/` en **AMBAS máquinas**.

**Estructura Target**:
/agente_workspace/skills/whatsapp/
├── SKILL.md # Documentación del skill
├── requirements.txt # Dependencias Python
├── init.py
├── whatsapp_skill.py # API principal
│
├── core/
│ ├── init.py
│ ├── parser.py # Parse chat WhatsApp
│ ├── transcriber.py # STT
│ ├── interpreter.py # Análisis LLM
│ ├── translator.py # Traducción
│ ├── pipeline.py # Orquestador principal
│ └── processors/
│ ├── init.py
│ ├── image_processor.py # Visión
│ ├── video_processor.py # Video
│ └── pdf_processor.py # Documentos
│
├── routing/ ⭐ NUEVO
│ ├── init.py
│ ├── task_router.py # Enruta tareas a DGX vs UM890
│ └── remote_client.py # Cliente Ollama remoto
│
├── utils/
│ ├── init.py
│ ├── config.py # Validación centralizada
│ ├── logger.py # Logger con rotación
│ ├── http_client.py # HTTP + reintentos
│ ├── exceptions.py # Custom exceptions
│ └── infrastructure.py # Healthchecks
│
├── webhook/
│ ├── init.py
│ ├── endpoint.py # Endpoint Meta
│ └── client.py # WhatsApp API client
│
├── tests/
│ ├── conftest.py
│ ├── test_task_router.py
│ ├── test_remote_client.py
│ ├── test_pipeline.py
│ ├── test_infrastructure.py
│ └── fixtures/
│
├── examples/
│ └── usage.py
│
├── .env # Variables de entorno
└── .env.example # Template

**Actividades**:
1. **Migrar código existente**
   - Copiar archivos de `/whatsapp-agent/src/` a `core/`
   - Adaptar imports y rutas
   - Eliminar hardcoding de PROJECT_DIR

2. **Crear TaskRouter** (módulo crítico)
   ```python
   class TaskRouter:
       """Enruta tareas a DGX o UM890 según tipo, latencia y complejidad."""

       def route_transcription(self, audio_file) -> str:
           """Audio → SIEMPRE DGX whisper-server"""
           return "dgx_whisper"

       def route_vision(self, image_file) -> str:
           """Imagen/video → SIEMPRE UM890 gemma4-es local"""
           return "um890_gemma4"

       def route_chat(self, prompt: str, urgency: bool = False) -> str:
           """Chat rápido → SIEMPRE UM890 qwen35-es local"""
           return "um890_qwen35"

       def route_reasoning(self, content: str, complexity: int) -> str:
           """Razonamiento → UM890 para moderado, DGX para profundo."""
           if complexity <= 5:
               return "um890_qwen36"
           if complexity <= 8:
               return "um890_nemotron33"
           return "dgx_nemotron_120b"

       def route_translation(self, text) -> str:
           """Traducción profunda → DGX nemotron-3-super:120b"""
           return "dgx_nemotron_120b"

**Deliverables**:
- TaskRouter implementado y testeable
- RemoteClient funcional

**Verificación**: ✅ Imports OK, TaskRouter decide correctamente, código compila

---

### **FASE 2: Validación de Infraestructura** (1 día)

Crear herramientas para validar setup en ambas máquinas.

**Actividades**:
1. **Script `utils/infrastructure.py`**
   ```python
   def validate_infrastructure() -> dict:
       """Valida setup completo"""
       checks = {
           "machine_type": get_machine_type(),  # "dgx" o "um890"
           "local_ollama": check_ollama_health("http://127.0.0.1:11434"),
           "tailscale": check_tailscale_ip(),
           "local_models": validate_models_loaded(),
       }
       
       if machine_type == "um890":
           checks["dgx_remote"] = check_ollama_health("http://100.64.129.87:11434")
           checks["whisper_dgx"] = check_whisper_health("http://100.64.129.87:8765")
       else:  # DGX
           checks["whisper_local"] = check_whisper_health("http://127.0.0.1:8765")
       
       return checks
   ```

2. **CLI para validación**
   ```bash
   python -m whatsapp_skill.utils.infrastructure
   # Output:
   # ✅ Machine: UM890
   # ✅ Local Ollama: OK
   # ✅ Tailscale IP: 100.64.0.42
   # ✅ DGX Remote: OK (100.64.129.87)
   # ✅ whisper-server: OK
   # ⚠️  Model nemotron3:33b: NOT LOADED (use: ollama pull nemotron3:33b)
   ```

**Deliverables**:
- Script de validación en `utils/infrastructure.py`
- Documentación de troubleshooting
- Reporte de validación en ambas máquinas

**Verificación**: ✅ Script ejecuta sin errores en ambas máquinas

---

### **FASE 3: Robustecer Código** (3-4 días)

Agregar reintentos, timeouts granulares, fallbacks inteligentes.

**Actividades**:
1. **Mejorar HTTPClient** en `utils/http_client.py`
   - Reintentos exponenciales: 3 intentos, backoff 2x
   - Timeouts granulares por servicio:
     - DGX whisper-server: 300s
     - DGX nemotron-3-super:120b: 600s
     - UM890 visión: 60s
     - UM890 chat: 120s
   - Manejo de ConnectionError, Timeout, HTTP 5xx

2. **Fallback inteligente**
   ```python
   def process_with_fallback(task, preferred_machine):
       """Intenta en máquina preferida, falla a alternativa"""
       try:
           return execute_on(task, preferred_machine)
       except (TimeoutError, ConnectionError):
           log.warning(f"Timeout en {preferred_machine}, usando fallback")
           return execute_on(task, fallback_machine)
   ```

3. **Logging mejorado** en `utils/logger.py`
   - RotatingFileHandler: 10 MB x 10 backups
   - Formato: [timestamp] [nivel] [máquina] [módulo] mensaje
   - Métrica de intentos y tiempos

4. **Excepciones personalizadas** en `utils/exceptions.py`
   - `ConfigError`, `TranscriberError`, `LLMError`, `WebhookError`
   - Distinguir: recuperables (retry) vs fatales (fail-fast)

5. **Refactorizar módulos existentes**
   - `transcriber.py`: usar HTTPClient con reintentos
   - `interpreter.py`: validar JSON, reintentos en respuesta corrupta
   - `translator.py`: optimizar a 1 call LLM
   - `processors/*.py`: manejo de archivos corruptos (skip vs retry)

**Deliverables**:
- HTTPClient robusto con reintentos
- Logging rotativo en ambas máquinas
- Fallback logic implementada
- Módulos refactorizados

**Verificación**: ✅ Logs muestran reintentos, fallbacks funcionan, tiempos aceptables

---

### **FASE 4: Testing Unitario e Integración** (3-4 días)

Suite pytest con >80% cobertura, usando mocks de DGX y UM890.

**Estructura de Tests**:
```
tests/
├── conftest.py
├── test_config.py
├── test_task_router.py ⭐ CRÍTICO
├── test_remote_client.py
├── test_parser.py
├── test_transcriber.py
├── test_image_processor.py
├── test_interpreter.py
├── test_translator.py
├── test_pipeline.py
├── test_webhook.py
├── test_infrastructure.py
├── test_e2e.py
└── fixtures/
    ├── sample_chat.txt
    ├── sample_audio.wav
    ├── sample_image.png
    ├── sample_pdf.pdf
    └── mocked_responses.json
```

**Actividades**:
1. Tests por módulo (pytest + pytest-mock + requests-mock)
2. Mocks de servicios remotos
3. Objetivo: coverage >80%

**Deliverables**:
- Suite pytest completa
- Coverage report >80%
- Mocks para servicios

**Verificación**: ✅ pytest pasa, coverage >80%, retry logic demostrada

---

### **FASE 5: Documentación** (2 días)

**Actividades**:
1. SKILL.md completo
2. Actualizar TOOLS.md en `/agente_workspace/`
3. requirements.txt con versiones pinned
4. Docstrings Google-style
5. README.md en `/agente_workspace/skills/whatsapp/`

**Deliverables**:
- SKILL.md ejecutable
- TOOLS.md actualizado
- requirements.txt
- Docstrings completos
- README claro

**Verificación**: ✅ SKILL.md claro, TOOLS.md documenta la infraestructura

---

### **FASE 6: Integración WhatsApp Business API** (4-5 días)

**Flujo**:
```
Meta Webhook → UM890:8000/webhook
             ↓
Validar firma HMAC
             ↓
Parser payload
             ↓
pipeline.py + TaskRouter
  ├─ STT → DGX whisper
  ├─ Visión → UM890 gemma4-es
  ├─ Chat rápido → UM890 qwen35-es
  ├─ Razonamiento moderado → UM890 qwen36-es
  ├─ Agente local / fallback → UM890 nemotron3:33b
  └─ Análisis profundo / traducción → DGX nemotron-3-super:120b
             ↓
WhatsApp Client → Meta API → usuario
```

**Actividades**:
1. Endpoint Flask/FastAPI en `webhook/endpoint.py`
2. Client WhatsApp API en `webhook/client.py`
3. Seguridad: HMAC, rate limiting, sanitización
4. Configurar variables .env para WhatsApp
5. Integración con OpenClaw memory

**Deliverables**:
- Endpoint Webhook funcional
- Client WhatsApp API
- HMAC validación
- Logging seguro

**Verificación**: ✅ Webhook procesa Meta payloads correctamente

---

### **FASE 7: DevOps y Containerización** (2-3 días)

**Actividades**:
1. Dockerfile
2. docker-compose.yml
3. .dockerignore
4. Makefile

**Deliverables**:
- Dockerfile
- docker-compose.yml
- Makefile
- .dockerignore
- .gitignore

**Verificación**: ✅ Build sin errores, healthcheck pasa

---

### **FASE 8: Verificación Final e Integración E2E** (2 días)

**Actividades**:
1. E2E test completo
2. Performance testing
3. Checklist final
4. Documentación de despliegue

**Deliverables**:
- E2E tests pasando
- Performance baselines
- Checklist completado
- Documentación de despliegue

**Verificación**: ✅ E2E test pasa, ambas máquinas funcionan en armonía

---

## 📁 Estructura Final de Archivos

```
/agente_workspace/
├── skills/
│   ├── whatsapp/
│   │   ├── SKILL.md
│   │   ├── requirements.txt
│   │   ├── Makefile
│   │   ├── Dockerfile
│   │   ├── docker-compose.yml
│   │   ├── __init__.py
│   │   ├── whatsapp_skill.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── parser.py
│   │   │   ├── transcriber.py
│   │   │   ├── interpreter.py
│   │   │   ├── translator.py
│   │   │   ├── pipeline.py
│   │   │   └── processors/
│   │   │       ├── __init__.py
│   │   │       ├── image_processor.py
│   │   │       ├── video_processor.py
│   │   │       └── pdf_processor.py
│   │   ├── routing/
│   │   │   ├── __init__.py
│   │   │   ├── task_router.py
│   │   │   └── remote_client.py
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── logger.py
│   │   │   ├── http_client.py
│   │   │   ├── exceptions.py
│   │   │   └── infrastructure.py
│   │   ├── webhook/
│   │   │   ├── __init__.py
│   │   │   ├── endpoint.py
│   │   │   └── client.py
│   │   ├── tests/
│   │   │   ├── conftest.py
│   │   │   ├── test_*.py
│   │   │   └── fixtures/
│   │   ├── examples/
│   │   │   └── usage.py
│   │   ├── .env
│   │   └── .env.example
│   ├── email/
│   └── ...
├── memory/
├── MEMORY.md
├── TOOLS.md
└── SOUL.md
```

---

## ✅ Checklist Final

- [ ] TaskRouter enruta correctamente
- [ ] DGX y UM890 comunican vía Tailscale
- [ ] STT → DGX, Visión → UM890
- [ ] Reintentos y fallbacks funcionan
- [ ] Webhook recibe Meta payloads
- [ ] pytest >80%
- [ ] SKILL.md y TOOLS.md completos
- [ ] Chat procesado fin-a-fin correctamente

---

## 🎯 Diferenciadores Clave

1. **TaskRouter**: Decisión inteligente de dónde ejecutar cada tarea
2. **Timeouts granulares**: Respeta capacidad de cada máquina
3. **Fallback degradado**: Sistema sigue funcionando sin DGX
4. **Tailscale como backbone**: Red privada cifrada, sin puertos abiertos
5. **Distribución óptima**: Visión local (UM890), análisis pesado (DGX)
6. **MEMORY.md compartida**: OpenClaw mantiene contexto persistente

---

## Timeline

**Total: 21-25 días** (algunas fases pueden paralelizarse)

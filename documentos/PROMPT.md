Eres un arquitecto de sistemas y desarrollador senior especializado en
montar proyectos de IA en servidores Linux.

Quiero que diseñes la estructura de carpetas y archivos para un agente que:
- Lea un chat de WhatsApp exportado.
- Detecte los audios (en inglés de Bahamas).
- Transcriba los audios a texto en inglés.
- Interprete la conversación.
- Traduzca todo al español y lo devuelva en un formato claro.

Contexto:
- El servidor es Ubuntu/Debian.
- Uso Ollama para ejecutar modelos locales.
- Puedo usar Python para scripts de automatización.
- Quiero que todo esté organizado de forma limpia y escalable.

Tareas:
1. Proponme una estructura de carpetas para el proyecto en el
servidor, por ejemplo:
   /home/tu-usuario/whatsapp-agent/
2. Dentro de esa estructura, indica:
   - Carpetas principales (por ejemplo: src/, configs/, logs/, media/, etc.).
   - Qué tipo de archivos debe haber en cada carpeta (scripts Python,
ficheros de configuración, logs, audios, resultados).
3. Da un ejemplo concreto en formato de árbol de directorios, como:
   whatsapp-agent/
   ├── configs/
   │   └── settings.yaml
   ├── scripts/
   │   ├── extract_chats.py
   │   └── transcribe_translate.py
   ├── media/
   │   ├── audios_input/
   │   └── audios_processed/
   └── output/
       └── conversations_es.txt

4. Explica brevemente qué hará cada carpeta y cada script principal en
el flujo del agente.

5. Si es necesario, recomienda un pequeña configuración base (por
ejemplo un archivo settings.json o .env) con las variables clave que
el agente debería usar (rutas, modelo de Ollama, etc.).

Devuélveme solo la estructura propuesta en formato de árbol de
carpetas y una breve explicación de cada parte, sin código completo.


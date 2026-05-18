#!/usr/bin/env python3
import subprocess, tempfile, os, sys, json
import requests

WHISPER_BIN   = os.path.expanduser("~/whisper.cpp/build/bin/whisper-cli")
WHISPER_MODEL = os.path.expanduser("~/whisper.cpp/models/ggml-large-v3.bin")
OLLAMA_URL    = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL  = "qwen35-es"
MIC_CARD      = "hw:2,0"  # no usado con pipewire
SAMPLE_RATE   = 16000
STATE_FILE    = os.path.expanduser("~/.config/asistente_voz/state.json")

VOCES = {
    "es": os.path.expanduser("~/.piper/voices/es_ES-sharvard-medium.onnx"),
    "en": os.path.expanduser("~/.piper/voices/en_US-ryan-high.onnx"),
    "pt": os.path.expanduser("~/.piper/voices/pt_BR-faber-medium.onnx"),
}

SYSTEM_PROMPTS = {
    "es": "Eres un asistente personal inteligente. Responde siempre en español, de forma clara y concisa.",
    "en": "You are a smart personal assistant. Always respond in English, clearly and concisely.",
    "pt": "Voce eh um assistente pessoal inteligente. Responda sempre em portugues brasileiro, de forma clara e concisa.",
}

CAMBIO_IDIOMA = {
    "español": "es", "spanish": "es", "espanhol": "es",
    "inglés": "en", "ingles": "en", "english": "en", "ingles": "en",
    "portugués": "pt", "portugues": "pt", "portuguese": "pt",
}

os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

def cargar_estado():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"lang_respuesta": "auto"}

def guardar_estado(estado):
    json.dump(estado, open(STATE_FILE, "w"))

MIC_TARGET = "alsa_input.usb-Jieli_Technology_USB_Composite_Device-02.mono-fallback"

def grabar_audio(segundos=7):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    print(f"Grabando {segundos}s... habla ahora")
    proc = subprocess.Popen([
        "pw-record",
        f"--target={MIC_TARGET}",
        "--rate=16000", "--channels=1",
        "--format=s16",
        tmp.name
    ])
    import time; time.sleep(segundos)
    proc.terminate()
    proc.wait()
    return tmp.name

DGX_WHISPER_URL = "http://100.64.129.87:8765/inference"

def transcribir(audio_path):
    """STT remoto en el DGX Spark via whisper-server."""
    import json as _json
    with open(audio_path, "rb") as f:
        resp = requests.post(
            DGX_WHISPER_URL,
            files={"file": ("audio.wav", f, "audio/wav")},
            data={"response_format": "json", "language": "auto"}
        )
    data = resp.json()
    texto = data.get("text", "").strip()
    lang_code = data.get("language", "")
    lang = "es"
    if lang_code in ("en", "english"):      lang = "en"
    elif lang_code in ("pt", "portuguese"): lang = "pt"
    elif lang_code in ("es", "spanish"):    lang = "es"
    return texto, lang

def detectar_cambio_idioma(texto):
    texto_lower = texto.lower()
    triggers = ["cambia", "change", "muda", "habla", "speak", "fala", "responde", "respond"]
    for patron, lang in CAMBIO_IDIOMA.items():
        if patron in texto_lower and any(w in texto_lower for w in triggers):
            return lang
    return None

def preguntar_llm(texto, lang):
    import json as _json
    instruccion = SYSTEM_PROMPTS[lang] + " " + texto
    result = subprocess.run(
        ["openclaw", "agent", "--agent", "main", "-m", instruccion, "--json", "--model", "dgx/nemotron-3-super:120b"],
        capture_output=True, text=True
    )
    output = result.stdout  # JSON solo en stdout, stderr tiene logs
    # El JSON empieza en el primer {
    idx = output.find("{")
    if idx >= 0:
        try:
            data = _json.loads(output[idx:])
            payloads = data.get("payloads", [])
            if payloads:
                return payloads[0].get("text", "").strip()
        except _json.JSONDecodeError:
            # Puede haber múltiples objetos — intentar con el decoder manual
            try:
                decoder = _json.JSONDecoder()
                data, _ = decoder.raw_decode(output, idx)
                payloads = data.get("payloads", [])
                if payloads:
                    return payloads[0].get("text", "").strip()
            except Exception as e:
                print(f"Error parsing: {e}")
    return ""


def hablar(texto, lang):
    modelo_voz = VOCES.get(lang, VOCES["es"])
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    subprocess.run(
        ["piper", "--model", modelo_voz, "--output_file", tmp.name],
        input=texto, text=True, capture_output=True
    )
    subprocess.run(["aplay", "-q", tmp.name])
    os.unlink(tmp.name)

def confirmar_cambio_idioma(nuevo_lang):
    msgs = {
        "es": "Cambio a español. Ahora te respondo en español.",
        "en": "Switching to English. I will now respond in English.",
        "pt": "Mudando para portugues. Agora vou responder em portugues.",
    }
    hablar(msgs[nuevo_lang], nuevo_lang)

def procesar(audio_path, estado):
    texto, lang_stt = transcribir(audio_path)
    os.unlink(audio_path)
    if not texto:
        return estado
    print(f"Tu [{lang_stt.upper()}]: {texto}")
    nuevo_lang = detectar_cambio_idioma(texto)
    if nuevo_lang:
        estado["lang_respuesta"] = nuevo_lang
        guardar_estado(estado)
        confirmar_cambio_idioma(nuevo_lang)
        return estado
    lang_resp = lang_stt if estado["lang_respuesta"] == "auto" else estado["lang_respuesta"]
    respuesta = preguntar_llm(texto, lang_resp)
    print(f"Asistente [{lang_resp.upper()}]: {respuesta}")
    hablar(respuesta, lang_resp)
    return estado

def modo_push_to_talk():
    estado = cargar_estado()
    print(f"Push-to-talk multilingue | Idioma: {estado.get('lang_respuesta', 'auto')}")
    print("Comandos: 'cambia a ingles', 'change to spanish', 'muda para portugues'")
    print("Enter para hablar, Ctrl+C para salir.\n")
    try:
        while True:
            input("Presiona Enter para hablar...")
            estado = procesar(grabar_audio(7), estado)
    except KeyboardInterrupt:
        print("\nSaliendo...")

def modo_wake_word():
    from openwakeword.model import Model
    estado = cargar_estado()
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1,
                    rate=SAMPLE_RATE, input=True, frames_per_buffer=1280)
    print("Escuchando wake word 'hey jarvis'... Ctrl+C para salir")
    hablar("Listo, te escucho.", "es")
    try:
        while True:
            audio = np.frombuffer(stream.read(1280), dtype=np.int16)
            if oww.predict(audio).get("hey_jarvis", 0) > 0.5:
                hablar("Dime", "es")
                estado = procesar(grabar_audio(7), estado)
    except KeyboardInterrupt:
        print("\nSaliendo...")
    finally:
        stream.stop_stream(); stream.close(); p.terminate()

if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "push"
    if modo == "wake":
        modo_wake_word()
    else:
        modo_push_to_talk()

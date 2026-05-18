"""Infrastructure healthchecks for UM890 and DGX."""

import os
import socket
from typing import Dict

from skills.whatsapp.utils.config import Config
from skills.whatsapp.utils.http_client import HttpClient


HTTP = HttpClient(retries=2, backoff_factor=1.5)


def _safe_get(url: str, timeout: int = 10) -> bool:
    try:
        HTTP.get(url, timeout=timeout)
        return True
    except Exception:
        return False


def get_machine_type() -> str:
    return Config.MACHINE_TYPE


def check_ollama_health(base_url: str) -> bool:
    return _safe_get(f"{base_url}/api/tags", timeout=10)


def check_whisper_health(whisper_url: str) -> bool:
    # whisper-server may not expose a dedicated health endpoint, fallback to TCP probe.
    try:
        host_port = whisper_url.replace("http://", "").split("/")[0]
        host, port = host_port.split(":")
        with socket.create_connection((host, int(port)), timeout=3):
            return True
    except Exception:
        return False


def check_tailscale_ip() -> str:
    return os.getenv("TAILSCALE_IP", "unknown")


def validate_models_loaded(base_url: str) -> Dict[str, bool]:
    required = {
        Config.VISION_MODEL,
        Config.FAST_MODEL,
        Config.REASONING_MODEL,
        Config.AGENT_LOCAL_MODEL,
        Config.DGX_LLM_MODEL,
        Config.FALLBACK_DGX_MODEL,
    }
    loaded = {model: False for model in required}

    try:
        resp = HTTP.get(f"{base_url}/api/tags", timeout=15)
        data = resp.json()
        tags = {item.get("name", "") for item in data.get("models", [])}
        for model in required:
            loaded[model] = model in tags
    except Exception:
        pass

    return loaded


def validate_infrastructure() -> dict:
    checks = {
        "machine_type": get_machine_type(),
        "local_ollama": check_ollama_health(Config.LOCAL_OLLAMA_URL),
        "tailscale": check_tailscale_ip(),
        "local_models": validate_models_loaded(Config.LOCAL_OLLAMA_URL),
    }

    if checks["machine_type"] == "um890":
        checks["dgx_remote"] = check_ollama_health(Config.DGX_OLLAMA_URL)
        checks["whisper_dgx"] = check_whisper_health(Config.DGX_WHISPER_URL)
        checks["dgx_models"] = validate_models_loaded(Config.DGX_OLLAMA_URL)
    else:
        checks["whisper_local"] = check_whisper_health(Config.DGX_WHISPER_URL)

    return checks


def _print_report(checks: dict) -> None:
    print(f"Machine: {checks['machine_type']}")
    print(f"Local Ollama: {'OK' if checks['local_ollama'] else 'FAIL'}")
    print(f"Tailscale IP: {checks['tailscale']}")

    if checks.get("dgx_remote") is not None:
        print(f"DGX Remote Ollama: {'OK' if checks['dgx_remote'] else 'FAIL'}")
    if checks.get("whisper_dgx") is not None:
        print(f"Whisper DGX: {'OK' if checks['whisper_dgx'] else 'FAIL'}")
    if checks.get("whisper_local") is not None:
        print(f"Whisper Local: {'OK' if checks['whisper_local'] else 'FAIL'}")

    local_models = checks.get("local_models", {})
    if local_models:
        print("Local model status:")
        for model, ok in sorted(local_models.items()):
            print(f"  - {model}: {'OK' if ok else 'MISSING'}")

    dgx_models = checks.get("dgx_models", {})
    if dgx_models:
        print("DGX model status:")
        for model, ok in sorted(dgx_models.items()):
            print(f"  - {model}: {'OK' if ok else 'MISSING'}")


if __name__ == "__main__":
    _print_report(validate_infrastructure())

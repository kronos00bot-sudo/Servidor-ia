"""Remote/local inference client driven by RouteTarget."""

from typing import Any, Optional

from skills.whatsapp.utils.http_client import HttpClient


class RemoteClient:
    """Execute whisper and ollama generation requests using routed targets."""

    def __init__(self, http_client: Optional[HttpClient] = None):
        self.http = http_client or HttpClient()

    def transcribe(self, whisper_url: str, file_handle: Any, timeout: int = 300) -> dict:
        resp = self.http.post(
            whisper_url,
            files={"file": ("audio.wav", file_handle, "audio/wav")},
            data={"response_format": "json", "language": "auto"},
            timeout=timeout,
        )
        return resp.json()

    def generate(
        self,
        generate_url: str,
        model: str,
        prompt: str,
        timeout: int,
        images: Optional[list] = None,
    ) -> dict:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        if images:
            payload["images"] = images

        resp = self.http.post(generate_url, json=payload, timeout=timeout)
        return resp.json()

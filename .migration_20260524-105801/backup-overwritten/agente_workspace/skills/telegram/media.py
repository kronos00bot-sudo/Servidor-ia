"""Telegram media download and processing helpers."""

from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from skills.telegram.routing.remote_client import RemoteClient
from skills.telegram.routing.task_router import TaskRouter
from skills.telegram.transcriber import transcribe_file
from skills.telegram.utils.http_client import HttpClient

from .utils.config import TelegramConfig


class TelegramMediaClient:
    """Download Telegram files via Bot API."""

    def __init__(self, token: Optional[str] = None, http_client: Optional[HttpClient] = None):
        self.token = token or TelegramConfig.TELEGRAM_BOT_TOKEN
        self.http = http_client or HttpClient()
        self.download_root = TelegramConfig.PROJECT_DIR / "media" / "telegram"
        self.download_root.mkdir(parents=True, exist_ok=True)

    def get_file(self, file_id: str) -> Dict[str, Any]:
        url = f"https://api.telegram.org/bot{self.token}/getFile"
        resp = self.http.get(url, params={"file_id": file_id}, timeout=30)
        return resp.json()

    def download_file(self, file_path: str, destination: Path) -> Path:
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        resp = self.http.get(url, timeout=60)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(resp.content)
        return destination

    def download_attachment(self, message: Dict[str, Any], chat_id: str, msg_id: Any) -> Dict[str, Any]:
        raw_type = message.get("raw_type") or message.get("type")
        file_id = message.get("file_id")
        if not file_id:
            return {"ok": False, "error": "Missing file_id"}

        file_info = self.get_file(file_id)
        result = file_info.get("result") if isinstance(file_info, dict) else None
        file_path = (result or {}).get("file_path")
        if not file_path:
            return {"ok": False, "error": "Missing file_path from Telegram API"}

        file_name = message.get("file_name") or Path(file_path).name
        ext = Path(file_name).suffix or Path(file_path).suffix or _default_suffix(raw_type)
        dest_dir = self.download_root / str(chat_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        destination = dest_dir / f"{int(msg_id):04d}_{Path(file_name).stem}{ext}"
        saved = self.download_file(file_path, destination)
        return {
            "ok": True,
            "kind": raw_type,
            "file_id": file_id,
            "file_path": file_path,
            "file_name": file_name,
            "saved_path": str(saved),
        }


def _default_suffix(raw_type: str) -> str:
    return {
        "voice": ".oga",
        "audio": ".mp3",
        "video": ".mp4",
        "photo": ".jpg",
        "document": ".bin",
    }.get(raw_type, ".bin")


def _extract_video_frames(video_path: Path, output_dir: Path, interval_seconds: int, max_frames: int = 3) -> list[Path]:
    """Extract a small set of frames for visual summarization."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame_%03d.jpg"
    safe_interval = max(1, int(interval_seconds or 30))
    cmd = [
        TelegramConfig.FFMPEG_BIN,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{safe_interval}",
        "-frames:v",
        str(max(1, int(max_frames))),
        str(pattern),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "ffmpeg failed extracting frames").strip())
    return sorted(output_dir.glob("frame_*.jpg"))


def _build_video_visual_summary(video_path: Path, router: TaskRouter, remote: RemoteClient, msg_id: int) -> str:
    """Generate a short visual summary of sampled video frames."""
    frames_dir = TelegramConfig.PROJECT_DIR / "media" / "processed" / "video_frames" / f"{int(msg_id):04d}"
    frames = _extract_video_frames(
        video_path=video_path,
        output_dir=frames_dir,
        interval_seconds=TelegramConfig.VIDEO_FRAME_INTERVAL,
        max_frames=3,
    )
    if not frames:
        return ""

    images_b64: list[str] = []
    for frame in frames:
        raw = frame.read_bytes()
        images_b64.append(base64.b64encode(raw).decode("ascii"))

    prompt = (
        "Describe briefly what is happening in these video frames. "
        "Return 2-4 concise bullet points in Spanish."
    )
    route_vision = getattr(router, "route_vision", None)
    route = route_vision({"type": "video", "path": str(video_path)}) if callable(route_vision) else router.route_chat(prompt)
    try:
        raw = remote.generate(
            generate_url=route.host,
            model=route.model,
            prompt=prompt,
            timeout=route.timeout,
            images=images_b64,
        )
    except Exception:
        fallback = router.route_fallback("vision")
        raw = remote.generate(
            generate_url=fallback.host,
            model=fallback.model,
            prompt=prompt,
            timeout=fallback.timeout,
            images=images_b64,
        )
    return (raw.get("response") or "").strip()


def _process_video_media(saved_path: Path, msg_id: int, router: TaskRouter) -> Dict[str, Any]:
    """Combine audio transcription and sampled-frame visual summary for videos."""
    transcript_result = transcribe_file(str(saved_path), int(msg_id))
    transcript_text = (transcript_result.get("text") or "").strip()
    transcript_error = (transcript_result.get("error") or "").strip()

    visual_summary = ""
    visual_error = ""
    try:
        visual_summary = _build_video_visual_summary(saved_path, router=router, remote=RemoteClient(), msg_id=msg_id)
    except Exception as exc:
        visual_error = str(exc)

    sections: list[str] = []
    if transcript_text:
        sections.append(f"Transcripcion de audio:\n{transcript_text}")
    if visual_summary:
        sections.append(f"Resumen visual:\n{visual_summary}")

    if sections:
        return {
            "id": msg_id,
            "text": "\n\n".join(sections),
            "error": None,
            "audio_error": transcript_error or None,
            "visual_error": visual_error or None,
        }

    errors = [e for e in [transcript_error, visual_error] if e]
    return {
        "id": msg_id,
        "text": None,
        "error": "; ".join(errors) if errors else "video processing failed",
        "audio_error": transcript_error or None,
        "visual_error": visual_error or None,
    }


def _read_text_file_best_effort(path: Path, max_chars: int = 4000) -> str:
    """Read text-like documents with tolerant decoding and bounded output."""
    raw = path.read_bytes()
    for encoding in ("utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            text = ""
    text = " ".join((text or "").split())
    return text[:max_chars].strip()


def _extract_pdf_text(path: Path, timeout_seconds: int = 25, max_chars: int = 4000) -> str:
    """Extract PDF text using pdftotext when available."""
    if shutil.which("pdftotext") is None:
        return ""

    cmd = ["pdftotext", "-layout", str(path), "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    if result.returncode != 0:
        return ""
    text = " ".join((result.stdout or "").split())
    return text[:max_chars].strip()


def _summarize_image_document(path: Path, router: TaskRouter) -> str:
    """Build a short Spanish summary for image documents."""
    raw = path.read_bytes()
    image_b64 = base64.b64encode(raw).decode("ascii")
    prompt = (
        "Describe brevemente el contenido principal de esta imagen en espanol. "
        "Responde en 2-4 puntos claros."
    )
    route_vision = getattr(router, "route_vision", None)
    route = route_vision({"type": "document_image", "path": str(path)}) if callable(route_vision) else router.route_chat(prompt)
    remote = RemoteClient()
    try:
        raw_resp = remote.generate(
            generate_url=route.host,
            model=route.model,
            prompt=prompt,
            timeout=route.timeout,
            images=[image_b64],
        )
    except Exception:
        fallback = router.route_fallback("vision")
        raw_resp = remote.generate(
            generate_url=fallback.host,
            model=fallback.model,
            prompt=prompt,
            timeout=fallback.timeout,
            images=[image_b64],
        )
    return (raw_resp.get("response") or "").strip()


def _process_document_media(saved_path: Path, msg_id: int, message: Dict[str, Any], router: TaskRouter) -> Dict[str, Any]:
    """Best-effort processing for Telegram documents without blocking moderation flow."""
    mime = (message.get("mime_type") or "").lower()
    ext = saved_path.suffix.lower()
    file_name = message.get("file_name") or saved_path.name

    text_ext = {".txt", ".md", ".csv", ".json", ".log", ".py", ".yaml", ".yml", ".xml", ".ini", ".toml"}
    image_ext = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

    extracted = ""
    if mime.startswith("text/") or ext in text_ext:
        extracted = _read_text_file_best_effort(saved_path)
    elif mime == "application/pdf" or ext == ".pdf":
        extracted = _extract_pdf_text(saved_path)
    elif mime.startswith("audio/"):
        audio = transcribe_file(str(saved_path), int(msg_id))
        extracted = (audio.get("text") or "").strip()
    elif mime.startswith("video/"):
        video = _process_video_media(saved_path, int(msg_id), router=router)
        extracted = (video.get("text") or "").strip()
    elif mime.startswith("image/") or ext in image_ext:
        extracted = _summarize_image_document(saved_path, router=router)

    if extracted:
        return {
            "id": msg_id,
            "text": f"[document] {file_name}\n\n{extracted}",
            "error": None,
        }

    size = 0
    try:
        size = saved_path.stat().st_size
    except OSError:
        pass
    return {
        "id": msg_id,
        "text": (
            "[document] Se recibio un documento pero no se pudo extraer su contenido automaticamente. "
            f"Nombre: {file_name}. MIME: {mime or 'desconocido'}. Tamano: {size} bytes."
        ),
        "error": None,
    }


def process_telegram_media(message: Dict[str, Any], router: TaskRouter, media_client: Optional[TelegramMediaClient] = None) -> Dict[str, Any]:
    """Download and process a Telegram media message using the shared core processors."""
    media_client = media_client or TelegramMediaClient()
    chat_id = message.get("chat_id") or "unknown"
    msg_id = message.get("message_id") or 0
    raw_type = message.get("raw_type") or message.get("type")

    if raw_type not in {"voice", "audio", "photo", "document", "video"}:
        return {"ok": False, "error": f"Unsupported media type: {raw_type}"}

    downloaded = media_client.download_attachment(message, chat_id=chat_id, msg_id=msg_id)
    if not downloaded.get("ok"):
        return downloaded

    saved_path = Path(downloaded["saved_path"])
    result: Dict[str, Any]

    if raw_type in {"voice", "audio"}:
        result = transcribe_file(str(saved_path), int(msg_id))
    elif raw_type == "video":
        result = _process_video_media(saved_path, int(msg_id), router=router)
    elif raw_type == "photo":
        result = {
            "id": msg_id,
            "text": None,
            "error": "photo processing is disabled in telegram-only mode",
        }
    elif raw_type == "document":
        result = _process_document_media(saved_path, int(msg_id), message=message, router=router)
    else:
        result = {"id": msg_id, "text": None, "error": f"Unsupported media type: {raw_type}"}

    return {
        "ok": True,
        "kind": raw_type,
        "download": downloaded,
        "result": result,
        "text": result.get("text"),
        "error": result.get("error"),
    }

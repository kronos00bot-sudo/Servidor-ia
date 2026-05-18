"""Task routing policy for distributed WhatsApp processing."""

from dataclasses import dataclass

from skills.whatsapp.utils.config import Config


@dataclass(frozen=True)
class RouteTarget:
    """Represents where and how a task should run."""

    key: str
    host: str
    model: str
    timeout: int


class TaskRouter:
    """Route tasks to UM890 local models or DGX remote services."""

    def __init__(self, config: Config):
        self.config = config

    def route_transcription(self, message: dict) -> RouteTarget:
        return RouteTarget(
            key="dgx_whisper",
            host=self.config.DGX_WHISPER_URL,
            model="whisper-server",
            timeout=self.config.TIMEOUTS["whisper"],
        )

    def route_vision(self, message: dict) -> RouteTarget:
        return RouteTarget(
            key="um890_gemma4",
            host=f"{self.config.LOCAL_OLLAMA_URL}/api/generate",
            model=self.config.VISION_MODEL,
            timeout=self.config.TIMEOUTS["vision"],
        )

    def route_chat(self, prompt: str, urgency: bool = False) -> RouteTarget:
        _ = urgency
        return RouteTarget(
            key="um890_qwen35",
            host=f"{self.config.LOCAL_OLLAMA_URL}/api/generate",
            model=self.config.FAST_MODEL,
            timeout=self.config.TIMEOUTS["chat"],
        )

    def route_reasoning(self, prompt: str, complexity: int = 0) -> RouteTarget:
        _ = prompt
        if complexity <= 5:
            return RouteTarget(
                key="um890_qwen36",
                host=f"{self.config.LOCAL_OLLAMA_URL}/api/generate",
                model=self.config.REASONING_MODEL,
                timeout=self.config.TIMEOUTS["reasoning"],
            )
        if complexity <= 8:
            return RouteTarget(
                key="um890_nemotron33",
                host=f"{self.config.LOCAL_OLLAMA_URL}/api/generate",
                model=self.config.AGENT_LOCAL_MODEL,
                timeout=self.config.TIMEOUTS["reasoning"],
            )
        return RouteTarget(
            key="dgx_nemotron_120b",
            host=f"{self.config.DGX_OLLAMA_URL}/api/generate",
            model=self.config.DGX_LLM_MODEL,
            timeout=self.config.TIMEOUTS["translation"],
        )

    def route_document(self, message: dict) -> RouteTarget:
        _ = message
        return RouteTarget(
            key="dgx_nemotron_120b",
            host=f"{self.config.DGX_OLLAMA_URL}/api/generate",
            model=self.config.DGX_LLM_MODEL,
            timeout=self.config.TIMEOUTS["document"],
        )

    def route_translation(self, text: str) -> RouteTarget:
        _ = text
        return RouteTarget(
            key="dgx_nemotron_120b",
            host=f"{self.config.DGX_OLLAMA_URL}/api/generate",
            model=self.config.DGX_LLM_MODEL,
            timeout=self.config.TIMEOUTS["translation"],
        )

    def route_fallback(self, task_type: str) -> RouteTarget:
        if task_type == "vision":
            return RouteTarget(
                key="dgx_gemma4_26b",
                host=f"{self.config.DGX_OLLAMA_URL}/api/generate",
                model=self.config.DGX_VISION_MODEL,
                timeout=self.config.TIMEOUTS["vision_fallback"],
            )
        if task_type == "translation":
            return RouteTarget(
                key="dgx_gptoss_120b",
                host=f"{self.config.DGX_OLLAMA_URL}/api/generate",
                model=self.config.FALLBACK_DGX_MODEL,
                timeout=self.config.TIMEOUTS["translation"],
            )

        return RouteTarget(
            key="um890_qwen35",
            host=f"{self.config.LOCAL_OLLAMA_URL}/api/generate",
            model=self.config.FAST_MODEL,
            timeout=self.config.TIMEOUTS["chat"],
        )

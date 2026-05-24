"""HTTP client with retries, backoff and error classification."""

import re
import time
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

import requests

from .exceptions import NetworkError, RetryableError


class HttpClient:
    """Simple resilient HTTP client for local and remote inference services."""

    def __init__(self, retries: int = 3, backoff_factor: float = 2.0):
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.session = requests.Session()

    @staticmethod
    def sanitize_url(url: str) -> str:
        try:
            parts = urlsplit(url)
            redacted_path = re.sub(r"/bot[^/]+", "/bot<redacted>", parts.path)
            return urlunsplit((parts.scheme, parts.netloc, redacted_path, "", ""))
        except Exception:
            return "<redacted-url>"

    def _request(self, method: str, url: str, timeout: int = 60, **kwargs: Any) -> requests.Response:
        delay = 1.0
        last_error: Optional[Exception] = None
        safe_url = self.sanitize_url(url)

        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.request(method=method, url=url, timeout=timeout, **kwargs)

                if 500 <= resp.status_code <= 599:
                    raise RetryableError(f"Server error {resp.status_code} from {safe_url}")

                resp.raise_for_status()
                return resp
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt == self.retries:
                    raise NetworkError(f"Network error calling {safe_url}: {exc}") from exc
            except RetryableError as exc:
                last_error = exc
                if attempt == self.retries:
                    raise NetworkError(str(exc)) from exc
            except requests.RequestException as exc:
                raise NetworkError(f"HTTP error calling {safe_url}: {exc}") from exc

            time.sleep(delay)
            delay *= self.backoff_factor

        raise NetworkError(f"Unexpected request failure for {safe_url}: {last_error}")

    def get(self, url: str, params: Optional[dict] = None, timeout: int = 60) -> requests.Response:
        return self._request("GET", url, params=params, timeout=timeout)

    def post(
        self,
        url: str,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        files: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: int = 120,
    ) -> requests.Response:
        return self._request(
            "POST",
            url,
            json=json,
            data=data,
            files=files,
            headers=headers,
            timeout=timeout,
        )

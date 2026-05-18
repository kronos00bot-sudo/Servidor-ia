"""HTTP client with retries, backoff and error classification."""

import time
from typing import Any, Optional

import requests

from .exceptions import NetworkError, RetryableError


class HttpClient:
    """Simple resilient HTTP client for local and remote inference services."""

    def __init__(self, retries: int = 3, backoff_factor: float = 2.0):
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.session = requests.Session()

    def _request(self, method: str, url: str, timeout: int = 60, **kwargs: Any) -> requests.Response:
        delay = 1.0
        last_error: Optional[Exception] = None

        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.request(method=method, url=url, timeout=timeout, **kwargs)

                # Retry only transient server-side failures.
                if 500 <= resp.status_code <= 599:
                    raise RetryableError(f"Server error {resp.status_code} from {url}")

                resp.raise_for_status()
                return resp
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt == self.retries:
                    raise NetworkError(f"Network error calling {url}: {exc}") from exc
            except RetryableError as exc:
                last_error = exc
                if attempt == self.retries:
                    raise NetworkError(str(exc)) from exc
            except requests.RequestException as exc:
                raise NetworkError(f"HTTP error calling {url}: {exc}") from exc

            time.sleep(delay)
            delay *= self.backoff_factor

        raise NetworkError(f"Unexpected request failure for {url}: {last_error}")

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

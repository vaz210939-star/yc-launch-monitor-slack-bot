from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class HttpError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class UrlLibTransport:
    def __init__(self, timeout: float = 25.0, max_bytes: int = 5_000_000):
        self.timeout = timeout
        self.max_bytes = max_bytes

    def _request(
        self,
        url: str,
        *,
        method: str,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> bytes:
        if params:
            url = f"{url}?{urlencode(params)}"
        request_headers = {"User-Agent": "yc-launch-monitor/0.1", **(headers or {})}
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = Request(url, data=body, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read(self.max_bytes + 1)
                if len(data) > self.max_bytes:
                    raise HttpError(f"Response exceeds {self.max_bytes} bytes")
                return data
        except HTTPError as exc:
            try:
                retry_after = None
                raw_retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if raw_retry_after:
                    try:
                        retry_after = float(raw_retry_after)
                    except ValueError:
                        pass
                status_code = exc.code
                failed_url = request.full_url
            finally:
                exc.close()
            raise HttpError(
                f"HTTP {status_code} from {failed_url}",
                status_code=status_code,
                retry_after=retry_after,
            ) from exc
        except URLError as exc:
            raise HttpError(f"Network error for {request.full_url}: {exc.reason}") from exc

    def get_text(self, url: str, *, headers=None, params=None) -> str:
        return self._request(url, method="GET", headers=headers, params=params).decode("utf-8", "replace")

    def get_json(self, url: str, *, headers=None, params=None) -> dict[str, Any]:
        return json.loads(self.get_text(url, headers=headers, params=params))

    def post_json(self, url: str, payload: dict[str, Any], *, headers=None) -> dict[str, Any]:
        raw = self._request(url, method="POST", headers=headers, payload=payload)
        return json.loads(raw.decode("utf-8", "replace"))

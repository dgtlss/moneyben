"""Small stdlib-backed HTTP helpers with a requests-like surface."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class HTTPError(RuntimeError):
    pass


@dataclass
class SimpleResponse:
    status_code: int
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            detail = self.body.decode("utf-8", errors="replace").strip()
            if detail:
                raise HTTPError(f"HTTP {self.status_code}: {detail[:500]}")
            raise HTTPError(f"HTTP {self.status_code}")


class SimpleSession:
    def __init__(self):
        self.headers: dict[str, str] = {}

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: int = 20) -> SimpleResponse:
        if params:
            query = parse.urlencode(params)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"
        req = request.Request(url, headers=self.headers, method="GET")
        return self._send(req, timeout=timeout)

    def post(self, url: str, json: dict[str, Any] | None = None, timeout: int = 20) -> SimpleResponse:
        payload = None if json is None else __import__("json").dumps(json).encode("utf-8")
        req = request.Request(url, headers=self.headers, data=payload, method="POST")
        return self._send(req, timeout=timeout)

    def _send(self, req: request.Request, timeout: int) -> SimpleResponse:
        try:
            with request.urlopen(req, timeout=timeout) as response:
                return SimpleResponse(status_code=response.status, body=response.read())
        except error.HTTPError as exc:
            return SimpleResponse(status_code=exc.code, body=exc.read())

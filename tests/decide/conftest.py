"""Shared mocking helpers for decide.py's HTTP calls.

Every test mocks `urllib.request.urlopen` directly (per project policy: no real
network calls in tests). These two helpers build the shapes `urlopen` needs to
produce: a context-manager response, or a raised HTTPError.
"""

import io
import urllib.error


class FakeResponse:
    """A minimal stand-in for the context manager `urlopen()` returns."""

    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def fake_response(body: bytes, status: int = 200) -> FakeResponse:
    return FakeResponse(body, status)


def fake_http_error(code: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url="https://example.invalid", code=code, msg="error", hdrs=None, fp=io.BytesIO(body))

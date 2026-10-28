"""Every failure path must escalate — never act, never review, never raise.

Covers: HTTP error status, timeout, connection error, empty body, non-JSON body,
a CF "refusal" (content that isn't the requested JSON shape), and a missing
credential. None of these may leak the API key into the returned error string.
"""

import json
import urllib.error
from unittest.mock import patch

from conftest import fake_http_error, fake_response
from decide import decide

SECRET = "sk-test-super-secret-token"


def _one_predicate(name="q1"):
    return [{"name": name, "type": "predicate", "instructions": "Is this true?"}]


class TestJevFailuresEscalate:
    @patch("decide.urllib.request.urlopen")
    def test_http_403_escalates_without_leaking_key(self, mock_urlopen):
        mock_urlopen.side_effect = fake_http_error(403, body=f"blocked by WAF, key={SECRET}".encode())
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET)
        answer = result["q1"]
        assert answer["band"] == "escalate"
        assert answer["value"] is None
        assert answer["probability"] is None
        assert answer["source"] == "jev"
        assert "403" in answer["error"]
        assert SECRET not in answer["error"]

    @patch("decide.urllib.request.urlopen")
    def test_non_http_scheme_escalates_without_network_call(self, mock_urlopen):
        # Bandit B310 (CodeFactor): urlopen must never be reachable with an
        # unvalidated scheme (file:/, etc.) — api_base is operator-supplied,
        # not request content, but a misconfigured value must still escalate
        # cleanly rather than ever attempt urlopen().
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET, api_base="file:///etc/passwd")
        answer = result["q1"]
        assert answer["band"] == "escalate"
        assert "scheme" in answer["error"]
        mock_urlopen.assert_not_called()

    @patch("decide.urllib.request.urlopen")
    def test_timeout_escalates(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET)
        answer = result["q1"]
        assert answer["band"] == "escalate"
        assert "time" in answer["error"].lower()

    @patch("decide.urllib.request.urlopen")
    def test_connection_error_escalates(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("no route to host")
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET)
        answer = result["q1"]
        assert answer["band"] == "escalate"
        assert answer["error"]

    @patch("decide.urllib.request.urlopen")
    def test_empty_body_escalates(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(b"")
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET)
        assert result["q1"]["band"] == "escalate"

    @patch("decide.urllib.request.urlopen")
    def test_non_json_body_escalates(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(b"not json at all")
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET)
        assert result["q1"]["band"] == "escalate"

    @patch("decide.urllib.request.urlopen")
    def test_missing_answers_key_escalates(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(json.dumps({"model": "jev-1.13.0"}).encode())
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET)
        assert result["q1"]["band"] == "escalate"

    @patch("decide.urllib.request.urlopen")
    def test_missing_api_key_escalates_without_network_call(self, mock_urlopen):
        result = decide("state", _one_predicate(), backend="jev", api_key="")
        answer = result["q1"]
        assert answer["band"] == "escalate"
        assert "TYPESAFE_API_KEY" in answer["error"]
        mock_urlopen.assert_not_called()

    @patch("decide.urllib.request.urlopen")
    def test_never_raises_on_any_backend_failure(self, mock_urlopen):
        # A deliberately unlisted exception type — not HTTPError/TimeoutError/
        # URLError, and not RuntimeError either (that would pass by coincidence
        # via an unrelated except clause). _post_json's catch-all must still
        # turn this into an escalate verdict rather than let it propagate.
        mock_urlopen.side_effect = ConnectionResetError("peer reset")
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET)
        assert result["q1"]["band"] == "escalate"
        assert "ConnectionResetError" in result["q1"]["error"]

    @patch("decide.urllib.request.urlopen")
    def test_unlisted_exception_does_not_leak_key(self, mock_urlopen):
        mock_urlopen.side_effect = ConnectionResetError(f"peer reset, key={SECRET}")
        result = decide("state", _one_predicate(), backend="jev", api_key=SECRET)
        assert result["q1"]["band"] == "escalate"
        assert SECRET not in result["q1"]["error"]


class TestCfFailuresEscalate:
    def test_missing_token_escalates_without_network_call(self):
        with patch("decide.urllib.request.urlopen") as mock_urlopen:
            result = decide("state", _one_predicate(), backend="cf", api_key="", api_base="https://example.invalid")
            answer = result["q1"]
            assert answer["band"] == "escalate"
            assert "CF_WORKERS_AI_TOKEN" in answer["error"]
            mock_urlopen.assert_not_called()

    def test_missing_base_url_escalates_without_network_call(self):
        with patch("decide.urllib.request.urlopen") as mock_urlopen:
            result = decide("state", _one_predicate(), backend="cf", api_key=SECRET, api_base="")
            answer = result["q1"]
            assert answer["band"] == "escalate"
            assert "LLM_BASE_URL" in answer["error"]
            mock_urlopen.assert_not_called()

    @patch("decide.urllib.request.urlopen")
    def test_refusal_non_json_content_escalates(self, mock_urlopen):
        body = json.dumps({"choices": [{"message": {"content": "I can't answer that."}}]}).encode()
        mock_urlopen.return_value = fake_response(body)
        result = decide("state", _one_predicate(), backend="cf", api_key=SECRET, api_base="https://example.invalid")
        answer = result["q1"]
        assert answer["band"] == "escalate"
        assert answer["probability"] is None

    @patch("decide.urllib.request.urlopen")
    def test_http_error_does_not_leak_token(self, mock_urlopen):
        mock_urlopen.side_effect = fake_http_error(401, body=f"token={SECRET}".encode())
        result = decide("state", _one_predicate(), backend="cf", api_key=SECRET, api_base="https://example.invalid")
        answer = result["q1"]
        assert answer["band"] == "escalate"
        assert SECRET not in answer["error"]

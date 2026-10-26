"""Clef backend (Cloudflare Workers AI decision model).

Verified 2026-10-26 against developers.cloudflare.com/workers-ai/models/clef-flash/
and its schema-input.json / schema-output.json:

- POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef-flash
  (or .../clef), Authorization: Bearer <token>
- body: {"model": "clef-flash"|"clef", "state", "questions": {id: {type, instructions, criteria?}}}
- answers: same noul / choice / score shapes as Jev (choice and score carry "confidence")

UNVERIFIED (no live call yet): whether the REST response is wrapped in Cloudflare's usual
{"result": ...} envelope, so both shapes are accepted.
"""

import json
from unittest.mock import patch

import pytest
from conftest import fake_response
from decide import DecideError, decide

BASE = "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1"
Q = [{"name": "q1", "type": "predicate", "instructions": "Is it a bug?"}]


def _ok(answers, wrapped=True):
    body = {"model": "clef-flash", "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 0}}
    return fake_response(json.dumps({"result": body, "success": True} if wrapped else body).encode())


def _request(mock_urlopen):
    (request,), _kwargs = mock_urlopen.call_args
    return request


class TestClefRequestShape:
    @patch("decide.urllib.request.urlopen")
    def test_url_derived_from_llm_base_url_and_bearer(self, mock_urlopen):
        mock_urlopen.return_value = _ok({"q1": {"type": "noul", "noul": 0.9}})
        decide("s", Q, backend="clef", api_key="t1", api_base=BASE)
        request = _request(mock_urlopen)
        assert (
            request.full_url == "https://api.cloudflare.com/client/v4/accounts/abc123/ai/run/@cf/cloudflare/clef-flash"
        )
        assert request.get_header("Authorization") == "Bearer t1"

    @patch("decide.urllib.request.urlopen")
    def test_body_uses_the_jev_wire_shape(self, mock_urlopen):
        mock_urlopen.return_value = _ok({"q1": {"type": "noul", "noul": 0.9}})
        decide("s", Q, backend="clef", api_key="t1", api_base=BASE)
        assert json.loads(_request(mock_urlopen).data) == {
            "model": "clef-flash",
            "state": "s",
            "questions": {"q1": {"type": "noul", "instructions": "Is it a bug?"}},
        }

    @patch("decide.urllib.request.urlopen")
    def test_model_clef_selects_the_27b_endpoint(self, mock_urlopen):
        mock_urlopen.return_value = _ok({"q1": {"type": "noul", "noul": 0.9}})
        decide("s", Q, backend="clef", api_key="t1", api_base=BASE, model="clef")
        request = _request(mock_urlopen)
        assert request.full_url.endswith("/ai/run/@cf/cloudflare/clef")
        assert json.loads(request.data)["model"] == "clef"

    def test_unknown_model_is_a_malformed_call(self):
        with pytest.raises(DecideError):
            decide("s", Q, backend="clef", api_key="t1", api_base=BASE, model="llama")


class TestClefAnswers:
    @pytest.mark.parametrize("wrapped", [True, False])
    @patch("decide.urllib.request.urlopen")
    def test_noul_answer_bands_and_source(self, mock_urlopen, wrapped):
        mock_urlopen.return_value = _ok({"q1": {"type": "noul", "noul": 0.05}}, wrapped=wrapped)
        result = decide("s", Q, backend="clef", api_key="t1", api_base=BASE)
        assert result["q1"] == {"value": False, "probability": 0.05, "band": "act", "source": "clef", "error": None}

    @patch("decide.urllib.request.urlopen")
    def test_choice_answer_uses_confidence(self, mock_urlopen):
        mock_urlopen.return_value = _ok(
            {"c": {"type": "choice", "choice": "bug", "probabilities": {"bug": 0.6, "docs": 0.4}, "confidence": 0.3}}
        )
        q = [{"name": "c", "type": "choice", "instructions": "Kind?", "choices": ["bug", "docs"]}]
        result = decide("s", q, backend="clef", api_key="t1", api_base=BASE)
        assert result["c"]["value"] == "bug"
        assert result["c"]["band"] == "review"
        assert result["c"]["source"] == "clef"


class TestClefMissingConfig:
    def test_missing_token_escalates(self, monkeypatch):
        monkeypatch.delenv("CF_WORKERS_AI_TOKEN", raising=False)
        result = decide("s", Q, backend="clef", api_base=BASE)
        assert result["q1"]["band"] == "escalate"
        assert result["q1"]["error"] == "missing CF_WORKERS_AI_TOKEN"

    def test_missing_base_escalates(self, monkeypatch):
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        result = decide("s", Q, backend="clef", api_key="t1")
        assert result["q1"]["band"] == "escalate"
        assert result["q1"]["error"] == "missing LLM_BASE_URL"

    def test_base_without_ai_v1_suffix_escalates(self):
        result = decide("s", Q, backend="clef", api_key="t1", api_base="https://example.com/v1")
        assert result["q1"]["band"] == "escalate"
        assert "LLM_BASE_URL" in result["q1"]["error"]

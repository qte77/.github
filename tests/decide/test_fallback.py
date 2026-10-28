"""Cloudflare Workers AI fallback backend.

Shape (OpenAI-compatible `{base}/chat/completions`) is the convention already
used elsewhere in the qte77 estate (LLM_BASE_URL + api_base) — NOT independently
re-verified against Cloudflare's own docs this session. See decide.py's module
docstring and DEFAULT_CF_MODEL comment.
"""

import json
from unittest.mock import patch

from conftest import fake_response
from decide import DEFAULT_CF_MODEL, decide


def _captured_request(mock_urlopen):
    (request,), _kwargs = mock_urlopen.call_args
    return request


class TestCfRequestShape:
    @patch("decide.urllib.request.urlopen")
    def test_url_and_default_model(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"choices": [{"message": {"content": '{"value": true}'}}]}).encode()
        )
        decide(
            "state",
            [{"name": "q1", "type": "predicate", "instructions": "Is it fine?"}],
            backend="cf",
            api_key="tok",
            api_base="https://gateway.example",
        )
        request = _captured_request(mock_urlopen)
        assert request.full_url == "https://gateway.example/chat/completions"
        assert request.get_header("Authorization") == "Bearer tok"
        assert request.get_header("User-agent") == "qte77-decide/0.1.0"
        body = json.loads(request.data)
        assert body["model"] == DEFAULT_CF_MODEL
        assert body["messages"][0]["role"] == "user"
        assert "Is it fine?" in body["messages"][0]["content"]

    @patch("decide.urllib.request.urlopen")
    def test_explicit_model_overrides_default(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"choices": [{"message": {"content": '{"value": true}'}}]}).encode()
        )
        decide(
            "state",
            [{"name": "q1", "type": "predicate", "instructions": "x?"}],
            backend="cf",
            api_key="tok",
            api_base="https://gateway.example",
            model="@cf/other/model",
        )
        body = json.loads(_captured_request(mock_urlopen).data)
        assert body["model"] == "@cf/other/model"

    @patch("decide.urllib.request.urlopen")
    def test_choice_question_includes_labels_in_prompt(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"choices": [{"message": {"content": '{"value": "a"}'}}]}).encode()
        )
        decide(
            "state",
            [{"name": "c", "type": "choice", "instructions": "Pick", "choices": ["a", "b"]}],
            backend="cf",
            api_key="tok",
            api_base="https://gateway.example",
        )
        prompt = json.loads(_captured_request(mock_urlopen).data)["messages"][0]["content"]
        assert "a" in prompt and "b" in prompt


class TestCfResponseParsing:
    @patch("decide.urllib.request.urlopen")
    def test_probability_is_always_none_and_band_is_escalate(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"choices": [{"message": {"content": '{"value": true}'}}]}).encode()
        )
        result = decide(
            "state",
            [{"name": "q1", "type": "predicate", "instructions": "x?"}],
            backend="cf",
            api_key="tok",
            api_base="https://gateway.example",
        )
        answer = result["q1"]
        assert answer["value"] is True
        assert answer["probability"] is None
        assert answer["band"] == "escalate"
        assert answer["source"] == "cf"
        assert answer["error"] is None

    @patch("decide.urllib.request.urlopen")
    def test_fenced_json_content_is_unwrapped(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"choices": [{"message": {"content": '```json\n{"value": "a"}\n```'}}]}).encode()
        )
        result = decide(
            "state",
            [{"name": "c", "type": "choice", "instructions": "Pick", "choices": ["a", "b"]}],
            backend="cf",
            api_key="tok",
            api_base="https://gateway.example",
        )
        assert result["c"]["value"] == "a"

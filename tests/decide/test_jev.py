"""Jev backend: verified wire shape.

Verified 2026-10-10 against docs.typesafe.ai (/api, /models, /confidence) and
the installed typesafe-sdk==0.7.1 source (_core/endpoints.py, _core/transport.py,
_core/constants.py) via the real caller in qte77/feelings' eval/jev_gate.py:

- POST https://api.typesafe.ai/v1/systemone
- Authorization: Bearer <key>, Content-Type: application/json
- body: {"state", "model", "questions": {name: {type, instructions, criteria?}}}
- noul answer: {"type": "noul", "noul": <0-1 float>}
- choice answer: {"type": "choice", "choice": <label>, "probabilities": {...}, "confidence": <0-1 float>}
- score answer: {"type": "score", "score": <float>, "probabilities": {...}, "confidence": <0-1 float>}
"""

import json
from unittest.mock import patch

from conftest import fake_response
from decide import DEFAULT_JEV_MODEL, decide


def _captured_request(mock_urlopen):
    (request,), _kwargs = mock_urlopen.call_args
    return request


class TestJevRequestShape:
    @patch("decide.urllib.request.urlopen")
    def test_url_method_and_headers(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"model": DEFAULT_JEV_MODEL, "answers": {"q1": {"type": "noul", "noul": 0.9}}}).encode()
        )
        decide("some state", [{"name": "q1", "type": "predicate", "instructions": "Is it fine?"}], api_key="k1")
        request = _captured_request(mock_urlopen)
        assert request.full_url == "https://api.typesafe.ai/v1/systemone"
        assert request.get_method() == "POST"
        assert request.get_header("Authorization") == "Bearer k1"
        assert request.get_header("Content-type") == "application/json"
        assert request.get_header("User-agent") == "qte77-decide/0.1.0"

    @patch("decide.urllib.request.urlopen")
    def test_body_shape_and_default_model(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"model": DEFAULT_JEV_MODEL, "answers": {"q1": {"type": "noul", "noul": 0.1}}}).encode()
        )
        decide("some state", [{"name": "q1", "type": "predicate", "instructions": "Is it fine?"}], api_key="k1")
        request = _captured_request(mock_urlopen)
        body = json.loads(request.data)
        assert body == {
            "state": "some state",
            "model": DEFAULT_JEV_MODEL,
            "questions": {"q1": {"type": "noul", "instructions": "Is it fine?"}},
        }

    @patch("decide.urllib.request.urlopen")
    def test_explicit_model_overrides_default(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"model": "jev-preview", "answers": {"q1": {"type": "noul", "noul": 0.5}}}).encode()
        )
        decide(
            "s",
            [{"name": "q1", "type": "predicate", "instructions": "x?"}],
            api_key="k1",
            model="jev-preview",
        )
        request = _captured_request(mock_urlopen)
        assert json.loads(request.data)["model"] == "jev-preview"

    @patch("decide.urllib.request.urlopen")
    def test_choice_and_score_questions_build_criteria(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps(
                {
                    "model": DEFAULT_JEV_MODEL,
                    "answers": {
                        "c": {
                            "type": "choice",
                            "choice": "a",
                            "probabilities": {"a": 0.9, "b": 0.1},
                            "confidence": 0.9,
                        },
                        "s": {
                            "type": "score",
                            "score": 1.2,
                            "probabilities": {"0": 0.1, "1": 0.7, "2": 0.2},
                            "confidence": 0.6,
                        },
                    },
                }
            ).encode()
        )
        decide(
            "s",
            [
                {"name": "c", "type": "choice", "instructions": "Pick", "choices": ["a", "b"]},
                {"name": "s", "type": "score", "instructions": "Rate", "levels": ["lo", "mid", "hi"]},
            ],
            api_key="k1",
        )
        body = json.loads(_captured_request(mock_urlopen).data)
        assert body["questions"]["c"] == {"type": "choice", "instructions": "Pick", "criteria": {"a": None, "b": None}}
        assert body["questions"]["s"] == {"type": "score", "instructions": "Rate", "criteria": ["lo", "mid", "hi"]}


class TestJevResponseParsing:
    @patch("decide.urllib.request.urlopen")
    def test_noul_answer_uses_raw_probability_symmetric_gate(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"model": DEFAULT_JEV_MODEL, "answers": {"q1": {"type": "noul", "noul": 0.05}}}).encode()
        )
        result = decide("s", [{"name": "q1", "type": "predicate", "instructions": "x?"}], api_key="k1")
        answer = result["q1"]
        assert answer["probability"] == 0.05
        assert answer["value"] is False
        assert answer["band"] == "act"  # confidently false: 0.05 <= 1 - 0.85
        assert answer["source"] == "jev"
        assert answer["error"] is None

    @patch("decide.urllib.request.urlopen")
    def test_choice_answer_uses_confidence_not_top_probability(self, mock_urlopen):
        # top probability 0.9, but a deliberately different confidence (0.3) to
        # prove we read the vendor's `confidence` field, not probabilities[choice].
        mock_urlopen.return_value = fake_response(
            json.dumps(
                {
                    "model": DEFAULT_JEV_MODEL,
                    "answers": {
                        "c": {"type": "choice", "choice": "a", "probabilities": {"a": 0.9, "b": 0.1}, "confidence": 0.3}
                    },
                }
            ).encode()
        )
        result = decide(
            "s", [{"name": "c", "type": "choice", "instructions": "Pick", "choices": ["a", "b"]}], api_key="k1"
        )
        answer = result["c"]
        assert answer["value"] == "a"
        assert answer["probability"] == 0.3
        assert answer["band"] == "review"  # low confidence must NOT act, even with a high top probability

    @patch("decide.urllib.request.urlopen")
    def test_score_answer_uses_confidence(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps(
                {
                    "model": DEFAULT_JEV_MODEL,
                    "answers": {"s": {"type": "score", "score": 2.1, "probabilities": {"2": 0.9}, "confidence": 0.95}},
                }
            ).encode()
        )
        result = decide(
            "s", [{"name": "s", "type": "score", "instructions": "Rate", "levels": ["lo", "mid", "hi"]}], api_key="k1"
        )
        answer = result["s"]
        assert answer["value"] == 2.1
        assert answer["probability"] == 0.95
        assert answer["band"] == "act"

    @patch("decide.urllib.request.urlopen")
    def test_unrecognized_answer_type_escalates(self, mock_urlopen):
        mock_urlopen.return_value = fake_response(
            json.dumps({"model": DEFAULT_JEV_MODEL, "answers": {"q1": {"type": "future-type"}}}).encode()
        )
        result = decide("s", [{"name": "q1", "type": "predicate", "instructions": "x?"}], api_key="k1")
        assert result["q1"]["band"] == "escalate"

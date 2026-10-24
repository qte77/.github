"""CLI contract: JSON in on stdin, JSON out on stdout."""

import io
import json
from unittest.mock import patch

import pytest
from conftest import fake_response
from decide import main


class TestCliSuccess:
    @patch("decide.urllib.request.urlopen")
    def test_valid_input_prints_decide_result(self, mock_urlopen, monkeypatch, capsys):
        mock_urlopen.return_value = fake_response(
            json.dumps({"model": "jev-1.13.0", "answers": {"q1": {"type": "noul", "noul": 0.9}}}).encode()
        )
        payload = {
            "state": "s",
            "questions": [{"name": "q1", "type": "predicate", "instructions": "x?"}],
            "api_key": "k1",
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        exit_code = main()
        assert exit_code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["q1"]["band"] == "act"
        assert out["q1"]["probability"] == 0.9

    @patch("decide.urllib.request.urlopen")
    def test_null_optional_fields_fall_back_to_defaults(self, mock_urlopen, monkeypatch, capsys):
        mock_urlopen.return_value = fake_response(
            json.dumps({"model": "jev-1.13.0", "answers": {"q1": {"type": "noul", "noul": 0.9}}}).encode()
        )
        payload = {
            "state": "s",
            "questions": [{"name": "q1", "type": "predicate", "instructions": "x?"}],
            "api_key": "k1",
            "hi": None,
            "model": None,
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        assert main() == 0
        out = json.loads(capsys.readouterr().out)
        assert out["q1"]["band"] == "act"


class TestCliErrors:
    def test_invalid_json_on_stdin_exits_2(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
        assert main() == 2
        err = json.loads(capsys.readouterr().err)
        assert "error" in err

    def test_non_object_json_on_stdin_exits_2(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO("[1, 2]"))
        assert main() == 2

    @pytest.mark.parametrize("payload", [{"questions": []}, {"state": "s"}])
    def test_missing_required_field_exits_2(self, payload, monkeypatch, capsys):
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        assert main() == 2
        err = json.loads(capsys.readouterr().err)
        assert "error" in err

    def test_unknown_backend_exits_2(self, monkeypatch, capsys):
        payload = {
            "state": "s",
            "questions": [{"name": "q1", "type": "predicate", "instructions": "x?"}],
            "backend": "openai",
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
        assert main() == 2
        err = json.loads(capsys.readouterr().err)
        assert "openai" in err["error"]

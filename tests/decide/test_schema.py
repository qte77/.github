"""Question-shape validation: building the wire-format payload for Jev, and the
call-level validation (name required/unique, backend must be known).

These exercise `_jev_question_payload` and `decide()`'s own input checks
directly, without any network mocking.
"""

import pytest
from decide import DecideError, _jev_question_payload, _QuestionShapeError, decide


class TestJevQuestionPayload:
    def test_predicate_maps_to_noul(self):
        payload = _jev_question_payload({"name": "q", "type": "predicate", "instructions": "Is it safe?"})
        assert payload == {"type": "noul", "instructions": "Is it safe?"}

    def test_choice_with_list_of_labels(self):
        payload = _jev_question_payload(
            {"name": "q", "type": "choice", "instructions": "Pick one", "choices": ["a", "b"]}
        )
        assert payload["type"] == "choice"
        assert payload["criteria"] == {"a": None, "b": None}

    def test_choice_with_described_criteria_passes_through(self):
        criteria = {"a": "the first option", "b": "the second option"}
        payload = _jev_question_payload(
            {"name": "q", "type": "choice", "instructions": "Pick one", "choices": criteria}
        )
        assert payload["criteria"] == criteria

    def test_score_with_ordered_levels(self):
        payload = _jev_question_payload(
            {"name": "q", "type": "score", "instructions": "Rate it", "levels": ["bad", "ok", "good"]}
        )
        assert payload["type"] == "score"
        assert payload["criteria"] == ["bad", "ok", "good"]

    def test_unknown_type_raises_shape_error(self):
        with pytest.raises(_QuestionShapeError):
            _jev_question_payload({"name": "q", "type": "essay", "instructions": "Write one"})

    def test_missing_instructions_raises_shape_error(self):
        with pytest.raises(_QuestionShapeError):
            _jev_question_payload({"name": "q", "type": "predicate"})

    def test_choice_without_choices_raises_shape_error(self):
        with pytest.raises(_QuestionShapeError):
            _jev_question_payload({"name": "q", "type": "choice", "instructions": "Pick one"})

    def test_score_without_levels_raises_shape_error(self):
        with pytest.raises(_QuestionShapeError):
            _jev_question_payload({"name": "q", "type": "score", "instructions": "Rate it"})


class TestDecideCallValidation:
    def test_unknown_backend_raises_decide_error(self):
        with pytest.raises(DecideError):
            decide("state", [{"name": "q", "type": "predicate", "instructions": "x?"}], backend="openai")

    def test_question_without_name_raises_decide_error(self):
        with pytest.raises(DecideError):
            decide("state", [{"type": "predicate", "instructions": "x?"}])

    def test_duplicate_question_names_raise_decide_error(self):
        questions = [
            {"name": "q", "type": "predicate", "instructions": "x?"},
            {"name": "q", "type": "predicate", "instructions": "y?"},
        ]
        with pytest.raises(DecideError):
            decide("state", questions)

    def test_one_malformed_question_does_not_block_the_others(self):
        # A single bad question (handled in _decide_jev via _QuestionShapeError)
        # escalates on its own; it must not raise or block sibling questions.
        questions = [
            {"name": "bad", "type": "choice", "instructions": "Pick"},  # missing choices
            {"name": "good", "type": "predicate", "instructions": "Is this fine?"},
        ]
        result = decide("state", questions, backend="jev", api_key="")
        assert result["bad"]["band"] == "escalate"
        assert "choices" in result["bad"]["error"]
        assert result["good"]["band"] == "escalate"  # no key either, but reached its own check
        assert "TYPESAFE_API_KEY" in result["good"]["error"]

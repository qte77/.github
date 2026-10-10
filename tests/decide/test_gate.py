"""Unit tests for the act/review/escalate banding logic.

`_band` is the one piece of pure math in `decide.py`: given a 0-1 value and a `hi`
threshold, it returns a band. It has two modes:

- symmetric=True (predicate/noul): a value near 0 is just as decisive as a value
  near 1 ("confidently false" is as actionable as "confidently true"), so both
  tails act.
- symmetric=False (choice/score): the value is TypeSafe's `confidence` statistic
  (concentration of the probability distribution, 0 = spread evenly, 1 = all mass
  on one outcome), which only has one decisive tail. A low confidence means
  "unsure," not "confidently something else" — so only the high tail acts.
"""

from decide import _band


class TestBandSymmetric:
    """Predicate/noul questions: both tails of the probability act."""

    def test_high_probability_acts(self):
        assert _band(0.9, hi=0.85, symmetric=True) == "act"

    def test_probability_at_hi_boundary_acts(self):
        assert _band(0.85, hi=0.85, symmetric=True) == "act"

    def test_low_probability_acts(self):
        assert _band(0.1, hi=0.85, symmetric=True) == "act"

    def test_probability_at_low_boundary_acts(self):
        assert _band(0.15, hi=0.85, symmetric=True) == "act"

    def test_middle_probability_reviews(self):
        assert _band(0.5, hi=0.85, symmetric=True) == "review"

    def test_just_inside_low_boundary_reviews(self):
        assert _band(0.151, hi=0.85, symmetric=True) == "review"

    def test_just_inside_high_boundary_reviews(self):
        assert _band(0.849, hi=0.85, symmetric=True) == "review"


class TestBandAsymmetric:
    """Choice/score questions: only the high tail of confidence acts."""

    def test_high_confidence_acts(self):
        assert _band(0.9, hi=0.85, symmetric=False) == "act"

    def test_confidence_at_hi_boundary_acts(self):
        assert _band(0.85, hi=0.85, symmetric=False) == "act"

    def test_low_confidence_reviews_not_acts(self):
        # Would be "act" under the symmetric rule (0.1 <= 1 - 0.85); must NOT be
        # here, since low confidence means "the model is unsure," not "confidently
        # the opposite" — there is no opposite for an argmax over N options.
        assert _band(0.1, hi=0.85, symmetric=False) == "review"

    def test_zero_confidence_reviews(self):
        assert _band(0.0, hi=0.85, symmetric=False) == "review"

    def test_middle_confidence_reviews(self):
        assert _band(0.5, hi=0.85, symmetric=False) == "review"


class TestBandMissingValue:
    """A missing value (error, timeout, refusal, None probability) always escalates."""

    def test_none_escalates_symmetric(self):
        assert _band(None, hi=0.85, symmetric=True) == "escalate"

    def test_none_escalates_asymmetric(self):
        assert _band(None, hi=0.85, symmetric=False) == "escalate"

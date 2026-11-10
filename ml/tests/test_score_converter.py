"""Tests for ml.scoring.converter — score conversion and interpretation."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ml.scoring.converter import (
    SCORE_BANDS,
    SCORE_MAX,
    SCORE_MIN,
    RiskCategory,
    ScoreResult,
    convert_batch,
    convert_score,
    get_risk_category,
    probability_to_score,
    score_to_probability,
)


# ---------------------------------------------------------------------------
# Test probability_to_score
# ---------------------------------------------------------------------------

class TestProbabilityToScore:
    def test_zero_probability_gives_max_score(self) -> None:
        assert probability_to_score(0.0) == 900

    def test_one_probability_gives_min_score(self) -> None:
        assert probability_to_score(1.0) == 300

    def test_half_probability_gives_midpoint(self) -> None:
        assert probability_to_score(0.5) == 600

    def test_formula_correctness(self) -> None:
        # score = 300 + (1 - p) * 600
        assert probability_to_score(0.25) == 750
        assert probability_to_score(0.75) == 450

    def test_result_is_integer(self) -> None:
        score = probability_to_score(0.333)
        assert isinstance(score, int)

    def test_rounding(self) -> None:
        # 300 + (1 - 0.123) * 600 = 300 + 0.877 * 600 = 300 + 526.2 = 826
        assert probability_to_score(0.123) == 826

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="must be in"):
            probability_to_score(-0.1)
        with pytest.raises(ValueError, match="must be in"):
            probability_to_score(1.1)

    def test_nan_returns_min_score(self) -> None:
        assert probability_to_score(float("nan")) == 300

    def test_boundary_values(self) -> None:
        assert SCORE_MIN <= probability_to_score(0.0) <= SCORE_MAX
        assert SCORE_MIN <= probability_to_score(1.0) <= SCORE_MAX
        assert SCORE_MIN <= probability_to_score(0.5) <= SCORE_MAX

    def test_monotonic_decreasing(self) -> None:
        probs = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        scores = [probability_to_score(p) for p in probs]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]


# ---------------------------------------------------------------------------
# Test score_to_probability
# ---------------------------------------------------------------------------

class TestScoreToProbability:
    def test_max_score_gives_zero_probability(self) -> None:
        assert score_to_probability(900) == pytest.approx(0.0)

    def test_min_score_gives_one_probability(self) -> None:
        assert score_to_probability(300) == pytest.approx(1.0)

    def test_midpoint(self) -> None:
        assert score_to_probability(600) == pytest.approx(0.5)

    def test_inverse_of_probability_to_score(self) -> None:
        for p in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
            score = probability_to_score(p)
            recovered_p = score_to_probability(score)
            assert abs(recovered_p - p) < 0.01  # Allow for rounding

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="must be in"):
            score_to_probability(299)
        with pytest.raises(ValueError, match="must be in"):
            score_to_probability(901)


# ---------------------------------------------------------------------------
# Test get_risk_category
# ---------------------------------------------------------------------------

class TestGetRiskCategory:
    def test_very_low_risk(self) -> None:
        assert get_risk_category(800) == "Very Low Risk"
        assert get_risk_category(850) == "Very Low Risk"
        assert get_risk_category(900) == "Very Low Risk"

    def test_low_risk(self) -> None:
        assert get_risk_category(700) == "Low Risk"
        assert get_risk_category(750) == "Low Risk"
        assert get_risk_category(799) == "Low Risk"

    def test_medium_risk(self) -> None:
        assert get_risk_category(600) == "Medium Risk"
        assert get_risk_category(650) == "Medium Risk"
        assert get_risk_category(699) == "Medium Risk"

    def test_high_risk(self) -> None:
        assert get_risk_category(500) == "High Risk"
        assert get_risk_category(550) == "High Risk"
        assert get_risk_category(599) == "High Risk"

    def test_very_high_risk(self) -> None:
        assert get_risk_category(300) == "Very High Risk"
        assert get_risk_category(400) == "Very High Risk"
        assert get_risk_category(499) == "Very High Risk"

    def test_all_bands_covered(self) -> None:
        """Every score from 300 to 900 should map to a category."""
        for score in range(300, 901):
            category = get_risk_category(score)
            assert category in {c.value for c in RiskCategory}

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            get_risk_category(299)
        with pytest.raises(ValueError):
            get_risk_category(901)


# ---------------------------------------------------------------------------
# Test convert_score
# ---------------------------------------------------------------------------

class TestConvertScore:
    def test_basic_conversion(self) -> None:
        result = convert_score(0.2)
        assert isinstance(result, ScoreResult)
        assert result.score == 780
        assert result.probability == 0.2
        assert result.risk_category == "Low Risk"

    def test_no_confidence_by_default(self) -> None:
        result = convert_score(0.5)
        assert result.confidence_interval is None

    def test_with_confidence(self) -> None:
        result = convert_score(0.5, include_confidence=True)
        assert result.confidence_interval is not None
        lower, upper = result.confidence_interval
        assert lower <= result.score <= upper
        assert SCORE_MIN <= lower
        assert upper <= SCORE_MAX

    def test_to_dict(self) -> None:
        result = convert_score(0.3)
        d = result.to_dict()
        assert "score" in d
        assert "probability" in d
        assert "risk_category" in d

    def test_to_dict_with_confidence(self) -> None:
        result = convert_score(0.3, include_confidence=True)
        d = result.to_dict()
        assert "confidence_interval" in d
        assert "lower" in d["confidence_interval"]
        assert "upper" in d["confidence_interval"]

    def test_extreme_probabilities(self) -> None:
        low_risk = convert_score(0.01)
        high_risk = convert_score(0.99)
        assert low_risk.score > high_risk.score
        assert low_risk.risk_category == "Very Low Risk"
        assert high_risk.risk_category == "Very High Risk"


# ---------------------------------------------------------------------------
# Test convert_batch
# ---------------------------------------------------------------------------

class TestConvertBatch:
    def test_batch_conversion(self) -> None:
        probs = [0.1, 0.3, 0.5, 0.7, 0.9]
        results = convert_batch(probs)
        assert len(results) == 5
        for result in results:
            assert isinstance(result, ScoreResult)

    def test_batch_monotonic(self) -> None:
        probs = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        results = convert_batch(probs)
        scores = [r.score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_empty_batch(self) -> None:
        results = convert_batch([])
        assert results == []

    def test_numpy_array_input(self) -> None:
        probs = np.array([0.2, 0.5, 0.8])
        results = convert_batch(probs)
        assert len(results) == 3

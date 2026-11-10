"""Tests for custom scoring endpoint (Phase 11.1)."""

from __future__ import annotations

import pytest

from app.api.v1.scores import CustomScoreRequest, CustomScoreResponse


class TestCustomScoreRequest:
    """Tests for CustomScoreRequest schema."""

    def test_default_values(self) -> None:
        req = CustomScoreRequest(national_id="12345678")
        assert req.industry_vertical == "general"
        assert req.prediction_horizon == 365
        assert req.feature_selection is None

    def test_custom_values(self) -> None:
        req = CustomScoreRequest(
            national_id="12345678",
            industry_vertical="retail",
            prediction_horizon=30,
            feature_selection=["cblri", "utdi"],
        )
        assert req.industry_vertical == "retail"
        assert req.prediction_horizon == 30
        assert len(req.feature_selection) == 2

    def test_national_id_min_length(self) -> None:
        with pytest.raises(Exception):
            CustomScoreRequest(national_id="1234")  # Too short

    def test_national_id_max_length(self) -> None:
        with pytest.raises(Exception):
            CustomScoreRequest(national_id="a" * 21)  # Too long


class TestCustomScoreResponse:
    """Tests for CustomScoreResponse schema."""

    def test_valid_response(self) -> None:
        resp = CustomScoreResponse(
            vyce_score=650,
            niq_score=72,
            risk_drivers=[],
            industry_vertical="retail",
            prediction_horizon="12_months",
            model_version="xgb_2026_01_v1",
            model_selection_reason="General model used.",
            confidence_interval={"lower": 620, "upper": 680},
            score_date="2026-03-08",
            data_quality="high",
        )
        assert resp.vyce_score == 650
        assert resp.industry_vertical == "retail"

    def test_score_range_validation(self) -> None:
        with pytest.raises(Exception):
            CustomScoreResponse(
                vyce_score=200,  # Below 300
                niq_score=72,
                industry_vertical="general",
                prediction_horizon="12_months",
                model_version="v1",
                model_selection_reason="test",
                confidence_interval={},
                score_date="2026-03-08",
                data_quality="high",
            )

"""Score interpretation helper (BRD §4.3).

Maps VyceScore ranges to human-readable risk levels and creditworthiness
descriptions for Kenya DPA 2019 compliance.
"""

from __future__ import annotations

from app.schemas.scores import ScoreInterpretation


def interpret_score(vyce_score: int) -> ScoreInterpretation:
    """Return risk level and interpretation for a given VyceScore.

    Score ranges (BRD §4.3):
        800-900: Very Low Risk  / Excellent creditworthiness
        700-799: Low Risk       / Good creditworthiness
        600-699: Medium Risk    / Fair creditworthiness
        500-599: High Risk      / Poor creditworthiness
        300-499: Very High Risk / Very poor creditworthiness

    Raises:
        ValueError: If the score is outside the valid 300-900 range.
    """
    if vyce_score < 300 or vyce_score > 900:
        raise ValueError(f"VyceScore must be between 300 and 900, got {vyce_score}")

    if vyce_score >= 800:
        return ScoreInterpretation(
            risk_level="Very Low Risk",
            interpretation="Excellent creditworthiness",
        )
    if vyce_score >= 700:
        return ScoreInterpretation(
            risk_level="Low Risk",
            interpretation="Good creditworthiness",
        )
    if vyce_score >= 600:
        return ScoreInterpretation(
            risk_level="Medium Risk",
            interpretation="Fair creditworthiness",
        )
    if vyce_score >= 500:
        return ScoreInterpretation(
            risk_level="High Risk",
            interpretation="Poor creditworthiness",
        )
    return ScoreInterpretation(
        risk_level="Very High Risk",
        interpretation="Very poor creditworthiness",
    )

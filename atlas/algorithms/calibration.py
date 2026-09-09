"""
Cultural Calibration & Epistemic Prediction Engine for PLOT.
Evaluates human forecasts of global opinion splits using multi-category Brier scores.
Computes the Cultural Calibration Index (CCI: 0–1,000), rank tiers, and cultural blindspots.
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional


@dataclass
class CalibrationResult:
    brier_score: float
    calibration_index: int
    rank_tier: str
    rank_description: str
    percentile: int
    blindspot_choice: str
    blindspot_delta: float
    blindspot_message: str
    ground_truth: Dict[str, float]
    predictions: Dict[str, float]


class CulturalCalibrationScorer:
    """
    Evaluates epistemic accuracy of crowdsourced predictions against live empirical ground truth.
    Uses strictly proper multi-category Brier scores mapped to a 0–1,000 index.
    """

    CHOICES = ("A", "B", "C", "D")

    def __init__(self, baseline_prior: float = 0.25):
        self.baseline_prior = baseline_prior

    def compute_brier_score(
        self, predictions: Dict[str, float], ground_truth: Dict[str, float]
    ) -> float:
        """
        Compute multi-category Brier score: BS = (1/K) * sum((f_k - o_k)^2)
        BS in [0.0, 1.0]. 0.0 is perfect prediction.
        """
        k = len(self.CHOICES)
        sq_errors = []
        for choice in self.CHOICES:
            f_k = float(predictions.get(choice, 0.0))
            o_k = float(ground_truth.get(choice, 0.0))
            sq_errors.append((f_k - o_k) ** 2)
        return float(sum(sq_errors) / k)

    def compute_calibration_index(
        self, brier_score: float, ground_truth: Dict[str, float]
    ) -> int:
        """
        Map Brier score into a calibrated index from 0 to 1,000.
        A perfect forecast (BS = 0) receives 1,000.
        A uniform random forecast (all 0.25) receives approximately 600.
        An inverted/severe error forecast receives <= 200.
        """
        if brier_score <= 1e-6:
            return 1000

        k = len(self.CHOICES)
        uniform_bs = sum((0.25 - float(ground_truth.get(c, 0.25))) ** 2 for c in self.CHOICES) / k

        # Theoretical worst possible Brier score for this ground truth distribution
        worst_bs = max(
            sum(((1.0 if c == worst_c else 0.0) - float(ground_truth.get(c, 0.0))) ** 2 for c in self.CHOICES) / k
            for worst_c in self.CHOICES
        )
        worst_bs = max(0.20, worst_bs)

        if uniform_bs < 0.005:
            # If ground truth itself is roughly uniform, scale directly against worst_bs
            cci = 1000.0 * (1.0 - (brier_score / worst_bs))
        elif brier_score <= uniform_bs:
            # Scale from 1,000 down to 600
            ratio = brier_score / uniform_bs
            cci = 1000.0 - (400.0 * ratio)
        else:
            # Scale from 600 down to 0: extreme/inverted errors drop rapidly below 200
            effective_worst = min(worst_bs, max(0.24, uniform_bs + 0.15))
            excess = min(1.0, (brier_score - uniform_bs) / max(0.01, effective_worst - uniform_bs))
            cci = max(0.0, 600.0 * (1.0 - excess))

        return int(round(min(1000.0, max(0.0, cci))))

    def diagnose_blindspot(
        self, predictions: Dict[str, float], ground_truth: Dict[str, float]
    ) -> Tuple[str, float, str]:
        """
        Identify the choice with the largest forecasting discrepancy.
        Returns (choice_letter, delta, narrative_message).
        """
        discrepancies = []
        for choice in self.CHOICES:
            f_k = float(predictions.get(choice, 0.0))
            o_k = float(ground_truth.get(choice, 0.0))
            delta = f_k - o_k  # Positive = overestimated, Negative = underestimated
            discrepancies.append((choice, delta, abs(delta)))

        # Find largest discrepancy
        top_choice, top_delta, abs_delta = max(discrepancies, key=lambda x: x[2])
        pct_diff = round(abs_delta * 100)

        if top_delta < -0.05:
            message = f"You underestimated global resonance for Option {top_choice} by {pct_diff}%."
        elif top_delta > 0.05:
            message = f"You overestimated global resonance for Option {top_choice} by {pct_diff}%."
        else:
            message = "Remarkably balanced perspective across all options."

        return top_choice, round(top_delta, 3), message

    def assign_rank_tier(self, cci: int) -> Tuple[str, str, int]:
        """Map CCI (0–1,000) to cultural archetype rank tier, narrative, and percentile."""
        if cci >= 900:
            return (
                "EMPATHIC DIPLOMAT",
                "Exceptional global perception. You read human cultural currents with razor precision.",
                96,
            )
        elif cci >= 750:
            return (
                "CULTURAL ANTHROPOLOGIST",
                "High cultural calibration. You easily look past your immediate regional bubble.",
                82,
            )
        elif cci >= 600:
            return (
                "CURIOUS OBSERVER",
                "Solid empirical intuition. Broadly aligned with global realities with minor blindspots.",
                58,
            )
        elif cci >= 400:
            return (
                "LOCAL REALIST",
                "Moderate projection bias. Your forecast reflected your home region more than the world.",
                35,
            )
        else:
            return (
                "ECHO-CHAMBER NATIVE",
                "Significant cultural divergence. Global sentiment surprised your expectations.",
                14,
            )

    def evaluate(
        self, predictions: Dict[str, float], ground_truth: Dict[str, float]
    ) -> CalibrationResult:
        """Evaluate a user's prediction vector against empirical ground truth."""
        bs = self.compute_brier_score(predictions, ground_truth)
        cci = self.compute_calibration_index(bs, ground_truth)
        blind_choice, blind_delta, blind_msg = self.diagnose_blindspot(predictions, ground_truth)
        tier_title, tier_desc, percentile = self.assign_rank_tier(cci)

        return CalibrationResult(
            brier_score=round(bs, 4),
            calibration_index=cci,
            rank_tier=tier_title,
            rank_description=tier_desc,
            percentile=percentile,
            blindspot_choice=blind_choice,
            blindspot_delta=blind_delta,
            blindspot_message=blind_msg,
            ground_truth=ground_truth,
            predictions=predictions,
        )

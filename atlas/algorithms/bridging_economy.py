"""
Bridging Economy & Epistemic Reputation Engine for PLOT: The Cultural Atlas.
Implements strategy-proof bridging yield, anti-farming reputation aggregation,
epistemic peer prediction, and hybrid reputation tiers.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any

Z_95_ONESIDED: float = 1.644853


@dataclass(frozen=True)
class PerspectiveRatingInput:
    rater_salt: str
    rater_cohort: str          # e.g., "GEN_Z", "BOOMER_PLUS"
    rater_stance: str          # 'A', 'B', 'C', 'D', or 'UNSPECIFIED'
    rating_category: str       # 'HELPFUL_BRIDGE', 'INFORMATIVE', 'ECHO_ONLY', 'UNHELPFUL'


@dataclass(frozen=True)
class BridgingYieldResult:
    perspective_id: str
    bc_yield: float            # Bridging Capital Yield [0.0, 100.0]
    conservative_bridge: float
    polarization_delta: float
    effective_sample_size: float
    has_quorum: bool
    is_sacred_bridge: bool


@dataclass(frozen=True)
class AuthorReputationResult:
    author_salt: str
    active_abs: float          # Active Author Bridging Score
    lifetime_peak_abs: float
    bridging_b_index: int      # Hirsch-style bridging index
    echo_contamination_pct: float
    reputation_tier: str       # 'CITIZEN_DELIBERATOR', 'CONSENSUS_BUILDER', 'CULTURAL_DIPLOMAT', 'SACRED_ARBITER'
    tier_insignia: str


# -----------------------------------------------------------------------------
# 1. Perspective Bridging Capital Yield Engine
# -----------------------------------------------------------------------------

def calculate_weighted_wilson_lower(
    ratings: List[PerspectiveRatingInput],
    perspective_stance: str,
    z: float = Z_95_ONESIDED,
) -> Tuple[float, float]:
    """
    Computes stance-weighted bridging utility and effective sample size.
    Neutralizes agreement bias by rewarding cross-stance endorsements.
    Returns (wilson_lower_bound, effective_sample_size).
    """
    if not ratings:
        return 0.0, 0.0

    category_utilities = {
        "HELPFUL_BRIDGE": 1.00,
        "INFORMATIVE": 0.20,
        "ECHO_ONLY": 0.00,
        "UNHELPFUL": 0.00,
    }

    weighted_successes = 0.0
    sum_weights = 0.0
    sum_sq_weights = 0.0

    for r in ratings:
        u = category_utilities.get(r.rating_category, 0.0)
        # Weighting: cross-stance endorsement gets 1.60x, in-group gets 0.65x
        if r.rater_stance == "UNSPECIFIED" or perspective_stance == "UNSPECIFIED":
            w = 1.00
        elif r.rater_stance != perspective_stance:
            w = 1.60
        else:
            w = 0.65

        weighted_successes += w * u
        sum_weights += w
        sum_sq_weights += w * w

    if sum_weights <= 0.0:
        return 0.0, 0.0

    p_hat = weighted_successes / sum_weights
    n_eff = (sum_weights * sum_weights) / sum_sq_weights

    # Wilson lower bound on continuous bounded utility
    z2 = z * z
    denominator = 1.0 + (z2 / n_eff)
    center = p_hat + (z2 / (2.0 * n_eff))
    spread = z * math.sqrt(max(0.0, (p_hat * (1.0 - p_hat) / n_eff) + (z2 / (4.0 * n_eff * n_eff))))
    lower = (center - spread) / denominator

    return round(max(0.0, min(1.0, lower)), 4), round(n_eff, 2)


def calculate_perspective_bridging_capital(
    perspective_id: str,
    perspective_stance: str,
    ratings_cohort_a: List[PerspectiveRatingInput],
    ratings_cohort_b: List[PerspectiveRatingInput],
    min_quorum: int = 5,
    k_vol_half: float = 25.0,
    tau_polar: float = 0.35,
) -> BridgingYieldResult:
    """
    Evaluates Strategy-Proof Bridging Capital Yield (BC_p).
    Implements Epistemic Quorum, Harmonic Effective Sample Size,
    Quadratic Polarization Damping, and Saturating Yield Curve.
    """
    n_a_raw = len(ratings_cohort_a)
    n_b_raw = len(ratings_cohort_b)
    has_quorum = (n_a_raw >= min_quorum) and (n_b_raw >= min_quorum)

    if not has_quorum:
        return BridgingYieldResult(
            perspective_id=perspective_id,
            bc_yield=0.0,
            conservative_bridge=0.0,
            polarization_delta=0.0,
            effective_sample_size=0.0,
            has_quorum=False,
            is_sacred_bridge=False,
        )

    w_lower_a, n_eff_a = calculate_weighted_wilson_lower(ratings_cohort_a, perspective_stance)
    w_lower_b, n_eff_b = calculate_weighted_wilson_lower(ratings_cohort_b, perspective_stance)

    # 1. Harmonic Conservative Bridge Score
    if (w_lower_a + w_lower_b) > 0.0:
        b_conservative = 2.0 * (w_lower_a * w_lower_b) / (w_lower_a + w_lower_b)
    else:
        b_conservative = 0.0

    # 2. Polarization Delta
    delta = abs(w_lower_a - w_lower_b)

    # 3. Polarization Damper (Quadratic drop to zero at tau_polar)
    if delta >= tau_polar:
        polar_damper = 0.0
    else:
        polar_damper = max(0.0, 1.0 - ((delta / tau_polar) ** 2))

    # 4. Dyadic Harmonic Effective Sample Size
    n_eff_harmonic = (2.0 * n_eff_a * n_eff_b) / max(1.0, (n_eff_a + n_eff_b))

    # 5. Saturating Yield Curve S(n_eff)
    s_curve = n_eff_harmonic / (n_eff_harmonic + k_vol_half)

    # 6. Final Yield
    bc_yield = round(100.0 * b_conservative * polar_damper * s_curve, 2)
    is_sacred = (b_conservative >= 0.48) and (delta <= 0.20) and (bc_yield >= 35.0)

    return BridgingYieldResult(
        perspective_id=perspective_id,
        bc_yield=bc_yield,
        conservative_bridge=round(b_conservative, 4),
        polarization_delta=round(delta, 4),
        effective_sample_size=round(n_eff_harmonic, 2),
        has_quorum=True,
        is_sacred_bridge=is_sacred,
    )


# -----------------------------------------------------------------------------
# 2. Author Bridging Score ($ABS$) & Reputation Engine
# -----------------------------------------------------------------------------

def calculate_author_bridging_score(
    authored_perspectives: List[Dict[str, Any]],  # [{"bc_yield": float, "is_echo": bool, "age_days": float}]
    lifetime_peak_abs: float = 0.0,
    half_life_days: float = 60.0,
) -> AuthorReputationResult:
    """
    Computes Author Bridging Score ($ABS$) using Sub-Linear Discounted Cumulative Yield,
    Bridging b-Index, Proportional Echo Damping, and 60-day Temporal Half-Life.
    """
    if not authored_perspectives:
        return AuthorReputationResult(
            author_salt="",
            active_abs=0.0,
            lifetime_peak_abs=lifetime_peak_abs,
            bridging_b_index=0,
            echo_contamination_pct=0.0,
            reputation_tier="CITIZEN_DELIBERATOR",
            tier_insignia="Basalt Slate",
        )

    # Extract valid yields sorted descending
    yields = sorted([float(p.get("bc_yield", 0.0)) for p in authored_perspectives], reverse=True)

    # 1. Compute Bridging b-Index (b perspectives with BC >= 15 * b)
    b_index = 0
    for idx, y in enumerate(yields, start=1):
        if y >= (15.0 * idx):
            b_index = idx
        else:
            break

    # 2. Rank-Discounted Cumulative Sum with Temporal Decay
    discounted_sum = 0.0
    total_echo_count = 0

    for idx, p in enumerate(authored_perspectives):
        y = float(p.get("bc_yield", 0.0))
        age = float(p.get("age_days", 0.0))
        is_echo = bool(p.get("is_echo", False))

        if is_echo:
            total_echo_count += 1

        # Temporal Decay Weight
        decay_factor = 2.0 ** (-age / half_life_days)
        # Rank Discount (using sorted index)
        rank = idx + 1
        discounted_sum += (y / math.sqrt(rank)) * decay_factor

    abs_base = (20.0 * b_index) + discounted_sum

    # 3. Proportional Echo Damping Multiplier
    echo_ratio = total_echo_count / max(1, len(authored_perspectives))
    echo_multiplier = 1.0 / (1.0 + 1.5 * total_echo_count)

    # 4. Active ABS with 20% Lifetime Peak Guarantee
    active_abs = round((abs_base * echo_multiplier) + (0.20 * lifetime_peak_abs), 2)
    new_peak = max(lifetime_peak_abs, active_abs)

    # 5. Hybrid Tier Assignment
    if active_abs >= 750.0 and b_index >= 5 and echo_ratio <= 0.08:
        tier = "SACRED_ARBITER"
        insignia = "Gold Keystone"
    elif active_abs >= 300.0 and b_index >= 3 and echo_ratio <= 0.15:
        tier = "CULTURAL_DIPLOMAT"
        insignia = "Dual Rosette"
    elif active_abs >= 100.0 and b_index >= 1:
        tier = "CONSENSUS_BUILDER"
        insignia = "Plumb Line"
    else:
        tier = "CITIZEN_DELIBERATOR"
        insignia = "Basalt Slate"

    return AuthorReputationResult(
        author_salt="",
        active_abs=active_abs,
        lifetime_peak_abs=new_peak,
        bridging_b_index=b_index,
        echo_contamination_pct=round(echo_ratio * 100, 1),
        reputation_tier=tier,
        tier_insignia=insignia,
    )


# -----------------------------------------------------------------------------
# 3. Rater Calibration Karma ($RCK$) Engine
# -----------------------------------------------------------------------------

def calculate_rater_karma_delta(
    rating_category: str,
    rater_stance: str,
    perspective_stance: str,
    cohort_a_lower: float,
    cohort_b_lower: float,
    rater_cci: int = 500,  # Cultural Calibration Index from calibration.py (0 - 1000)
) -> float:
    """
    Computes Epistemic Rater Karma without Keynesian Beauty Contest traps.
    Rewards Cross-Cohort Concordance Discovery and Epistemic Humility.
    """
    # 1. Base participation credit (debounced)
    karma = 0.50

    # 2. Check if the perspective proved to be an actual cross-cohort bridge
    conservative_bridge = 0.0
    if (cohort_a_lower + cohort_b_lower) > 0.0:
        conservative_bridge = 2.0 * (cohort_a_lower * cohort_b_lower) / (cohort_a_lower + cohort_b_lower)
    delta = abs(cohort_a_lower - cohort_b_lower)
    is_verified_bridge = (conservative_bridge >= 0.48) and (delta <= 0.20)

    # 3. Cross-Cohort Concordance Bounty
    # Rater rewarded ONLY when their HELPFUL endorsement matches genuine cross-cohort bridging
    if rating_category == "HELPFUL_BRIDGE" and is_verified_bridge:
        concordance_bounty = 3.0 * conservative_bridge * max(0.0, 1.0 - (delta / 0.35))
        karma += concordance_bounty

        # Counter-Attitudinal Bonus: Endorsing a perspective outside one's own prior choice
        if rater_stance != "UNSPECIFIED" and perspective_stance != "UNSPECIFIED":
            if rater_stance != perspective_stance:
                karma += 2.00  # Epistemic Humility Dividend

    # 4. Calibration Multiplier from CulturalCalibrationScorer (0.60 to 1.00)
    calib_multiplier = 0.60 + 0.40 * (max(0, min(1000, rater_cci)) / 1000.0)
    return round(karma * calib_multiplier, 2)

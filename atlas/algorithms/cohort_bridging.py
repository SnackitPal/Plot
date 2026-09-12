"""
Cohort Bridging Analytics Engine for PLOT: The Cultural Atlas.
Evaluates inter-subjective demographic consensus across generations, urbanicities, and regions.
Uses Sample-Size Robust Harmonic Bridging (Wilson Score Lower Bound + Epistemic Quorum Gate).
"""

import math
from typing import Dict, List, Any, Optional

# Standard Normal Quantile for 95% One-Sided Confidence (90% Two-Sided)
Z_95_ONESIDED: float = 1.644853


def calculate_wilson_lower_bound(
    helpful: int,
    total: int,
    z: float = Z_95_ONESIDED,
) -> float:
    """
    Computes the conservative Wilson Score Interval Lower Bound W^-(h, n, z).
    Closed-form solution using only standard math module.
    Returns 0.0 if total <= 0.
    """
    if total <= 0:
        return 0.0
    
    n = float(total)
    h = float(max(0, min(helpful, total)))
    p_hat = h / n
    z2 = z * z
    
    # Wilson interval lower bound equation
    denominator = 1.0 + (z2 / n)
    center = p_hat + (z2 / (2.0 * n))
    spread = z * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * n * n)))
    
    lower_bound = (center - spread) / denominator
    return round(max(0.0, min(1.0, lower_bound)), 4)


def calculate_cohort_helpfulness(
    ratings_by_cohort: Dict[str, Dict[str, Any]],
    laplace_prior: float = 0.5,
    laplace_weight: float = 1.0,
    z: float = Z_95_ONESIDED,
) -> Dict[str, Dict[str, Any]]:
    """
    Computes sample size, raw approval rate, Laplace-smoothed rate, and Wilson lower bound per cohort.
    """
    results: Dict[str, Dict[str, Any]] = {}
    for cohort, stats in ratings_by_cohort.items():
        total = int(stats.get("total_ratings", 0))
        helpful = int(stats.get("helpful_ratings", 0))
        
        if total <= 0:
            raw_rate = 0.5
            smoothed_rate = 0.5
            wilson_lower = 0.0
        else:
            raw_rate = helpful / total
            smoothed_rate = (helpful + laplace_prior * laplace_weight) / (total + laplace_weight)
            wilson_lower = calculate_wilson_lower_bound(helpful, total, z=z)
            
        results[cohort] = {
            "total": total,
            "helpful": helpful,
            "raw_rate": round(raw_rate, 3),
            "approval_rate": round(smoothed_rate, 3),
            "approval_pct": int(round(smoothed_rate * 100)),
            "wilson_lower": wilson_lower,
            "margin_of_error": round(max(0.0, smoothed_rate - wilson_lower), 3),
        }
    return results


def calculate_harmonic_bridge_score(r_a: float, r_b: float) -> float:
    """
    Computes the Harmonic Mean between two approval rates:
        B_{AB} = 2 * (r_a * r_b) / (r_a + r_b)
        
    Enforces that high bridge scores require strong mutual endorsement from BOTH cohorts.
    """
    if r_a <= 0.0 or r_b <= 0.0:
        return 0.0
    return round(2.0 * (r_a * r_b) / (r_a + r_b), 3)


def classify_bridging_status(
    cohort_a_rate: float,
    cohort_b_rate: float,
    sample_a: int = 1,
    sample_b: int = 1,
    wilson_a: Optional[float] = None,
    wilson_b: Optional[float] = None,
    min_sample: int = 5,
    axis: str = "generation",
) -> Dict[str, Any]:
    """
    Classifies the bridging status of a perspective across two cohorts (A and B).
    Uses the Hybrid Dual-Gate Architecture:
      Gate 1: Epistemic Quorum Gate (min_sample >= 5)
      Gate 2: Conservative Wilson Lower Credible Bound Consensus
      Gate 3: Polarization & Demographic Echo Analysis
    """
    delta = round(abs(cohort_a_rate - cohort_b_rate), 3)
    bridge_score = calculate_harmonic_bridge_score(cohort_a_rate, cohort_b_rate)
    
    # Compute Wilson lower bounds if not provided
    if wilson_a is None:
        wilson_a = calculate_wilson_lower_bound(int(round(cohort_a_rate * sample_a)), sample_a)
    if wilson_b is None:
        wilson_b = calculate_wilson_lower_bound(int(round(cohort_b_rate * sample_b)), sample_b)
        
    conservative_bridge = calculate_harmonic_bridge_score(wilson_a, wilson_b)
    has_quorum = (sample_a >= min_sample) and (sample_b >= min_sample)
    
    # Gate 1: Epistemic Quorum Check
    if not has_quorum:
        return {
            "status": "INSUFFICIENT_DATA",
            "bridge_score": bridge_score,
            "conservative_bridge_score": conservative_bridge,
            "polarization_delta": delta,
            "badge": "🌱 Needs More Ratings",
            "summary": f"Awaiting quorum ({sample_a}/{min_sample} vs {sample_b}/{min_sample})",
            "color": "#888888",
            "is_sacred_bridge": False,
            "has_quorum": False,
        }
        
    # Gate 2: Sacred Bridge Validation (Conservative Credible Bound Consensus)
    is_statistically_sound = (
        cohort_a_rate >= 0.65
        and cohort_b_rate >= 0.65
        and delta <= 0.20
        and bridge_score >= 0.70
        and wilson_a >= 0.45
        and wilson_b >= 0.45
        and conservative_bridge >= 0.48
    )
    
    if is_statistically_sound:
        return {
            "status": "SACRED_BRIDGE",
            "bridge_score": bridge_score,
            "conservative_bridge_score": conservative_bridge,
            "polarization_delta": delta,
            "badge": "🤝 Sacred Bridge",
            "summary": "Verified Cross-Cohort Consensus",
            "color": "#FFD700",
            "is_sacred_bridge": True,
            "has_quorum": True,
        }
        
    # Gate 3: Demographic Polarization / Echo Chambers
    if delta >= 0.35:
        if (cohort_a_rate >= 0.70 and cohort_b_rate < 0.45) or (cohort_b_rate >= 0.70 and cohort_a_rate < 0.45):
            return {
                "status": "INTRA_GROUP_ECHO",
                "bridge_score": bridge_score,
                "conservative_bridge_score": conservative_bridge,
                "polarization_delta": delta,
                "badge": "📢 Echo Chamber",
                "summary": "Appeals only to one cohort",
                "color": "#FF4500",
                "is_sacred_bridge": False,
                "has_quorum": True,
            }
        
        chasm_status = "GENERATIONAL_CHASM" if axis == "generation" else "DEMOGRAPHIC_CHASM"
        return {
            "status": chasm_status,
            "bridge_score": bridge_score,
            "conservative_bridge_score": conservative_bridge,
            "polarization_delta": delta,
            "badge": "⚡ Chasm",
            "summary": "Deep cross-cohort split",
            "color": "#FF6B6B",
            "is_sacred_bridge": False,
            "has_quorum": True,
        }
        
    # Default: Unaligned / Moderate Deliberation
    return {
        "status": "UNALIGNED",
        "bridge_score": bridge_score,
        "conservative_bridge_score": conservative_bridge,
        "polarization_delta": delta,
        "badge": "⚖️ Moderate",
        "summary": "Balanced distributed opinion",
        "color": "#4A90E2",
        "is_sacred_bridge": False,
        "has_quorum": True,
    }


def rank_bridging_perspectives(
    perspectives: List[Dict[str, Any]],
    cohort_ratings_map: Dict[str, Dict[str, Dict[str, Any]]],
    cohort_axis: str = "generation",
    cohort_a: str = "GEN_Z",
    cohort_b: str = "BOOMER_PLUS",
    min_sample: int = 5,
) -> List[Dict[str, Any]]:
    """
    Ranks perspectives prioritizing statistically verified SACRED_BRIDGE perspectives.
    Uses multi-tier Pareto sorting so unvoted perspectives never outrank evaluated perspectives.
    """
    augmented: List[Dict[str, Any]] = []
    
    for p in perspectives:
        pid = p["perspective_id"]
        raw_cohorts = cohort_ratings_map.get(pid, {})
        computed_cohorts = calculate_cohort_helpfulness(raw_cohorts)
        
        default_stats = {
            "total": 0,
            "helpful": 0,
            "raw_rate": 0.5,
            "approval_rate": 0.5,
            "approval_pct": 50,
            "wilson_lower": 0.0,
            "margin_of_error": 0.5,
        }
        c_a_info = computed_cohorts.get(cohort_a, default_stats)
        c_b_info = computed_cohorts.get(cohort_b, default_stats)
        
        bridge_info = classify_bridging_status(
            c_a_info["approval_rate"],
            c_b_info["approval_rate"],
            sample_a=c_a_info["total"],
            sample_b=c_b_info["total"],
            wilson_a=c_a_info.get("wilson_lower", 0.0),
            wilson_b=c_b_info.get("wilson_lower", 0.0),
            min_sample=min_sample,
            axis=cohort_axis,
        )
        
        p_item = dict(p)
        p_item["cohort_axis"] = cohort_axis
        p_item["cohort_a"] = cohort_a
        p_item["cohort_b"] = cohort_b
        p_item["cohort_a_stats"] = c_a_info
        p_item["cohort_b_stats"] = c_b_info
        p_item["all_cohort_stats"] = computed_cohorts
        p_item["bridging"] = bridge_info
        
        if bridge_info["is_sacred_bridge"]:
            p_item["bridging_status"] = "SACRED_BRIDGE"
        elif bridge_info["status"] in ("GENERATIONAL_CHASM", "DEMOGRAPHIC_CHASM", "INTRA_GROUP_ECHO"):
            p_item["bridging_status"] = "THE_SPLIT"
        else:
            p_item["bridging_status"] = bridge_info["status"]
            
        augmented.append(p_item)
        
    # Multi-Tier Pareto Lexicographical Sort:
    # 1. is_sacred_bridge (1 vs 0)
    # 2. has_quorum (1 vs 0) -> evaluated content strictly beats unvoted content
    # 3. conservative_bridge_score -> conservative Wilson harmonic score
    # 4. -polarization_delta -> lower polarization preferred
    # 5. total helpful ratings -> volume tie-breaker
    augmented.sort(
        key=lambda item: (
            1 if item["bridging"]["is_sacred_bridge"] else 0,
            1 if item["bridging"]["has_quorum"] else 0,
            item["bridging"]["conservative_bridge_score"],
            -item["bridging"]["polarization_delta"],
            item.get("helpful_ratings", 0),
        ),
        reverse=True,
    )
    
    return augmented

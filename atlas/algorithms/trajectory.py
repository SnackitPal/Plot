"""
Psychometric Drift Analytics Engine for PLOT: The Cultural Atlas.
Computes longitudinal vector trajectory metrics, step distances, mean drift velocity,
dimensional variance (Core Anchor vs Fluid Frontier), and Twin City Migration Journeys
across sequential 30-day slate completion snapshots.
"""

import math
from typing import List, Dict, Any, Optional

DIMENSION_LABELS = {
    "autonomy": "Work Autonomy",
    "punctuality": "Time Discipline",
    "boundary": "Family vs. Strangers",
    "freedom": "Financial Freedom",
    "trust": "Civic Trust",
}

DIMENSION_NARRATIVES = {
    "autonomy": {
        "anchor": "Your philosophy on personal autonomy and career freedom remains your unshakeable compass.",
        "frontier": "Your stance on career versus company loyalty adapts fluidly to specific dilemma stakes.",
    },
    "punctuality": {
        "anchor": "Your relationship with time and scheduling discipline is an immovable bedrock principle.",
        "frontier": "Your temporal margins and patience for tardiness flex dynamically across social vs professional contexts.",
    },
    "boundary": {
        "anchor": "Your loyalty to family vs. strangers stays firmly anchored.",
        "frontier": "Family vs. Strangers: This is where you wrestle the most. Depending on the scenario, you dynamically weigh loyalty to family against fairness to strangers.",
    },
    "freedom": {
        "anchor": "Your views on financial sovereignty and capital exit optionality are steadfast.",
        "frontier": "Your calculus regarding wealth, windfalls, and lifestyle security shows active, thoughtful re-evaluation.",
    },
    "trust": {
        "anchor": "Civic Trust: No matter what tricky dilemma we throw at you, your trust in everyday people and public rules stays rock-solid.",
        "frontier": "Your willingness to trust everyday people vs. double-check shifts depending on the scenario.",
    },
}

AXIS_KEYS = ["autonomy", "punctuality", "boundary", "freedom", "trust"]


def calculate_step_distance(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """
    Computes normalized Euclidean step distance between two 5D coordinates.
    Strictly in [0.0, 1.0].
    """
    sum_sq = sum((v1.get(k, 0.5) - v2.get(k, 0.5)) ** 2 for k in AXIS_KEYS)
    return round(min(1.0, math.sqrt(sum_sq) / math.sqrt(len(AXIS_KEYS))), 4)


def calculate_trajectory_analytics(snapshots: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates longitudinal evolution across sequential compass snapshots.
    Returns:
      - step_distances: list of normalized distance shifts between adjacent days
      - cumulative_distance: total path length traveled in 5D cultural space
      - mean_drift_velocity: average distance moved per completed day
      - stability_tier: classification of philosophical movement
      - core_anchor: dimension with lowest longitudinal variance (bedrock)
      - fluid_frontier: dimension with highest longitudinal variance (growth realm)
      - dimensional_variances: variance and mean for each of the 5 axes
      - city_journey: chronological sequence of primary twin cities
      - migration_summary: narrative summarizing cultural migration
      - history_points: sanitized coordinates ready for SVG radar ghost rendering
    """
    if not snapshots:
        return {
            "snapshot_count": 0,
            "cumulative_distance": 0.0,
            "mean_drift_velocity": 0.0,
            "stability_tier": {
                "key": "INITIAL",
                "label": "First Steps",
                "description": "Complete daily slates to unlock your longitudinal trajectory.",
            },
            "core_anchor": None,
            "fluid_frontier": None,
            "dimensional_variances": {},
            "city_journey": [],
            "migration_summary": "No trajectory recorded yet.",
            "history_points": [],
        }

    # Normalize snapshot coordinates into standard dicts
    cleaned_points = []
    for s in snapshots:
        vec = {
            "autonomy": float(s.get("vector_autonomy", 0.5)),
            "punctuality": float(s.get("vector_punctuality", 0.5)),
            "boundary": float(s.get("vector_boundary", 0.5)),
            "freedom": float(s.get("vector_freedom", 0.5)),
            "trust": float(s.get("vector_trust", 0.5)),
        }
        cleaned_points.append({
            "day_number": int(s.get("day_number", 1)),
            "vector": vec,
            "primary_city": str(s.get("primary_city", "")),
            "match_pct": float(s.get("match_pct", 0.0)),
            "confidence_pct": int(s.get("confidence_pct", 0)),
            "archetype_title": str(s.get("archetype_title", "")),
            "num_votes": int(s.get("num_votes", 0)),
            "calculated_at": str(s.get("calculated_at", "")),
        })

    # Sort strictly by day_number ascending
    cleaned_points.sort(key=lambda p: p["day_number"])

    # 1. Step distances and cumulative drift
    step_distances = [0.0]
    for i in range(1, len(cleaned_points)):
        dist = calculate_step_distance(cleaned_points[i - 1]["vector"], cleaned_points[i]["vector"])
        step_distances.append(dist)
        cleaned_points[i]["step_distance"] = dist

    cleaned_points[0]["step_distance"] = 0.0
    cumulative_distance = round(sum(step_distances), 4)
    n_steps = len(cleaned_points) - 1
    drift_velocity = round(cumulative_distance / n_steps, 4) if n_steps > 0 else 0.0

    # 2. Stability tier classification
    if drift_velocity < 0.04:
        stability_tier = {
            "key": "ANCHORED_BEDROCK",
            "label": "Rock-Solid Conviction",
            "badge": "⚓ Rock-Solid Conviction",
            "description": "No matter what dilemma we throw at you, your core values stay rock-solid.",
        }
    elif drift_velocity < 0.12:
        stability_tier = {
            "key": "GRADUAL_REFINER",
            "label": "Steady Explorer",
            "badge": "🧭 Steady Explorer",
            "description": "You thoughtfully adapt your views with each new dilemma.",
        }
    elif drift_velocity < 0.22:
        stability_tier = {
            "key": "EXPLORATORY_VOYAGER",
            "label": "Open-Minded Wanderer",
            "badge": "🌊 Open-Minded Wanderer",
            "description": "You are open to big shifts as fresh perspectives challenge your thinking.",
        }
    else:
        stability_tier = {
            "key": "PARADIGM_SHIFTER",
            "label": "Fresh Perspective",
            "badge": "⚡ Fresh Perspective",
            "description": "You frequently rethink your assumptions from the ground up.",
        }

    # 3. Longitudinal Variance per dimension
    dim_variances = {}
    n_points = len(cleaned_points)
    for axis in AXIS_KEYS:
        vals = [p["vector"][axis] for p in cleaned_points]
        mean_val = sum(vals) / n_points
        if n_points > 1:
            var_val = sum((x - mean_val) ** 2 for x in vals) / (n_points - 1)
        else:
            var_val = 0.0
        std_val = math.sqrt(var_val)
        dim_variances[axis] = {
            "key": axis,
            "label": DIMENSION_LABELS.get(axis, axis.title()),
            "mean": round(mean_val, 4),
            "variance": round(var_val, 6),
            "std_dev": round(std_val, 4),
            "stability_pct": max(0, min(100, round((1.0 - std_val * 2.0) * 100))),
        }

    # If fewer than 2 snapshots, variance is meaningless (N=1 single observation)
    if n_points < 2:
        core_anchor = None
        fluid_frontier = None
    else:
        sorted_by_var = sorted(dim_variances.values(), key=lambda d: d["variance"])
        anchor_dim = sorted_by_var[0]
        frontier_dim = sorted_by_var[-1]

        core_anchor = {
            "dimension_key": anchor_dim["key"],
            "label": anchor_dim["label"],
            "variance": anchor_dim["variance"],
            "stability_pct": anchor_dim["stability_pct"],
            "mean_value": anchor_dim["mean"],
            "narrative": DIMENSION_NARRATIVES.get(anchor_dim["key"], {}).get(
                "anchor", f"Your stance on {anchor_dim['label']} is your most steadfast conviction."
            ),
        }

        fluid_frontier = {
            "dimension_key": frontier_dim["key"],
            "label": frontier_dim["label"],
            "variance": frontier_dim["variance"],
            "volatility_pct": round(100 - frontier_dim["stability_pct"]),
            "mean_value": frontier_dim["mean"],
            "narrative": DIMENSION_NARRATIVES.get(frontier_dim["key"], {}).get(
                "frontier", f"Your stance on {frontier_dim['label']} is where your thinking evolves the most."
            ),
        }

    # 4. Twin City Migration Journey
    city_journey = []
    seen_cities = []
    for p in cleaned_points:
        c = p["primary_city"]
        if c:
            city_journey.append({
                "day_number": p["day_number"],
                "city": c,
                "match_pct": p["match_pct"],
            })
            if c not in seen_cities:
                seen_cities.append(c)

    if len(seen_cities) <= 1:
        migration_summary = f"Right at home (Locally Grounded): Your answers have consistently matched {seen_cities[0] if seen_cities else 'Reykjavik'} from day one."
    else:
        migration_summary = f"Your City Journey (Metropolitan Journey): Your vibe shifted through {' → '.join(seen_cities)} as you answered more questions."

    return {
        "snapshot_count": len(cleaned_points),
        "cumulative_distance": cumulative_distance,
        "mean_drift_velocity": drift_velocity,
        "step_distances": step_distances,
        "stability_tier": stability_tier,
        "core_anchor": core_anchor,
        "fluid_frontier": fluid_frontier,
        "dimensional_variances": dim_variances,
        "city_journey": city_journey,
        "distinct_cities_visited": seen_cities,
        "migration_summary": migration_summary,
        "history_points": cleaned_points,
    }

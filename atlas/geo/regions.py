"""
Geospatial Region Mapping & Cartogram Payload Engine for PLOT.
Bridges SVG macro-regions (data-region keys) with Uber H3 resolution-3 DGGS cells
and calculates live Empirical Bayes shrinkage statistics and credible intervals.
"""

from typing import Dict, Any, Optional, Tuple, List
import h3
from atlas.geo.hexgrid import AtlasHexGrid
from atlas.algorithms.shrinkage import EmpiricalBayesShrinkage
from atlas.content.benchmarks import get_benchmark_meta

# The 19 canonical macro-regions defined in PLOT's interactive cartogram
REGION_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "US_WEST": {
        "name": "United States (Pacific / Mountain)",
        "flag": "🇺🇸",
        "lat": 37.7749,
        "lng": -122.4194,
        "baseline_sample": 12450,
        "baseline_dist": [58, 22, 14, 6],
    },
    "US_EAST": {
        "name": "United States (Atlantic / Midwest)",
        "flag": "🇺🇸",
        "lat": 40.7128,
        "lng": -74.0060,
        "baseline_sample": 15300,
        "baseline_dist": [41, 49, 7, 3],
    },
    "CANADA": {
        "name": "Canada (All Provinces)",
        "flag": "🇨🇦",
        "lat": 43.6532,
        "lng": -79.3832,
        "baseline_sample": 3200,
        "baseline_dist": [64, 20, 11, 5],
    },
    "MEXICO": {
        "name": "Mexico (Metropolitan Areas)",
        "flag": "🇲🇽",
        "lat": 19.4326,
        "lng": -99.1332,
        "baseline_sample": 2890,
        "baseline_dist": [52, 33, 10, 5],
    },
    "BRAZIL": {
        "name": "Brazil (South / Southeast)",
        "flag": "🇧🇷",
        "lat": -23.5505,
        "lng": -46.6333,
        "baseline_sample": 3600,
        "baseline_dist": [32, 55, 9, 4],
    },
    "SOUTHERN_CONE": {
        "name": "Southern Cone (Argentina & Chile)",
        "flag": "🇦🇷",
        "lat": -34.6037,
        "lng": -58.3816,
        "baseline_sample": 1950,
        "baseline_dist": [38, 48, 10, 4],
    },
    "UK_IRELAND": {
        "name": "United Kingdom & Ireland",
        "flag": "🇬🇧",
        "lat": 51.5074,
        "lng": -0.1278,
        "baseline_sample": 4120,
        "baseline_dist": [66, 18, 12, 4],
    },
    "NORDICS": {
        "name": "Nordic Countries (SE, NO, DK, FI)",
        "flag": "🇸🇪",
        "lat": 59.3293,
        "lng": 18.0686,
        "baseline_sample": 2100,
        "baseline_dist": [35, 10, 51, 4],
    },
    "WEST_EUROPE": {
        "name": "Germany, France & Benelux",
        "flag": "🇪🇺",
        "lat": 48.8566,
        "lng": 2.3522,
        "baseline_sample": 8900,
        "baseline_dist": [61, 23, 12, 4],
    },
    "SOUTH_EUROPE": {
        "name": "Italy, Spain & Portugal",
        "flag": "🇪🇸",
        "lat": 41.9028,
        "lng": 12.4964,
        "baseline_sample": 4300,
        "baseline_dist": [36, 53, 8, 3],
    },
    "NORTH_AFRICA": {
        "name": "North Africa (Egypt, Morocco)",
        "flag": "🇪🇬",
        "lat": 30.0444,
        "lng": 31.2357,
        "baseline_sample": 1820,
        "baseline_dist": [29, 58, 9, 4],
    },
    "SUB_SAHARA": {
        "name": "Sub-Saharan Africa (West & East)",
        "flag": "🇳🇬",
        "lat": 6.5244,
        "lng": 3.3792,
        "baseline_sample": 2400,
        "baseline_dist": [22, 68, 7, 3],
    },
    "SOUTH_AFRICA": {
        "name": "Southern Africa",
        "flag": "🇿🇦",
        "lat": -26.2041,
        "lng": 28.0473,
        "baseline_sample": 1650,
        "baseline_dist": [44, 42, 10, 4],
    },
    "MIDDLE_EAST": {
        "name": "Middle East & Gulf States",
        "flag": "🇦🇪",
        "lat": 25.2048,
        "lng": 55.2708,
        "baseline_sample": 3100,
        "baseline_dist": [30, 54, 11, 5],
    },
    "SOUTH_ASIA": {
        "name": "South Asia (India, Pakistan, BD)",
        "flag": "🇮🇳",
        "lat": 19.0760,
        "lng": 72.8777,
        "baseline_sample": 6400,
        "baseline_dist": [24, 65, 8, 3],
    },
    "EAST_ASIA": {
        "name": "East Asia (Japan & South Korea)",
        "flag": "🇯🇵",
        "lat": 35.6762,
        "lng": 139.6503,
        "baseline_sample": 3800,
        "baseline_dist": [28, 22, 6, 44],
    },
    "SE_ASIA": {
        "name": "Southeast Asia (ASEAN)",
        "flag": "🇸🇬",
        "lat": 1.3521,
        "lng": 103.8198,
        "baseline_sample": 3400,
        "baseline_dist": [33, 52, 10, 5],
    },
    "OCEANIA": {
        "name": "Australia & New Zealand",
        "flag": "🇦🇺",
        "lat": -33.8688,
        "lng": 151.2093,
        "baseline_sample": 2900,
        "baseline_dist": [59, 21, 14, 6],
    },
    "CENTRAL_ASIA": {
        "name": "Central Asian Republics",
        "flag": "🇰🇿",
        "lat": 43.2389,
        "lng": 76.8897,
        "baseline_sample": 18,  # Under threshold (n < 30) for testing hatched state
        "baseline_dist": [25, 25, 25, 25],
    },
}

_hexgrid = AtlasHexGrid(resolution=3)

# Pre-computed mapping: region_key -> H3 cell ID
REGION_TO_H3: Dict[str, str] = {
    k: _hexgrid.latlng_to_cell(v["lat"], v["lng"]) for k, v in REGION_DEFINITIONS.items()
}

# Reverse mapping: H3 cell ID -> region_key
H3_TO_REGION: Dict[str, str] = {h3_cell: k for k, h3_cell in REGION_TO_H3.items()}


def get_region_key_for_cell(cell_id: str) -> Optional[str]:
    """Resolve an H3 cell ID to its matching SVG region key."""
    return H3_TO_REGION.get(cell_id)


def get_h3_cell_for_region(region_key: str) -> str:
    """Get the canonical H3 resolution-3 cell ID for an SVG region key."""
    if region_key not in REGION_TO_H3:
        raise KeyError(f"Unknown region key: '{region_key}'")
    return REGION_TO_H3[region_key]


def compute_cartogram_payload(
    question_id: str,
    db: Any,
    shrinkage: Optional[EmpiricalBayesShrinkage] = None,
    tier_filter: str = "all",
    mode: str = "community",
) -> Dict[str, Any]:
    """
    Construct the structured cartogram JSON payload for the frontend.
    Aggregates recorded SQLite votes by region, computes raw percentages,
    and applies Beta-Binomial Empirical Bayes shrinkage for 95% Credible Intervals.
    Supports tier_filter ('all' or 'verified').
    """
    if shrinkage is None:
        shrinkage = EmpiricalBayesShrinkage(
            prior_mean=0.25,  # Uninformative null prior for K=4 categorical options
            prior_weight=30.0,
            min_sample_threshold=30,
            confidence_level=0.95,
        )

    # 1. Fetch raw vote aggregates from SQLite based on tier_filter
    if tier_filter == "verified" and hasattr(db, "get_tier_hex_aggregates"):
        raw_rows = db.get_tier_hex_aggregates(question_id, min_tier=2)
    else:
        raw_rows = db.get_all_hex_aggregates(question_id)
    
    # Map cell_id -> {choice_letter: count}
    cell_votes: Dict[str, Dict[str, int]] = {}
    for row in raw_rows:
        cid = row["h3_cell_id"]
        letter = row["choice_letter"]
        count = row["vote_count"]
        if cid not in cell_votes:
            cell_votes[cid] = {}
        cell_votes[cid][letter] = cell_votes[cid].get(letter, 0) + count

    # 2. Compile regions data dictionary
    regions_payload: Dict[str, Any] = {}
    total_global_votes = 0
    global_letter_counts: Dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}

    bench_meta = get_benchmark_meta(question_id)

    for reg_key, meta in REGION_DEFINITIONS.items():
        cell_id = REGION_TO_H3[reg_key]
        votes_dict = cell_votes.get(cell_id, {})
        
        count_a = votes_dict.get("A", 0)
        count_b = votes_dict.get("B", 0)
        count_c = votes_dict.get("C", 0)
        count_d = votes_dict.get("D", 0)
        sample = count_a + count_b + count_c + count_d

        # Benchmark ground-truth target
        if bench_meta and reg_key in bench_meta.get("distributions", {}):
            bench_target_dist = list(bench_meta["distributions"][reg_key])
        else:
            bench_target_dist = list(meta["baseline_dist"])

        if mode == "benchmark":
            # Direct empirical benchmark data
            dist = bench_target_dist
            sample = meta["baseline_sample"]
            count_a = int(sample * (dist[0] / 100.0))
            count_b = int(sample * (dist[1] / 100.0))
            count_c = int(sample * (dist[2] / 100.0))
            count_d = max(0, sample - (count_a + count_b + count_c))
        elif sample > 0:
            pct_a = round((count_a / sample) * 100)
            pct_b = round((count_b / sample) * 100)
            pct_c = round((count_c / sample) * 100)
            pct_d = max(0, 100 - (pct_a + pct_b + pct_c))
            dist = [pct_a, pct_b, pct_c, pct_d]
        else:
            # Fall back to baseline proportions if no live votes yet recorded
            dist = bench_target_dist
            if tier_filter == "verified":
                sample = max(20, int(meta["baseline_sample"] * 0.20))
                dist_b = min(90, dist[1] + 6)
                dist_a = max(5, dist[0] - 6)
                count_a = int(sample * (dist_a / 100.0))
                count_b = int(sample * (dist_b / 100.0))
                count_c = int(sample * (dist[2] / 100.0))
                count_d = max(0, sample - (count_a + count_b + count_c))
            else:
                sample = meta["baseline_sample"]
                count_a = int(sample * (dist[0] / 100.0))
                count_b = int(sample * (dist[1] / 100.0))
                count_c = int(sample * (dist[2] / 100.0))
                count_d = max(0, sample - (count_a + count_b + count_c))

        total_global_votes += sample
        global_letter_counts["A"] += count_a
        global_letter_counts["B"] += count_b
        global_letter_counts["C"] += count_c
        global_letter_counts["D"] += count_d

        # Determine dominant choice
        choice_tuples = [("A", count_a), ("B", count_b), ("C", count_c), ("D", count_d)]
        dominant_letter, dominant_count = max(choice_tuples, key=lambda x: x[1])

        # Empirical Bayes shrinkage calculation for dominant choice
        estimate = shrinkage.estimate_cell(cell_id, dominant_count, sample)
        if estimate.is_hatched:
            ci_str = f"INSUFFICIENT SAMPLE (Hatched n = {sample} < 30)"
        else:
            ci_str = f"{estimate.ci_lower * 100:.1f}% — {estimate.ci_upper * 100:.1f}%"

        # Compute divergence against benchmark
        divergence_delta = [dist[i] - bench_target_dist[i] for i in range(4)]
        max_delta_val = max(divergence_delta, key=abs)

        regions_payload[reg_key] = {
            "name": meta["name"],
            "flag": meta["flag"],
            "sample": sample,
            "dist": dist,
            "ci": ci_str,
            "dominant": dominant_letter,
            "is_hatched": estimate.is_hatched,
            "h3_cell": cell_id,
            "benchmark_dist": bench_target_dist,
            "divergence": {
                "delta": divergence_delta,
                "max_delta": max_delta_val,
                "dominant_divergence": dominant_letter if abs(max_delta_val) >= 5 else None,
            },
            "raw_counts": {
                "A": count_a,
                "B": count_b,
                "C": count_c,
                "D": count_d,
            },
        }

    # Global distribution summary
    if total_global_votes > 0:
        g_pct_a = round((global_letter_counts["A"] / total_global_votes) * 100)
        g_pct_b = round((global_letter_counts["B"] / total_global_votes) * 100)
        g_pct_c = round((global_letter_counts["C"] / total_global_votes) * 100)
        g_pct_d = max(0, 100 - (g_pct_a + g_pct_b + g_pct_c))
        global_dist = [g_pct_a, g_pct_b, g_pct_c, g_pct_d]
    else:
        global_dist = [25, 25, 25, 25]

    return {
        "question_id": question_id,
        "tier_filter": tier_filter,
        "mode": mode,
        "provenance": bench_meta if bench_meta else None,
        "regions": regions_payload,
        "global_summary": {
            "total_votes": total_global_votes,
            "dist": global_dist,
            "counts": global_letter_counts,
        },
    }

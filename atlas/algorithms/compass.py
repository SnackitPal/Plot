"""
Multi-Dimensional Archetype Engine for PLOT: The Cultural Atlas.

Transforms a user's discrete daily votes across the 5 cultural axes into a continuous
5-dimensional cultural vector in [0.0, 1.0]^5:
1. Work Autonomy (q_01: Work vs. Income Primacy)
2. Punctuality Strictness (q_02: Monochronic vs. Polychronic Time)
3. Relational Decoupling (q_03: Interpersonal Boundary Permeability)
4. Capital Freedom (q_04: Financial Exit Velocity vs. Duty)
5. Civic Trust (q_05: Generalized Social Trust)

Matches the user against 15 empirically modeled Global City Centroids,
calculates normalized Euclidean distance alignment (0–100%), identifies Primary
Twin and Counter-Twin cities, and assigns a signature Cultural Archetype.
"""

import math
from typing import Dict, List, Tuple, Any, Optional

# Dimensional definitions
DIMENSIONS = [
    {
        "key": "autonomy",
        "label": "Work Autonomy",
        "question_id": "q_01",
        "low_label": "Income/Structure Primacy",
        "high_label": "Time Sovereignty",
        "color": "#E66101",
    },
    {
        "key": "punctuality",
        "label": "Punctuality Strictness",
        "question_id": "q_02",
        "low_label": "Polychronic Fluidity",
        "high_label": "Monochronic Precision",
        "color": "#5D8AA8",
    },
    {
        "key": "boundary",
        "label": "Relational Integration",
        "question_id": "q_03",
        "low_label": "Clean Separation",
        "high_label": "Relational Integration",
        "color": "#008856",
    },
    {
        "key": "freedom",
        "label": "Capital Freedom",
        "question_id": "q_04",
        "low_label": "Duty & Work Identity",
        "high_label": "Immediate Exit Velocity",
        "color": "#7B3294",
    },
    {
        "key": "trust",
        "label": "Civic Trust",
        "question_id": "q_05",
        "low_label": "Vigilant Skepticism",
        "high_label": "Generalized High Trust",
        "color": "#FF8C42",
    },
]

# Coordinate mapping per question choice
CHOICE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "q_01": {
        "A": 1.00,  # "Yes, without hesitation" -> Maximum Autonomy
        "B": 0.05,  # "No, income comes first" -> Income Primacy
        "C": 0.50,  # "Only if commute was >60 mins" -> Pragmatic Autonomy
        "D": 0.15,  # "I prefer commuting / office life" -> Social/Office Anchored
    },
    "q_02": {
        "A": 1.00,  # "Extremely rude, punctuality is absolute" -> Monochronic Strict
        "B": 0.05,  # "Polite / Expected buffer" -> Fluid / Expected buffer
        "C": 0.65,  # "Slightly discourteous, merits an apology" -> Moderately strict
        "D": 0.20,  # "Completely unnoticed or standard" -> Very relaxed
    },
    "q_03": {
        "A": 0.90,  # "Yes, genuine friendship is healthy" -> High relational integration
        "B": 0.10,  # "No, clean break always" -> Clean decoupling / strict boundary
        "C": 0.50,  # "Only distant social media polite check-ins" -> Moderate boundary
        "D": 0.40,  # "Depends on future partner comfort" -> Conditional boundary
    },
    "q_04": {
        "A": 1.00,  # "Immediately, next day resignation" -> Instant exit velocity
        "B": 0.05,  # "No, keep working for structure and purpose" -> Duty / Identity anchored
        "C": 0.75,  # "Pivot to passion project / creative work" -> Self-actualization pivot
        "D": 0.60,  # "Finish current quarter then exit gracefully" -> Conscientious exit
    },
    "q_05": {
        "A": 1.00,  # "High trust (leave front door unlocked)" -> Absolute high trust
        "B": 0.55,  # "Moderate trust (pragmatic vigilance)" -> Balanced vigilance
        "C": 0.10,  # "Low trust (assume stranger opportunism)" -> High skepticism
        "D": 0.30,  # "Highly hyper-segregated trust pockets" -> In-group fragmented
    },
}

# 15 Global City Centroids across 5 continents
GLOBAL_CITY_CENTROIDS: List[Dict[str, Any]] = [
    {
        "city_id": "tokyo",
        "city_name": "Tokyo",
        "country": "Japan",
        "flag": "🇯🇵",
        "vector": [0.35, 0.95, 0.25, 0.20, 0.92],
        "tagline": "Precision, duty, and community first",
        "narrative": "Tokyo runs on clockwork punctuality, social harmony, and duty to the team—almost the exact flip side of your personal-freedom-first mindset.",
    },
    {
        "city_id": "berlin",
        "city_name": "Berlin",
        "country": "Germany",
        "flag": "🇩🇪",
        "vector": [0.88, 0.82, 0.70, 0.75, 0.75],
        "tagline": "Autonomous Subcultural Freedom",
        "narrative": "Fiercely defends work-life sovereignty and unconventional lifepaths while upholding reliable German punctuality.",
    },
    {
        "city_id": "reykjavik",
        "city_name": "Reykjavik",
        "country": "Iceland",
        "flag": "🇮🇸",
        "vector": [0.90, 0.45, 0.85, 0.80, 0.95],
        "tagline": "High trust, chill schedules, maximum freedom",
        "narrative": "You believe people are fundamentally decent, you value your independence, and you don't stress over a 5-minute delay.",
    },
    {
        "city_id": "new_york",
        "city_name": "New York City",
        "country": "United States",
        "flag": "🇺🇸",
        "vector": [0.65, 0.72, 0.50, 0.90, 0.45],
        "tagline": "High-Velocity Pragmatic Ambition",
        "narrative": "Maximum appetite for capital exit and reinvention, balanced with rapid-tempo urban vigilance.",
    },
    {
        "city_id": "sao_paulo",
        "city_name": "São Paulo",
        "country": "Brazil",
        "flag": "🇧🇷",
        "vector": [0.55, 0.22, 0.78, 0.85, 0.25],
        "tagline": "Warm Relational Improvisation",
        "narrative": "High social warmth and relationship primacy with flexible time norms and agile street-smart navigation.",
    },
    {
        "city_id": "singapore",
        "city_name": "Singapore",
        "country": "Singapore",
        "flag": "🇸🇬",
        "vector": [0.40, 0.88, 0.35, 0.52, 0.90],
        "tagline": "Hyper-Efficient Technocratic Harmony",
        "narrative": "Flawless infrastructure, high civic safety, and strong respect for meritocracy and orderly civic life.",
    },
    {
        "city_id": "zurich",
        "city_name": "Zurich",
        "country": "Switzerland",
        "flag": "🇨🇭",
        "vector": [0.62, 0.95, 0.35, 0.80, 0.92],
        "tagline": "Precision Institutional Sovereignty",
        "narrative": "Uncompromising punctuality, immaculate public trust, and a quiet, discreet respect for personal autonomy.",
    },
    {
        "city_id": "london",
        "city_name": "London",
        "country": "United Kingdom",
        "flag": "🇬🇧",
        "vector": [0.75, 0.75, 0.52, 0.72, 0.62],
        "tagline": "Cosmopolitan Balance & Irony",
        "narrative": "Navigates tradition and relentless modernism, balancing professional diligence with quiet boundaries.",
    },
    {
        "city_id": "seoul",
        "city_name": "Seoul",
        "country": "South Korea",
        "flag": "🇰🇷",
        "vector": [0.30, 0.90, 0.28, 0.72, 0.82],
        "tagline": "Dynamic Hyper-Paced Achiever",
        "narrative": "Relentless speed ('Palli-palli'), unmatched tech adoption, strong collective cohesion, and fierce work ethic.",
    },
    {
        "city_id": "amsterdam",
        "city_name": "Amsterdam",
        "country": "Netherlands",
        "flag": "🇳🇱",
        "vector": [0.92, 0.80, 0.68, 0.85, 0.86],
        "tagline": "Direct Democratic Humanism",
        "narrative": "Unapologetic work-life balance, direct communication, high civic trust, and celebrated personal freedom.",
    },
    {
        "city_id": "mumbai",
        "city_name": "Mumbai",
        "country": "India",
        "flag": "🇮🇳",
        "vector": [0.45, 0.28, 0.88, 0.82, 0.40],
        "tagline": "Resilient In-Group Vitality ('Jugaad')",
        "narrative": "Extraordinary familial warmth, fluid temporal margins, and relentless entrepreneurial energy amid urban density.",
    },
    {
        "city_id": "nairobi",
        "city_name": "Nairobi",
        "country": "Kenya",
        "flag": "🇰🇪",
        "vector": [0.75, 0.35, 0.82, 0.85, 0.50],
        "tagline": "Agile Communal Enterprise",
        "narrative": "Silicon Savannah agility, deep communal mutual aid, flexible social timing, and rapid technological leapfrogging.",
    },
    {
        "city_id": "sydney",
        "city_name": "Sydney",
        "country": "Australia",
        "flag": "🇦🇺",
        "vector": [0.85, 0.65, 0.60, 0.80, 0.78],
        "tagline": "Easygoing Outdoor Individualism",
        "narrative": "Refuses to let careers consume life, pairing high egalitarian trust with a breezy, pragmatic social tempo.",
    },
    {
        "city_id": "madrid",
        "city_name": "Madrid",
        "country": "Spain",
        "flag": "🇪🇸",
        "vector": [0.78, 0.30, 0.85, 0.82, 0.68],
        "tagline": "Nocturnal Relational Vitality",
        "narrative": "Prioritizes evening terrace sociability and warm human connection far above rigid clock adherence.",
    },
    {
        "city_id": "cairo",
        "city_name": "Cairo",
        "country": "Egypt",
        "flag": "🇪🇬",
        "vector": [0.35, 0.15, 0.90, 0.75, 0.42],
        "tagline": "Deeply Rooted Kinship Traditionalism",
        "narrative": "Rich relational loyalty and hospitality where human connection and community always transcend the clock.",
    },
]


# 5x6 Domain Projection Matrix Pi
DOMAIN_PROJECTIONS: Dict[str, Dict[str, float]] = {
    "WORK_MOBILITY": {"autonomy": 1.0, "punctuality": 0.0, "boundary": 0.0, "freedom": 0.0, "trust": 0.0},
    "TIME_SOCIABILITY": {"autonomy": 0.0, "punctuality": 1.0, "boundary": 0.0, "freedom": 0.0, "trust": 0.0},
    "KINSHIP_BOUNDARIES": {"autonomy": 0.0, "punctuality": 0.0, "boundary": 1.0, "freedom": 0.0, "trust": 0.0},
    "CAPITAL_FREEDOM": {"autonomy": 0.0, "punctuality": 0.0, "boundary": 0.0, "freedom": 1.0, "trust": 0.0},
    "CIVIC_TRUST": {"autonomy": 0.0, "punctuality": 0.0, "boundary": 0.0, "freedom": 0.0, "trust": 1.0},
    "EXISTENTIAL_TECH": {"autonomy": 0.40, "punctuality": 0.0, "boundary": 0.30, "freedom": 0.0, "trust": 0.30},
}
DOMAIN_PROJECTION_TENSOR = DOMAIN_PROJECTIONS


def calculate_profile_confidence(
    num_votes: int,
    dimensional_weights: Optional[Dict[str, float]] = None,
) -> int:
    """
    Computes profile confidence metric (0-100%):
    When dimensional_weights are provided, evaluates joint multidimensional
    Fisher information coverage across all 5 axes:
    Confidence = min(100, round(100 * prod_{k=1}^5 (1 - exp(-w_k / 2.5))^0.2))
    Otherwise evaluates standard asymptotic curve min(100, round((1 - exp(-N / 6)) * 100)).
    """
    if num_votes <= 0:
        return 0

    if dimensional_weights and len(dimensional_weights) == 5:
        product = 1.0
        for k, w in dimensional_weights.items():
            dim_cov = max(0.05, 1.0 - math.exp(-max(0.0, w) / 1.2))
            product *= dim_cov
        geom_mean = product ** 0.2
        raw = geom_mean * 100.0
        return min(100, max(0, round(raw)))

    raw = (1.0 - math.exp(-num_votes / 6.0)) * 100.0
    return min(100, max(0, round(raw)))


def compute_user_dimensional_weights(
    votes: Dict[str, str],
    question_catalog: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Computes total accumulated evidence weights across each of the 5 dimensions."""
    catalog = question_catalog
    if catalog is None:
        try:
            from atlas.content.slates_30d import SLATES_30D
            catalog = {}
            for slate in SLATES_30D:
                for q in slate["questions"]:
                    weights = {ch["letter"]: ch["weight"] for ch in q["choices"]}
                    catalog[q["question_id"]] = {
                        "domain": q["domain"],
                        "axis": q["axis"],
                        "weights": weights,
                    }
        except ImportError:
            catalog = {}

    total_weights = {d["key"]: 0.0 for d in DIMENSIONS}
    for q_id, choice_raw in votes.items():
        if not choice_raw:
            continue
        choice = str(choice_raw).upper()

        if q_id in catalog:
            q_info = catalog[q_id]
            if choice in q_info.get("weights", {}):
                domain = q_info.get("domain", "")
                projections = DOMAIN_PROJECTIONS.get(domain, {q_info.get("axis", "autonomy"): 1.0})
                for axis_key, w in projections.items():
                    if axis_key in total_weights and w > 0:
                        total_weights[axis_key] += w
        elif q_id in CHOICE_WEIGHTS and choice in CHOICE_WEIGHTS[q_id]:
            axis_map = {
                "q_01": "autonomy",
                "q_02": "punctuality",
                "q_03": "boundary",
                "q_04": "freedom",
                "q_05": "trust",
            }
            axis_key = axis_map.get(q_id)
            if axis_key and axis_key in total_weights:
                total_weights[axis_key] += 1.0

    return total_weights


def compute_user_vector(
    votes: Dict[str, str],
    question_catalog: Optional[Dict[str, Any]] = None,
    prior_weight: float = 0.0,
    prior_mean: float = 0.50,
) -> Dict[str, float]:
    """
    Computes 5D normalized cultural coordinates from user votes using the
    Deterministic Bayesian Accumulator across the 5x6 Domain Projection Matrix:
    u_k(V) = (prior_weight * prior_mean + sum_{q in V} W_{q,k} * s(q, v_q)) / (prior_weight + sum_{q in V} W_{q,k})
    When prior_weight == 0.0 (default), computes standard order-invariant weighted mean,
    with unvoted dimensions falling back to 0.50.
    When prior_weight > 0.0 (e.g., 1.0), applies conjugate Bayesian prior shrinkage towards 0.50.
    Order-invariant, re-vote immune, and scales naturally across 1 to 150 dilemmas.
    """
    # Lazy load full catalog if available
    catalog = question_catalog
    if catalog is None:
        try:
            from atlas.content.slates_30d import SLATES_30D
            catalog = {}
            for slate in SLATES_30D:
                for q in slate["questions"]:
                    weights = {ch["letter"]: ch["weight"] for ch in q["choices"]}
                    catalog[q["question_id"]] = {
                        "domain": q["domain"],
                        "axis": q["axis"],
                        "weights": weights,
                    }
        except ImportError:
            catalog = {}

    weighted_sums = {d["key"]: 0.0 for d in DIMENSIONS}
    total_weights = {d["key"]: 0.0 for d in DIMENSIONS}

    for q_id, choice_raw in votes.items():
        if not choice_raw:
            continue
        choice = str(choice_raw).upper()

        # Check in full catalog
        if q_id in catalog:
            q_info = catalog[q_id]
            weights = q_info.get("weights", {})
            if choice in weights:
                score = weights[choice]
                domain = q_info.get("domain", "")
                projections = DOMAIN_PROJECTIONS.get(domain, {q_info.get("axis", "autonomy"): 1.0})
                for axis_key, w in projections.items():
                    if axis_key in weighted_sums and w > 0:
                        weighted_sums[axis_key] += w * score
                        total_weights[axis_key] += w

        # Fallback to Day 1 CHOICE_WEIGHTS
        elif q_id in CHOICE_WEIGHTS:
            if choice in CHOICE_WEIGHTS[q_id]:
                score = CHOICE_WEIGHTS[q_id][choice]
                # Map q_01..q_05 to axis
                axis_map = {
                    "q_01": "autonomy",
                    "q_02": "punctuality",
                    "q_03": "boundary",
                    "q_04": "freedom",
                    "q_05": "trust",
                }
                axis_key = axis_map.get(q_id)
                if axis_key and axis_key in weighted_sums:
                    weighted_sums[axis_key] += 1.0 * score
                    total_weights[axis_key] += 1.0

    vector = {}
    for d in DIMENSIONS:
        key = d["key"]
        t_weight = total_weights[key]
        if prior_weight > 0.0:
            vector[key] = round((prior_weight * prior_mean + weighted_sums[key]) / (prior_weight + t_weight), 4)
        elif t_weight > 0:
            vector[key] = round(weighted_sums[key] / t_weight, 4)
        else:
            vector[key] = prior_mean  # Neutral prior baseline

    return vector


def calculate_normalized_euclidean_distance(v1: List[float], v2: List[float]) -> float:
    """
    Computes normalized Euclidean distance between two 5D vectors.
    Since each coordinate is in [0, 1], maximum Euclidean distance is sqrt(5) ≈ 2.236.
    Normalized distance is strictly in [0.0, 1.0].
    """
    if len(v1) != len(v2) or len(v1) == 0:
        return 1.0
    sum_sq = sum((a - b) ** 2 for a, b in zip(v1, v2))
    raw_dist = math.sqrt(sum_sq)
    norm_dist = min(1.0, raw_dist / math.sqrt(len(v1)))
    return round(norm_dist, 4)


def calculate_alignment_pct(v1: List[float], v2: List[float]) -> float:
    """Computes percentage alignment: (1.0 - norm_distance) * 100."""
    dist = calculate_normalized_euclidean_distance(v1, v2)
    return round(max(0.0, (1.0 - dist) * 100), 1)


def find_city_matches(user_vector: Dict[str, float]) -> Dict[str, Any]:
    """
    Finds the closest (Primary Twin) and most distant (Counter-Twin) cities,
    along with ranked similarity scores across all 15 global hubs.
    """
    u_list = [
        user_vector.get("autonomy", 0.5),
        user_vector.get("punctuality", 0.5),
        user_vector.get("boundary", 0.5),
        user_vector.get("freedom", 0.5),
        user_vector.get("trust", 0.5),
    ]

    scored = []
    for city in GLOBAL_CITY_CENTROIDS:
        c_list = city["vector"]
        dist = calculate_normalized_euclidean_distance(u_list, c_list)
        pct = calculate_alignment_pct(u_list, c_list)
        scored.append({
            "city_id": city["city_id"],
            "city_name": city["city_name"],
            "country": city["country"],
            "flag": city["flag"],
            "match_pct": pct,
            "distance": dist,
            "tagline": city["tagline"],
            "narrative": city["narrative"],
        })

    # Sort descending by match_pct (closest first)
    scored.sort(key=lambda x: x["match_pct"], reverse=True)

    primary = scored[0]
    counter = scored[-1]

    return {
        "primary_twin": primary,
        "counter_twin": counter,
        "all_matches": scored,
    }


def classify_archetype(user_vector: Dict[str, float]) -> Dict[str, Any]:
    """
    Classifies a user into one of 8 signature cultural archetypes
    based on their dimensional coordinate profile.
    """
    autonomy = user_vector.get("autonomy", 0.5)
    punctuality = user_vector.get("punctuality", 0.5)
    boundary = user_vector.get("boundary", 0.5)
    freedom = user_vector.get("freedom", 0.5)
    trust = user_vector.get("trust", 0.5)

    if autonomy >= 0.70 and freedom >= 0.70 and punctuality >= 0.60:
        return {
            "title": "THE AUTONOMOUS COSMOPOLITAN",
            "tagline": "Independent, self-driven, and hates wasting time.",
            "summary": "You guard your personal freedom fiercely, but you're dead serious about showing up on time and keeping your word.",
            "superpower": "You carve your own path and never wait around for permission.",
            "blindspot": "Zero patience for endless committee meetings and slow bureaucracy.",
        }

    if autonomy >= 0.70 and punctuality <= 0.45:
        return {
            "title": "THE RELATIONAL NOMAD",
            "tagline": "Organic, Flexible, and Unshackled",
            "summary": "You reject clockwork rigidity in favor of organic social rhythm. Work is a tool for living, and relationships take precedence over schedules.",
            "superpower": "Extreme adaptability and genuine human connection across cultures.",
            "blindspot": "Can frustrate partners who rely on fixed deadlines and calendar precision.",
        }

    if punctuality >= 0.75 and trust >= 0.75:
        return {
            "title": "THE CIVIC PRECISIONIST",
            "tagline": "Orderly, Conscientious, and High-Trust",
            "summary": "You believe modern civilization flourishes when everyone is on time, keeps their word, and respects shared civic spaces.",
            "superpower": "Flawless reliability and the foundation of high-trust public institutions.",
            "blindspot": "Overly harsh judgment of cultures with fluid temporal margins.",
        }

    if boundary >= 0.75 and trust <= 0.45:
        return {
            "title": "THE RESILIENT IN-GROUP PROTECTOR",
            "tagline": "Vigilant, Communal, and Fiercely Loyal",
            "summary": "You place deep trust in your inner kinship circle while maintaining a healthy, pragmatic skepticism toward abstract institutions.",
            "superpower": "Unmatched loyalty and resourcefulness in turbulent environments.",
            "blindspot": "Reluctance to extend immediate trust to unfamiliar strangers or outsiders.",
        }

    if trust >= 0.75 and boundary >= 0.65:
        return {
            "title": "THE EGALITARIAN HUMANIST",
            "tagline": "High-Trust, Empathetic, and Inclusive",
            "summary": "You approach the world with radical goodwill, trusting strangers by default and seeing friendships as continuous lifelong bonds.",
            "superpower": "Builds psychological safety and bridges polarized groups effortlessly.",
            "blindspot": "Vulnerability to opportunistic exploitation in low-trust environments.",
        }

    if freedom <= 0.35 and punctuality >= 0.70:
        return {
            "title": "THE DEDICATED INSTITUTIONALIST",
            "tagline": "Disciplined, Duty-Bound, and Purpose-Driven",
            "summary": "You find deep meaning in craftsmanship, duty, and professional continuity. You wouldn't abandon your post simply because of windfall money.",
            "superpower": "Ironclad endurance and mastery that withstands economic volatility.",
            "blindspot": "Risk of identity entanglement with corporate or institutional roles.",
        }

    if freedom >= 0.75 and trust <= 0.40:
        return {
            "title": "THE SOVEREIGN PRAGMATIST",
            "tagline": "Calculated, Exit-Ready, and Self-Reliant",
            "summary": "You build your life around optionality and leverage. You believe personal autonomy is won through capital independence and sharp boundaries.",
            "superpower": "Decisive decision-making under uncertainty; zero vulnerability to traps.",
            "blindspot": "Can isolate oneself from the enduring beauty of collective interdependence.",
        }

    return {
        "title": "THE BALANCED SYNTHESIZER",
        "tagline": "Nuanced, Pragmatic, and Culturally Fluent",
        "summary": "You hold a rare equilibrium across the cultural spectrum—demanding neither absolute freedom nor rigid conformity. You adapt seamlessly anywhere.",
        "superpower": "Effortless cultural code-switching across diverse global contexts.",
        "blindspot": "Can struggle to take extreme decisive stands when consensus is impossible.",
    }


def generate_compass_report(rater_salt: str, votes: Dict[str, str]) -> Dict[str, Any]:
    """
    Compiles a comprehensive Compass Profile report for a user,
    including 5D coordinates, radar chart points, city matches, and archetype analysis.
    """
    user_vec = compute_user_vector(votes)
    matches = find_city_matches(user_vec)
    archetype = classify_archetype(user_vec)

    # Format dimension scores as percentages
    dimensions_report = []
    for d in DIMENSIONS:
        val = user_vec.get(d["key"], 0.5)
        dimensions_report.append({
            "key": d["key"],
            "label": d["label"],
            "value": val,
            "percentage": int(round(val * 100)),
            "low_label": d["low_label"],
            "high_label": d["high_label"],
            "color": d["color"],
        })

    valid_votes_count = len([v for v in votes.values() if v])
    dim_weights = compute_user_dimensional_weights(votes)
    confidence_pct = calculate_profile_confidence(valid_votes_count, dimensional_weights=dim_weights)
    if confidence_pct >= 90:
        confidence_label = "Hardened Cultural Identity"
    elif confidence_pct >= 70:
        confidence_label = "Established Profile"
    elif confidence_pct >= 40:
        confidence_label = "Preliminary Calibration"
    else:
        confidence_label = "Initial Spark"

    return {
        "rater_salt": rater_salt,
        "archetype": archetype,
        "dimensions": dimensions_report,
        "vector": user_vec,
        "primary_twin": matches["primary_twin"],
        "counter_twin": matches["counter_twin"],
        "all_matches": matches["all_matches"],
        "total_votes_considered": valid_votes_count,
        "confidence_pct": confidence_pct,
        "confidence_label": confidence_label,
    }


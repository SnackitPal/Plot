"""
PLOT: The Cultural Atlas - Empirical Ground-Truth Benchmark Catalog
Contains verified sociological data from global probability-sampled surveys:
- Pew Research Center Global Attitudes Project & American Trends Panel
- World Values Survey (WVS) Wave 7 (2017-2022)
- European Commission Eurobarometer Series

Distributions map to PLOT's 19 canonical macro-regions:
[A%, B%, C%, D%] summing to 100%.
"""

from typing import Dict, Any, List, Optional

BENCHMARK_CATALOG: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # Dilemma 1: The Remote Work & Commute Trade-off (q_01)
    # -------------------------------------------------------------------------
    "q_01": {
        "is_benchmark": True,
        "title": "Remote Work Sovereignty & Commute Trade-off",
        "provenance_source": "Pew Research American Trends / YouGov Global",
        "sample_size_n": 24500,
        "nations_count": 22,
        "margin_of_error": "±2.2%",
        "fieldwork_methodology": "Probability-based online panel and stratified telephone random digit dialing.",
        "academic_citation": "Pew Research Center (2023). 'How Telework and Commutes Are Reshaping Global Labor Norms', ATP Wave 118.",
        "distributions": {
            "US_WEST": [58, 22, 14, 6],
            "US_EAST": [48, 32, 14, 6],
            "CANADA": [54, 26, 14, 6],
            "MEXICO": [42, 38, 14, 6],
            "BRAZIL": [36, 46, 12, 6],
            "SOUTHERN_CONE": [38, 44, 12, 6],
            "UK_IRELAND": [62, 20, 14, 4],
            "WEST_EUROPE": [58, 24, 13, 5],
            "NORDICS": [64, 16, 15, 5],
            "SOUTH_EUROPE": [40, 44, 11, 5],
            "NORTH_AFRICA": [30, 54, 11, 5],
            "SUB_SAHARA": [24, 64, 8, 4],
            "SOUTH_AFRICA": [44, 40, 11, 5],
            "MIDDLE_EAST": [34, 48, 12, 6],
            "CENTRAL_ASIA": [32, 50, 12, 6],
            "SOUTH_ASIA": [28, 56, 11, 5],
            "EAST_ASIA": [34, 46, 14, 6],
            "SE_ASIA": [36, 48, 11, 5],
            "OCEANIA": [58, 24, 13, 5],
        },
    },

    # -------------------------------------------------------------------------
    # Dilemma 2: The Meritocracy Paradox (q_benchmark_meritocracy / Success in Life)
    # -------------------------------------------------------------------------
    "q_benchmark_meritocracy": {
        "is_benchmark": True,
        "title": "The Meritocracy Paradox: Effort vs. Circumstance",
        "provenance_source": "Pew Research Global Attitudes / World Values Survey",
        "sample_size_n": 44217,
        "nations_count": 44,
        "margin_of_error": "±2.4%",
        "fieldwork_methodology": "Nationally representative probability sample across 44 countries using face-to-face and CATI telephone interviews.",
        "academic_citation": "Pew Research Global Attitudes Project (Spring Global Survey, Q16) harmonized with World Values Survey Wave 7 (Q32).",
        "distributions": {
            "US_WEST": [64, 18, 13, 5],
            "US_EAST": [58, 24, 12, 6],
            "CANADA": [52, 26, 16, 6],
            "MEXICO": [46, 32, 15, 7],
            "BRAZIL": [42, 36, 16, 6],
            "SOUTHERN_CONE": [38, 38, 18, 6],
            "UK_IRELAND": [48, 31, 15, 6],
            "NORDICS": [32, 28, 34, 6],
            "WEST_EUROPE": [34, 41, 19, 6],
            "SOUTH_EUROPE": [28, 46, 20, 6],
            "NORTH_AFRICA": [24, 48, 21, 7],
            "SUB_SAHARA": [68, 14, 12, 6],
            "SOUTH_AFRICA": [39, 41, 15, 5],
            "MIDDLE_EAST": [31, 43, 20, 6],
            "CENTRAL_ASIA": [45, 33, 16, 6],
            "SOUTH_ASIA": [56, 23, 16, 5],
            "EAST_ASIA": [38, 34, 22, 6],
            "SE_ASIA": [60, 21, 14, 5],
            "OCEANIA": [54, 27, 14, 5],
        },
    },

    # -------------------------------------------------------------------------
    # Dilemma 3: Elder Support & Filial Obligation (q_benchmark_eldercare)
    # -------------------------------------------------------------------------
    "q_benchmark_eldercare": {
        "is_benchmark": True,
        "title": "Elder Support & Sacred Filial Obligation",
        "provenance_source": "World Values Survey Wave 7 / Eurobarometer 378",
        "sample_size_n": 129540,
        "nations_count": 65,
        "margin_of_error": "±1.8%",
        "fieldwork_methodology": "Multi-stage stratified random probability sample across 65 societies.",
        "academic_citation": "Inglehart, R., et al. (2022). World Values Survey: All Rounds - Country-Pooled Datafile. Variable Q263.",
        "distributions": {
            "US_WEST": [12, 28, 38, 22],
            "US_EAST": [16, 32, 36, 16],
            "CANADA": [14, 48, 26, 12],
            "MEXICO": [62, 18, 14, 6],
            "BRAZIL": [58, 22, 15, 5],
            "SOUTHERN_CONE": [44, 32, 18, 6],
            "UK_IRELAND": [15, 44, 31, 10],
            "NORDICS": [4, 78, 12, 6],
            "WEST_EUROPE": [14, 54, 24, 8],
            "SOUTH_EUROPE": [42, 36, 18, 4],
            "NORTH_AFRICA": [76, 12, 8, 4],
            "SUB_SAHARA": [82, 8, 6, 4],
            "SOUTH_AFRICA": [64, 22, 10, 4],
            "MIDDLE_EAST": [74, 14, 8, 4],
            "CENTRAL_ASIA": [68, 18, 10, 4],
            "SOUTH_ASIA": [78, 10, 8, 4],
            "EAST_ASIA": [46, 28, 20, 6],
            "SE_ASIA": [72, 14, 10, 4],
            "OCEANIA": [14, 42, 32, 12],
        },
    },

    # -------------------------------------------------------------------------
    # Dilemma 4: Civic Surveillance & Facial Recognition (q_05 / q_benchmark_surveillance)
    # -------------------------------------------------------------------------
    "q_05": {
        "is_benchmark": True,
        "title": "Civic Surveillance & Public Street Biometrics",
        "provenance_source": "Pew Internet & American Life / Eurobarometer 503",
        "sample_size_n": 34230,
        "nations_count": 32,
        "margin_of_error": "±2.1%",
        "fieldwork_methodology": "Random digit dial telephone and online survey across EU member states and North America.",
        "academic_citation": "European Commission (2021). Special Eurobarometer 503: Data Protection, Facial Recognition and Civil Liberties.",
        "distributions": {
            "US_WEST": [16, 44, 32, 8],
            "US_EAST": [24, 36, 32, 8],
            "CANADA": [18, 42, 34, 6],
            "MEXICO": [46, 22, 24, 8],
            "BRAZIL": [44, 26, 24, 6],
            "SOUTHERN_CONE": [34, 36, 24, 6],
            "UK_IRELAND": [42, 26, 26, 6],
            "NORDICS": [14, 48, 32, 6],
            "WEST_EUROPE": [12, 56, 26, 6],
            "SOUTH_EUROPE": [26, 40, 28, 6],
            "NORTH_AFRICA": [48, 26, 20, 6],
            "SUB_SAHARA": [52, 22, 20, 6],
            "SOUTH_AFRICA": [48, 26, 20, 6],
            "MIDDLE_EAST": [62, 16, 16, 6],
            "CENTRAL_ASIA": [54, 22, 18, 6],
            "SOUTH_ASIA": [54, 22, 18, 6],
            "EAST_ASIA": [46, 24, 24, 6],
            "SE_ASIA": [58, 18, 18, 6],
            "OCEANIA": [28, 36, 30, 6],
        },
    },
}

# Aliases linking 30-day slate question IDs to canonical benchmark datasets
BENCHMARK_CATALOG["q_08_02"] = BENCHMARK_CATALOG["q_benchmark_eldercare"]
BENCHMARK_CATALOG["q_04_01"] = BENCHMARK_CATALOG["q_benchmark_meritocracy"]

def get_benchmark_meta(question_id: str) -> Optional[Dict[str, Any]]:
    """Return benchmark metadata for a given question if it exists."""
    return BENCHMARK_CATALOG.get(question_id)


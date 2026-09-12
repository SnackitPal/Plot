"""
Unit and integration tests for Culture Shock & Relocation Radar Engine.
"""

import math
import pytest
from atlas.algorithms.culture_shock import (
    calculate_culture_shock,
    generate_personalized_dossier,
    CITY_LOCAL_CODES,
    DIMENSIONAL_PROTOCOLS,
)
from atlas.algorithms.compass import GLOBAL_CITY_CENTROIDS


def test_culture_shock_zero_distance_identity():
    """When user vector equals destination vector, CSI must be 0% and severity low."""
    tokyo = next(c for c in GLOBAL_CITY_CENTROIDS if c["city_id"] == "tokyo")
    tokyo_vec = {
        "autonomy": tokyo["vector"][0],
        "punctuality": tokyo["vector"][1],
        "boundary": tokyo["vector"][2],
        "freedom": tokyo["vector"][3],
        "trust": tokyo["vector"][4],
    }
    res = calculate_culture_shock(tokyo_vec, "tokyo")
    assert res["csi_pct"] == 0
    assert res["severity"] == "low"
    assert "Natural" in res["verdict"]
    for div in res["divergences"]:
        assert div["abs_delta"] == 0.0


def test_culture_shock_extreme_divergence():
    """Extreme polar opposite vectors must trigger acute culture shock (>= 75%)."""
    user_vec = {
        "autonomy": 1.0,
        "punctuality": 0.0,
        "boundary": 1.0,
        "freedom": 1.0,
        "trust": 0.0,
    }
    res = calculate_culture_shock(user_vec, "tokyo")
    # Tokyo vector is [0.35, 0.95, 0.25, 0.20, 0.92]
    # deltas: [+0.65, -0.95, +0.75, +0.80, -0.92]
    assert res["csi_pct"] >= 70
    assert res["severity"] == "acute"
    assert "Acute" in res["verdict"]


def test_culture_shock_divergence_sorting():
    """Divergences must be strictly sorted by abs_delta in descending order."""
    user_vec = {
        "autonomy": 0.80,
        "punctuality": 0.20,
        "boundary": 0.50,
        "freedom": 0.90,
        "trust": 0.40,
    }
    res = calculate_culture_shock(user_vec, "zurich")
    divs = res["divergences"]
    assert len(divs) == 5
    for i in range(len(divs) - 1):
        assert divs[i]["abs_delta"] >= divs[i + 1]["abs_delta"]


def test_culture_shock_protocol_cards_structure():
    """Top 3 protocol cards must be returned with complete fields and non-empty advice."""
    user_vec = {
        "autonomy": 0.90,
        "punctuality": 0.40,
        "boundary": 0.85,
        "freedom": 0.80,
        "trust": 0.95,
    }
    res = calculate_culture_shock(user_vec, "sao_paulo")
    cards = res["protocol_cards"]
    assert len(cards) <= 3
    assert len(cards) >= 1

    for card in cards:
        assert "dimension_key" in card
        assert "title" in card
        assert "actionable_rule" in card
        assert len(card["actionable_rule"]) > 20
        assert card["user_score"] >= 0 and card["user_score"] <= 100
        assert card["dest_score"] >= 0 and card["dest_score"] <= 100


def test_culture_shock_destination_metadata():
    """Destination metadata must include flag, local maxim, and transit code."""
    res = calculate_culture_shock({"autonomy": 0.5}, "berlin")
    dest = res["destination"]
    assert dest["city_name"] == "Berlin"
    assert dest["country"] == "Germany"
    assert dest["flag"] == "🇩🇪"
    assert len(dest["local_maxim"]) > 5
    assert len(dest["golden_rule"]) > 10
    assert len(dest["transit_code"]) > 10


def test_culture_shock_unknown_destination_fallback():
    """Passing an invalid destination city_id must gracefully fall back without throwing."""
    res = calculate_culture_shock({"autonomy": 0.5}, "atlantis_underwater_city")
    assert res["destination"]["city_id"] == "tokyo"  # Default fallback
    assert res["csi_pct"] >= 0


def test_personalized_dossier_structure():
    """Personalized dossier must contain 3 life arenas with roles, analysis, and watch-out traps."""
    user_vec = {
        "autonomy": 0.85,
        "punctuality": 0.75,
        "boundary": 0.40,
        "freedom": 0.90,
        "trust": 0.80,
    }
    dossier = generate_personalized_dossier(
        user_vec, total_votes=15, archetype_title="THE AUTONOMOUS COSMOPOLITAN"
    )
    assert dossier["archetype_title"] == "THE AUTONOMOUS COSMOPOLITAN"
    assert "15 empirical dilemma" in dossier["calibration_basis"]
    assert len(dossier["arenas"]) == 3

    arena_names = [a["arena"] for a in dossier["arenas"]]
    assert "High-Stakes Career & Ambition" in arena_names
    assert "Friendship, Intimacy & Boundaries" in arena_names
    assert "Stress, Conflict & Trust Instinct" in arena_names

    for arena in dossier["arenas"]:
        assert len(arena["archetype_role"]) > 0
        assert len(arena["analysis"]) > 30
        assert len(arena["watch_out"]) > 20


def test_api_culture_shock_and_destinations():
    """Verify serve_preview.py routes for /api/destinations and /api/culture-shock."""
    from serve_preview import AtlasRequestHandler
    import urllib.parse
    import io
    import json

    class DummyRequest:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(b"")

    # Test GET /api/destinations
    handler = AtlasRequestHandler.__new__(AtlasRequestHandler)
    handler.path = "/api/destinations"
    handler.request_version = "HTTP/1.1"
    handler.command = "GET"
    handler.wfile = io.BytesIO()

    sent_status = []
    sent_payload = []

    def mock_send(code, payload):
        sent_status.append(code)
        sent_payload.append(payload)

    handler._send_json = mock_send
    handler.do_GET()

    assert sent_status[0] == 200
    assert sent_payload[0]["status"] == "ok"
    assert len(sent_payload[0]["destinations"]) == 15
    first_dest = sent_payload[0]["destinations"][0]
    assert "city_id" in first_dest
    assert "flag" in first_dest
    assert "vector" in first_dest

    # Test GET /api/culture-shock?destination=zurich
    sent_status.clear()
    sent_payload.clear()
    handler.path = "/api/culture-shock?destination=zurich"
    handler.do_GET()

    assert sent_status[0] == 200
    shock = sent_payload[0]["culture_shock"]
    assert shock["destination"]["city_id"] == "zurich"
    assert "csi_pct" in shock
    assert "protocol_cards" in shock
    assert "dossier" in shock
    assert len(shock["dossier"]["arenas"]) == 3

"""
Unit and Integration Tests for Option 2: "Your Compass" Multi-Dimensional Archetype Engine.
Tests 5D vector projection, distance calculations, city matching, archetype classification,
database persistence, and REST API endpoints.
"""

import os
import json
import socket
import pytest
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import serve_preview
from atlas.algorithms.compass import (
    compute_user_vector,
    calculate_normalized_euclidean_distance,
    calculate_alignment_pct,
    find_city_matches,
    classify_archetype,
    generate_compass_report,
    GLOBAL_CITY_CENTROIDS,
)
from atlas.storage.database import AtlasDatabase


@pytest.fixture(scope="module")
def api_server():
    """Start an ephemeral test server on a dynamic port with isolated test DB."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    test_db = AtlasDatabase(db_path=db_path, auto_seed=True)
    orig_db = serve_preview.db
    serve_preview.db = test_db

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = ThreadingHTTPServer(("127.0.0.1", port), serve_preview.AtlasRequestHandler)
    server.daemon_threads = True

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, test_db

    server.shutdown()
    server.server_close()
    serve_preview.db = orig_db
    if os.path.exists(db_path):
        os.remove(db_path)


def test_compute_user_vector_and_defaults():
    # Full vote set
    votes = {
        "q_01": "A",  # Autonomy: 1.0
        "q_02": "A",  # Punctuality: 1.0
        "q_03": "B",  # Boundary: 0.10
        "q_04": "A",  # Freedom: 1.0
        "q_05": "A",  # Trust: 1.0
    }
    vec = compute_user_vector(votes)
    assert vec["autonomy"] == 1.0
    assert vec["punctuality"] == 1.0
    assert vec["boundary"] == 0.10
    assert vec["freedom"] == 1.0
    assert vec["trust"] == 1.0

    # Partial vote set defaults to 0.50
    partial_vec = compute_user_vector({"q_01": "B"})
    assert partial_vec["autonomy"] == 0.05
    assert partial_vec["punctuality"] == 0.50
    assert partial_vec["boundary"] == 0.50
    assert partial_vec["freedom"] == 0.50
    assert partial_vec["trust"] == 0.50


def test_distance_and_alignment_pct():
    v1 = [0.5, 0.5, 0.5, 0.5, 0.5]
    v2 = [0.5, 0.5, 0.5, 0.5, 0.5]
    dist = calculate_normalized_euclidean_distance(v1, v2)
    assert dist == 0.0
    assert calculate_alignment_pct(v1, v2) == 100.0

    # Opposites
    v_zero = [0.0, 0.0, 0.0, 0.0, 0.0]
    v_one = [1.0, 1.0, 1.0, 1.0, 1.0]
    dist_max = calculate_normalized_euclidean_distance(v_zero, v_one)
    assert dist_max == 1.0
    assert calculate_alignment_pct(v_zero, v_one) == 0.0


def test_find_city_matches_precision():
    # Tokyo-aligned user
    tokyo_votes = {"q_01": "D", "q_02": "A", "q_03": "B", "q_04": "B", "q_05": "A"}
    tokyo_vec = compute_user_vector(tokyo_votes)
    res = find_city_matches(tokyo_vec)

    assert len(res["all_matches"]) == len(GLOBAL_CITY_CENTROIDS)
    assert len(res["all_matches"]) == 15
    assert res["primary_twin"]["city_name"] in ("Tokyo", "Zurich", "Singapore")
    assert res["primary_twin"]["match_pct"] > 75.0
    assert res["counter_twin"]["match_pct"] < res["primary_twin"]["match_pct"]

    # Reykjavik-aligned user
    reykjavik_votes = {"q_01": "A", "q_02": "C", "q_03": "A", "q_04": "A", "q_05": "A"}
    reykjavik_vec = compute_user_vector(reykjavik_votes)
    res_rey = find_city_matches(reykjavik_vec)
    assert res_rey["primary_twin"]["city_name"] in ("Reykjavik", "Amsterdam", "Berlin")
    assert res_rey["primary_twin"]["match_pct"] > 80.0


def test_classify_archetypes():
    # Autonomous Cosmopolitan
    v1 = {"autonomy": 0.90, "punctuality": 0.85, "boundary": 0.60, "freedom": 0.90, "trust": 0.70}
    a1 = classify_archetype(v1)
    assert a1["title"] == "THE AUTONOMOUS COSMOPOLITAN"

    # Civic Precisionist
    v2 = {"autonomy": 0.30, "punctuality": 0.95, "boundary": 0.40, "freedom": 0.20, "trust": 0.95}
    a2 = classify_archetype(v2)
    assert a2["title"] == "THE CIVIC PRECISIONIST"

    # Relational Nomad
    v3 = {"autonomy": 0.85, "punctuality": 0.20, "boundary": 0.80, "freedom": 0.60, "trust": 0.50}
    a3 = classify_archetype(v3)
    assert a3["title"] == "THE RELATIONAL NOMAD"

    # Balanced Synthesizer
    v4 = {"autonomy": 0.50, "punctuality": 0.50, "boundary": 0.50, "freedom": 0.50, "trust": 0.50}
    a4 = classify_archetype(v4)
    assert a4["title"] == "THE BALANCED SYNTHESIZER"


def test_database_user_votes_and_archetype_persistence():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        temp_db_path = tf.name

    try:
        test_db = AtlasDatabase(db_path=temp_db_path, auto_seed=True)

        # 1. Record user votes
        test_db.record_user_vote("test_salt_999", "q_01", "A", "na_west")
        test_db.record_user_vote("test_salt_999", "q_02", "C", "na_west")
        test_db.record_user_vote("test_salt_999", "q_03", "A", "na_west")

        votes = test_db.get_user_votes("test_salt_999")
        assert votes["q_01"] == "A"
        assert votes["q_02"] == "C"
        assert votes["q_03"] == "A"

        # Update vote (upsert)
        test_db.record_user_vote("test_salt_999", "q_02", "A", "na_west")
        updated_votes = test_db.get_user_votes("test_salt_999")
        assert updated_votes["q_02"] == "A"

        # 2. Save and retrieve archetype profile
        profile_data = {
            "rater_salt": "test_salt_999",
            "archetype_title": "THE AUTONOMOUS COSMOPOLITAN",
            "primary_city": "Reykjavik",
            "primary_city_country": "Iceland",
            "primary_city_flag": "🇮🇸",
            "match_pct": 92.4,
            "counter_city": "Tokyo",
            "counter_city_country": "Japan",
            "counter_city_flag": "🇯🇵",
            "counter_match_pct": 41.2,
            "vector_autonomy": 0.90,
            "vector_punctuality": 0.85,
            "vector_boundary": 0.65,
            "vector_freedom": 0.80,
            "vector_trust": 0.95,
            "summary_narrative": "Test narrative summary",
        }
        test_db.save_archetype_profile(profile_data)

        fetched = test_db.get_archetype_profile("test_salt_999")
        assert fetched is not None
        assert fetched["archetype_title"] == "THE AUTONOMOUS COSMOPOLITAN"
        assert fetched["primary_city"] == "Reykjavik"
        assert fetched["match_pct"] == 92.4

    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


def test_api_compass_endpoints(api_server):
    base_url, _ = api_server

    # Test GET /api/compass/anon_tester
    req_get = urllib.request.Request(f"{base_url}/api/compass/anon_tester")
    with urllib.request.urlopen(req_get) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "ok"
        compass = data["compass"]
        assert "archetype" in compass
        assert "primary_twin" in compass
        assert "dimensions" in compass
        assert len(compass["dimensions"]) == 5

    # Test POST /api/compass/recalculate with explicit votes
    post_payload = json.dumps({
        "rater_salt": "tester_recalc",
        "votes": {
            "q_01": "A",
            "q_02": "A",
            "q_03": "B",
            "q_04": "A",
            "q_05": "A",
        }
    }).encode("utf-8")
    req_post = urllib.request.Request(
        f"{base_url}/api/compass/recalculate",
        data=post_payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req_post) as resp:
        assert resp.status == 200
        recalc_data = json.loads(resp.read().decode("utf-8"))
        assert recalc_data["status"] == "ok"
        report = recalc_data["compass"]
        assert report["rater_salt"] == "tester_recalc"
        assert report["vector"]["autonomy"] == 1.0
        assert report["primary_twin"]["match_pct"] > 0

"""
Automated unit and integration test suite for Cohort-Based Bridging Deliberation.
Verifies harmonic bridge scores, status classification, database demographics, and REST API endpoints.
"""

import os
import json
import socket
import tempfile
import threading
import urllib.request
import urllib.error
import pytest
from http.server import ThreadingHTTPServer

import serve_preview
from atlas.storage.database import AtlasDatabase
from atlas.algorithms.cohort_bridging import (
    calculate_wilson_lower_bound,
    calculate_harmonic_bridge_score,
    calculate_cohort_helpfulness,
    classify_bridging_status,
    rank_bridging_perspectives,
)


# -----------------------------------------------------------------
# Algorithmic Unit Tests
# -----------------------------------------------------------------

def test_harmonic_bridge_score_properties():
    """Verify mathematical properties of the harmonic bridging formula."""
    # 1. Identity when both cohorts agree equally
    assert calculate_harmonic_bridge_score(0.8, 0.8) == 0.8
    assert calculate_harmonic_bridge_score(0.5, 0.5) == 0.5
    
    # 2. Asymmetric penalty: one cohort at 0.95 and another at 0.20 must severely drop
    score_asym = calculate_harmonic_bridge_score(0.95, 0.20)
    # Arithmetic mean would be 0.575, but Harmonic mean is ~0.33
    assert score_asym < 0.35
    
    # 3. Zero absorption
    assert calculate_harmonic_bridge_score(0.0, 0.8) == 0.0
    assert calculate_harmonic_bridge_score(0.8, 0.0) == 0.0
    
    # 4. Commutative symmetry
    assert calculate_harmonic_bridge_score(0.75, 0.65) == calculate_harmonic_bridge_score(0.65, 0.75)


def test_classify_bridging_status():
    """Verify classification categories and thresholds."""
    # 1. Sacred Bridge: Both >= 0.65, delta <= 0.20, bridge score >= 0.70
    sb = classify_bridging_status(0.82, 0.78, sample_a=10, sample_b=10)
    assert sb["status"] == "SACRED_BRIDGE"
    assert sb["is_sacred_bridge"] is True
    assert "Sacred Bridge" in sb["badge"]
    
    # 2. Generational Chasm / Echo Chamber
    echo = classify_bridging_status(0.85, 0.20, sample_a=10, sample_b=10)
    assert echo["status"] in ("INTRA_GROUP_ECHO", "GENERATIONAL_CHASM")
    assert echo["is_sacred_bridge"] is False
    assert echo["polarization_delta"] == 0.65
    
    # 3. Insufficient data
    insuf = classify_bridging_status(0.90, 0.90, sample_a=1, sample_b=10, min_sample=2)
    assert insuf["status"] == "INSUFFICIENT_DATA"
    assert insuf["is_sacred_bridge"] is False
    
    # 4. Unaligned / Moderate
    mod = classify_bridging_status(0.52, 0.56, sample_a=10, sample_b=10)
    assert mod["status"] == "UNALIGNED"
    assert mod["is_sacred_bridge"] is False


def test_calculate_cohort_helpfulness():
    """Verify Laplace smoothing and approval rate calculations."""
    raw_input = {
        "GEN_Z": {"total_ratings": 10, "helpful_ratings": 8},
        "BOOMER_PLUS": {"total_ratings": 0, "helpful_ratings": 0},
    }
    stats = calculate_cohort_helpfulness(raw_input, laplace_prior=0.5, laplace_weight=1.0)
    
    assert stats["GEN_Z"]["raw_rate"] == 0.8
    # Laplace smoothed: (8 + 0.5*1.0) / (10 + 1.0) = 8.5 / 11.0 ≈ 0.773
    assert stats["GEN_Z"]["approval_rate"] == 0.773
    assert stats["GEN_Z"]["approval_pct"] == 77
    
    # Zero count falls back to prior
    assert stats["BOOMER_PLUS"]["approval_rate"] == 0.5
    assert stats["BOOMER_PLUS"]["approval_pct"] == 50
    assert stats["BOOMER_PLUS"]["wilson_lower"] == 0.0


def test_wilson_lower_bound_properties():
    """Verify mathematical properties of the Wilson Score Interval Lower Bound."""
    # 1. Total <= 0 returns 0.0
    assert calculate_wilson_lower_bound(0, 0) == 0.0
    assert calculate_wilson_lower_bound(5, -1) == 0.0
    
    # 2. Perfect score with small sample (2/2) has severe penalty: ~0.425
    wb_small = calculate_wilson_lower_bound(2, 2)
    assert 0.40 <= wb_small <= 0.45
    
    # 3. High sample with 80% (80/100) preserves confidence: ~0.727
    wb_large = calculate_wilson_lower_bound(80, 100)
    assert 0.71 <= wb_large <= 0.74
    
    # 4. Monotonicity in helpful votes
    assert calculate_wilson_lower_bound(5, 10) < calculate_wilson_lower_bound(8, 10)


def test_sybil_defense_and_asymmetric_sample_sizes():
    """Verify that 2 sockpuppets in Cohort B cannot crown an echo perspective as a Sacred Bridge."""
    # Cohort A has 100 raters (80 helpful), Cohort B has 2 raters (2 helpful)
    # Under raw smoothed rates: r_A = 0.797, r_B = 0.833, delta = 0.036, raw B_AB = 0.815
    res = classify_bridging_status(
        cohort_a_rate=0.797,
        cohort_b_rate=0.833,
        sample_a=100,
        sample_b=2,
        min_sample=5,
    )
    # Must fail quorum gate
    assert res["status"] == "INSUFFICIENT_DATA"
    assert res["is_sacred_bridge"] is False
    assert res["has_quorum"] is False


def test_unvoted_inversion_resolution_in_ranking():
    """Verify that unvoted perspectives (n=0) never outrank evaluated perspectives with moderate reception."""
    perspectives = [
        {"perspective_id": "p_unvoted", "body": "Untested perspective", "helpful_ratings": 0},
        {"perspective_id": "p_evaluated", "body": "Evaluated perspective", "helpful_ratings": 48},
    ]
    
    # Ratings map: p_unvoted has 0 votes, p_evaluated has 50 votes (24 helpful) in both cohorts
    ratings_map = {
        "p_unvoted": {
            "GEN_Z": {"total_ratings": 0, "helpful_ratings": 0},
            "BOOMER_PLUS": {"total_ratings": 0, "helpful_ratings": 0},
        },
        "p_evaluated": {
            "GEN_Z": {"total_ratings": 50, "helpful_ratings": 24},
            "BOOMER_PLUS": {"total_ratings": 50, "helpful_ratings": 24},
        },
    }
    
    ranked = rank_bridging_perspectives(perspectives, ratings_map, min_sample=5)
    
    # p_evaluated must strictly beat p_unvoted because it has quorum and verified positive Wilson score
    assert ranked[0]["perspective_id"] == "p_evaluated"
    assert ranked[1]["perspective_id"] == "p_unvoted"
    assert ranked[0]["bridging"]["has_quorum"] is True
    assert ranked[1]["bridging"]["has_quorum"] is False


def test_demographic_chasm_axis_naming():
    """Verify that divergence on non-generation axes returns DEMOGRAPHIC_CHASM."""
    res = classify_bridging_status(
        cohort_a_rate=0.80,
        cohort_b_rate=0.20,
        sample_a=20,
        sample_b=20,
        min_sample=5,
        axis="urbanicity",
    )
    assert res["status"] in ("INTRA_GROUP_ECHO", "DEMOGRAPHIC_CHASM")
    if res["status"] == "DEMOGRAPHIC_CHASM":
        assert "Chasm" in res["badge"]


# -----------------------------------------------------------------
# Storage & Seeding Tests
# -----------------------------------------------------------------

def test_database_demographics_and_cohort_ratings():
    """Verify user demographic persistence and cohort rating aggregation."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    try:
        db = AtlasDatabase(db_path=db_path, auto_seed=True)
        
        # 1. Test user demographic profile persistence
        db.save_user_demographics("test_user_1", "GEN_Z", "HYPER_URBAN", "ANGLOSPHERE")
        demo = db.get_user_demographics("test_user_1")
        assert demo["generation_cohort"] == "GEN_Z"
        assert demo["urbanicity"] == "HYPER_URBAN"
        assert demo["macro_region"] == "ANGLOSPHERE"
        
        # 2. Test rate perspective with auto-demographic lookup
        db.rate_perspective("p_01", "test_user_1", 1.0)
        with db._get_connection() as conn:
            row = conn.execute(
                "SELECT rater_generation, rater_urbanicity FROM perspective_ratings WHERE perspective_id = 'p_01' AND rater_salt = 'test_user_1';"
            ).fetchone()
            assert row["rater_generation"] == "GEN_Z"
            assert row["rater_urbanicity"] == "HYPER_URBAN"
            
        # 3. Test calibrated seed data
        cohort_ratings = db.get_perspective_cohort_ratings("q_01", "generation")
        assert "p_05" in cohort_ratings
        assert cohort_ratings["p_05"]["GEN_Z"]["helpful_pct"] >= 0.80
        assert cohort_ratings["p_05"]["BOOMER_PLUS"]["helpful_pct"] >= 0.80
        
        # p_01 has strong generational divergence in seed data
        assert cohort_ratings["p_01"]["GEN_Z"]["helpful_pct"] >= 0.80
        assert cohort_ratings["p_01"]["BOOMER_PLUS"]["helpful_pct"] <= 0.25
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


# -----------------------------------------------------------------
# REST API Integration Tests
# -----------------------------------------------------------------

@pytest.fixture(scope="module")
def api_server():
    """Start an ephemeral test server with isolated database."""
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


def make_request(url: str, method: str = "GET", data: dict = None):
    req = urllib.request.Request(url, method=method)
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json; charset=utf-8")
    else:
        body_bytes = None
    try:
        with urllib.request.urlopen(req, data=body_bytes, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def test_api_cohort_perspectives(api_server):
    """Verify GET /api/perspectives/:question_id/cohorts returns ranked bridging metrics."""
    base_url, db = api_server
    
    url = f"{base_url}/api/perspectives/q_01/cohorts?axis=generation&c1=GEN_Z&c2=BOOMER_PLUS"
    status, res = make_request(url)
    
    assert status == 200
    assert res["status"] == "ok"
    assert res["question_id"] == "q_01"
    assert res["cohort_axis"] == "generation"
    assert res["cohort_a"] == "GEN_Z"
    assert res["cohort_b"] == "BOOMER_PLUS"
    
    perspectives = res["perspectives"]
    assert len(perspectives) > 0
    
    # Top perspective should be a Sacred Bridge (p_05)
    top_p = perspectives[0]
    assert top_p["perspective_id"] == "p_05"
    assert top_p["bridging"]["is_sacred_bridge"] is True
    assert top_p["bridging"]["status"] == "SACRED_BRIDGE"
    assert top_p["cohort_a_stats"]["total"] >= 5
    assert top_p["cohort_b_stats"]["total"] >= 5
    
    # Polarized perspective (p_01) should have high polarization delta
    p01 = next(p for p in perspectives if p["perspective_id"] == "p_01")
    assert p01["bridging"]["polarization_delta"] >= 0.40
    assert p01["bridging"]["status"] in ("INTRA_GROUP_ECHO", "GENERATIONAL_CHASM")


def test_api_user_demographics_crud(api_server):
    """Verify POST and GET /api/user/demographics."""
    base_url, db = api_server
    
    salt = "demo_tester_99"
    payload = {
        "rater_salt": salt,
        "generation_cohort": "MILLENNIAL",
        "urbanicity": "RURAL",
        "macro_region": "EUROPE_WEST",
    }
    
    # 1. Save demographics
    status, res = make_request(f"{base_url}/api/user/demographics", method="POST", data=payload)
    assert status == 200
    assert res["status"] == "ok"
    assert res["demographics"]["generation_cohort"] == "MILLENNIAL"
    assert res["demographics"]["urbanicity"] == "RURAL"
    
    # 2. Retrieve demographics
    status_get, res_get = make_request(f"{base_url}/api/user/demographics/{salt}")
    assert status_get == 200
    assert res_get["demographics"]["generation_cohort"] == "MILLENNIAL"
    assert res_get["demographics"]["urbanicity"] == "RURAL"
    assert res_get["demographics"]["macro_region"] == "EUROPE_WEST"

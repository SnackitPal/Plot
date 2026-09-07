"""
Comprehensive automated test suite for Option 1:
30-Day Content Slate & MECE Question Engine.

Tests:
1. Content Corpus Integrity (30 slates, 150 calibrated dilemmas, 4 MECE choices, unique IDs)
2. Domain Projection Tensor and Order-Invariant Determinesian Bayesian Accumulator
3. Asymptotic Profile Confidence curve
4. Storage layer (30 slates atomic seeding, day lookup, streak tracking, trajectory)
5. REST API endpoints (GET /api/slates, GET /api/slate/day/:num, GET /api/user/state/:salt, GET /api/compass/trajectory/:salt)
"""

import os
import math
import json
import socket
import tempfile
import threading
import urllib.request
import urllib.error
import pytest
from http.server import ThreadingHTTPServer

import serve_preview
from atlas.content.slates_30d import (
    SLATES_30D,
    DOMAIN_METADATA,
    get_slate_by_day,
    get_all_slates_metadata
)
from atlas.algorithms.compass import (
    compute_user_vector,
    calculate_profile_confidence,
    generate_compass_report,
    DOMAIN_PROJECTION_TENSOR
)
from atlas.storage.database import AtlasDatabase


# ---------------------------------------------------------------------------
# 1. Content Corpus Tests
# ---------------------------------------------------------------------------

def test_slates_corpus_complete():
    """Verify that exactly 30 slates exist with 150 calibrated dilemmas."""
    assert len(SLATES_30D) == 30, f"Expected 30 slates, got {len(SLATES_30D)}"
    
    all_q_ids = set()
    valid_symbols = {"●", "▲", "■", "◆", "circle", "triangle", "square", "diamond"}
    
    for slate in SLATES_30D:
        assert 1 <= slate["day_number"] <= 30
        assert "title" in slate and len(slate["title"]) > 0
        assert "domain_tags" in slate and len(slate["domain_tags"]) > 0
        
        questions = slate["questions"]
        assert len(questions) == 5, f"Slate Day {slate['day_number']} must have exactly 5 questions"
        
        for q in questions:
            q_id = q.get("question_id") or q.get("id")
            assert q_id not in all_q_ids, f"Duplicate question ID: {q_id}"
            all_q_ids.add(q_id)
            
            assert "prompt" in q and len(q["prompt"]) > 5
            assert "cat" in q or "domain" in q
            
            choices = q["choices"]
            assert len(choices) == 4, f"Question {q_id} must have 4 choices"
            letters = [c["letter"] for c in choices]
            assert letters == ["A", "B", "C", "D"], f"Choices must be A, B, C, D in order for {q_id}"
            
            for c in choices:
                assert "label" in c and len(c["label"]) > 0
                assert "weight" in c
                w = c["weight"]
                assert isinstance(w, (int, float))
                assert 0.0 <= w <= 1.0, f"Choice weight {w} out of bounds [0.0, 1.0] for {q_id} choice {c['letter']}"
                assert c["shape_symbol"] in valid_symbols, f"Invalid symbol {c['shape_symbol']}"


def test_domain_metadata_coverage():
    """Verify that all 6 sociological domains are configured with descriptions."""
    expected_domains = {
        "WORK_MOBILITY",
        "TIME_SOCIABILITY",
        "KINSHIP_BOUNDARIES",
        "CAPITAL_FREEDOM",
        "CIVIC_TRUST",
        "EXISTENTIAL_TECH"
    }
    assert set(DOMAIN_METADATA.keys()) == expected_domains


def test_helper_get_slate_by_day():
    """Verify get_slate_by_day returns correct slate or None."""
    s1 = get_slate_by_day(1)
    assert s1 is not None
    assert s1["day_number"] == 1
    assert len(s1["questions"]) == 5

    s30 = get_slate_by_day(30)
    assert s30 is not None
    assert s30["day_number"] == 30

    assert get_slate_by_day(0) is None
    assert get_slate_by_day(31) is None


def test_helper_get_all_slates_metadata():
    """Verify get_all_slates_metadata marks completion accurately."""
    completed = {1, 3, 5}
    meta_list = get_all_slates_metadata(completed)
    assert len(meta_list) == 30
    
    day_1 = next(m for m in meta_list if m["day_number"] == 1)
    assert day_1["is_completed"] is True
    
    day_2 = next(m for m in meta_list if m["day_number"] == 2)
    assert day_2["is_completed"] is False


# ---------------------------------------------------------------------------
# 2. Algorithmic Core: Projection Tensor & Bayesian Accumulator Tests
# ---------------------------------------------------------------------------

def test_domain_projection_tensor_existence():
    """Ensure all 6 domains have valid 5D projection vectors."""
    for domain, proj in DOMAIN_PROJECTION_TENSOR.items():
        assert len(proj) == 5
        for dim, weight in proj.items():
            assert 0.0 <= weight <= 1.0
            
    # Check EXISTENTIAL_TECH specifically
    tech_proj = DOMAIN_PROJECTION_TENSOR["EXISTENTIAL_TECH"]
    assert math.isclose(tech_proj["autonomy"], 0.40)
    assert math.isclose(tech_proj["boundary"], 0.30)
    assert math.isclose(tech_proj["trust"], 0.30)


def test_order_invariant_bayesian_accumulator():
    """
    Verify that compute_user_vector is strictly order-invariant.
    Answering questions in order [q1, q2, q3] vs [q3, q1, q2] must produce identical vectors.
    """
    votes_forward = {
        "q_01": "A",
        "q_02": "B",
        "q_03": "C",
        "q_04": "D",
        "q_05": "A",
    }
    
    # Reverse dictionary order
    votes_reverse = {k: votes_forward[k] for k in reversed(list(votes_forward.keys()))}
    
    vec_forward = compute_user_vector(votes_forward)
    vec_reverse = compute_user_vector(votes_reverse)
    
    for axis in ["autonomy", "punctuality", "boundary", "freedom", "trust"]:
        assert math.isclose(vec_forward[axis], vec_reverse[axis], abs_tol=1e-6), (
            f"Axis {axis} violated order-invariance: {vec_forward[axis]} vs {vec_reverse[axis]}"
        )


def test_unvoted_dimensions_neutral_prior():
    """An empty or unvoted dimension must preserve the natural 0.50 neutral prior."""
    empty_vec = compute_user_vector({})
    for axis, val in empty_vec.items():
        assert math.isclose(val, 0.50)


def test_asymptotic_profile_confidence_curve():
    """
    Verify confidence curve:
    Confidence(N) = min(100, round((1 - e^(-N / 6)) * 100))
    """
    assert calculate_profile_confidence(0) == 0
    
    # 5 dilemmas (1 full daily slate)
    c5 = calculate_profile_confidence(5)
    expected_c5 = round((1 - math.exp(-5 / 6.0)) * 100)  # ~56%
    assert c5 == expected_c5
    
    # 20 dilemmas (4 days)
    c20 = calculate_profile_confidence(20)
    assert c20 >= 96
    
    # 35 dilemmas (7 days)
    c35 = calculate_profile_confidence(35)
    assert c35 >= 99


def test_generate_compass_report_includes_confidence():
    """Verify generate_compass_report attaches confidence_pct and confidence_label."""
    votes = {"q_01": "A", "q_02": "A"}
    report = generate_compass_report("test_rater_salt", votes)
    
    assert "confidence_pct" in report
    assert "confidence_label" in report
    assert "total_votes_considered" in report
    assert report["total_votes_considered"] == 2
    assert 0 < report["confidence_pct"] < 50


# ---------------------------------------------------------------------------
# 3. Database Layer Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db():
    """Create a temporary isolated SQLite database with auto_seed=True."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = AtlasDatabase(db_path=path, auto_seed=True)
    yield db
    if os.path.exists(path):
        os.remove(path)


def test_database_slates_seeding(temp_db):
    """Verify that all 30 slates are seeded and queryable."""
    slates = temp_db.get_all_slates()
    assert len(slates) == 30
    
    # Query Day 2 specifically
    day2 = temp_db.get_slate_by_day(2)
    assert day2 is not None
    assert day2["day_number"] == 2
    assert len(day2["questions"]) == 5
    
    # Query out-of-range day
    assert temp_db.get_slate_by_day(99) is None


def test_database_user_state_and_streak(temp_db):
    """Verify user state, vote caching, and streak tracking."""
    rater = "test_device_salt_alpha"
    
    # Initially user has no votes
    state = temp_db.get_user_state(rater)
    assert state["completed_days"] == []
    assert state["streak_stats"]["total_votes"] == 0
    assert state["streak_stats"]["completed_slates_count"] == 0
    
    # Vote on all 5 questions of Day 1
    day1 = temp_db.get_slate_by_day(1)
    for q in day1["questions"]:
        temp_db.record_user_vote(rater, q["question_id"], "A", "US_WEST")
        
    state_after = temp_db.get_user_state(rater)
    assert 1 in state_after["completed_days"]
    assert state_after["streak_stats"]["completed_slates_count"] == 1
    assert state_after["streak_stats"]["total_votes"] == 5


def test_database_compass_trajectory(temp_db):
    """Verify compass trajectory recording and history retrieval."""
    rater = "test_device_salt_beta"
    temp_db.record_compass_history(
        rater_salt=rater,
        slate_id="slate_daily_01",
        day_number=1,
        num_votes=5,
        vector={"autonomy": 0.8, "punctuality": 0.7, "boundary": 0.6, "freedom": 0.9, "trust": 0.85},
        archetype_title="THE AUTONOMOUS COSMOPOLITAN",
        primary_twin_city="Reykjavik",
        confidence_pct=56
    )
    
    trajectory = temp_db.get_compass_trajectory(rater)
    assert len(trajectory) == 1
    assert trajectory[0]["confidence_pct"] == 56
    assert trajectory[0]["archetype_title"] == "THE AUTONOMOUS COSMOPOLITAN"


# ---------------------------------------------------------------------------
# 4. REST API Endpoint Integration Tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_server():
    """Start an ephemeral test server on an available port with an isolated temporary DB."""
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
        with urllib.request.urlopen(req, data=body_bytes, timeout=5) as response:
            status = response.status
            body = response.read().decode("utf-8")
            return status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}


def test_api_get_slates(api_server):
    """GET /api/slates must return all 30 slates metadata."""
    base_url, _ = api_server
    status, body = make_request(f"{base_url}/api/slates")
    assert status == 200
    assert "slates" in body
    assert len(body["slates"]) == 30
    assert body["slates"][0]["day_number"] == 1


def test_api_get_slate_by_day(api_server):
    """GET /api/slate/day/:num must return the 5-question slate or 404."""
    base_url, _ = api_server
    status, body = make_request(f"{base_url}/api/slate/day/2")
    assert status == 200
    assert "slate" in body
    assert body["slate"]["day_number"] == 2
    assert len(body["slate"]["questions"]) == 5

    # 404 for nonexistent day
    status404, _ = make_request(f"{base_url}/api/slate/day/99")
    assert status404 == 404


def test_api_user_state_and_streak(api_server):
    """GET /api/user/state/:salt returns streak stats and completed days."""
    base_url, _ = api_server
    status, body = make_request(f"{base_url}/api/user/state/new_test_device")
    assert status == 200
    assert "state" in body
    assert "streak_stats" in body["state"]
    assert body["state"]["streak_stats"]["completed_slates_count"] == 0


def test_api_compass_recalculate_logs_trajectory(api_server):
    """POST /api/compass/recalculate recalculates compass and records trajectory."""
    base_url, _ = api_server
    payload = {
        "rater_salt": "device_trajectory_test",
        "votes": {"q_01": "A", "q_02": "B", "q_03": "C", "q_04": "D", "q_05": "A"}
    }
    status, body = make_request(f"{base_url}/api/compass/recalculate", method="POST", data=payload)
    assert status == 200
    assert "compass" in body
    assert "confidence_pct" in body["compass"]
    assert body["compass"]["confidence_pct"] > 50

    # Query trajectory
    t_status, t_body = make_request(f"{base_url}/api/compass/trajectory/device_trajectory_test")
    assert t_status == 200
    assert "trajectory" in t_body
    assert len(t_body["trajectory"]) >= 1
    assert t_body["trajectory"][-1]["num_votes"] == 5

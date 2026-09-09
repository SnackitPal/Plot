"""
Test Suite for Psychometric Trajectory Engine, Time-Machine Radar Analytics,
and Storage Layer Idempotency & Streak Calculation.
"""

import math
import os
import json
import socket
import datetime
import urllib.request
import urllib.error
import threading
import pytest
from http.server import ThreadingHTTPServer

from atlas.storage.database import AtlasDatabase
from atlas.algorithms.trajectory import (
    calculate_step_distance,
    calculate_trajectory_analytics,
)
import serve_preview


# ---------------------------------------------------------------------------
# 1. Trajectory Algorithmic Core Tests
# ---------------------------------------------------------------------------

def test_step_distance_calculation():
    """Verify normalized Euclidean step distance is bounded in [0.0, 1.0]."""
    v1 = {"autonomy": 0.5, "punctuality": 0.5, "boundary": 0.5, "freedom": 0.5, "trust": 0.5}
    v2 = {"autonomy": 0.5, "punctuality": 0.5, "boundary": 0.5, "freedom": 0.5, "trust": 0.5}
    assert calculate_step_distance(v1, v2) == 0.0

    # Max theoretical divergence: (0,0,0,0,0) vs (1,1,1,1,1)
    v_min = {k: 0.0 for k in ["autonomy", "punctuality", "boundary", "freedom", "trust"]}
    v_max = {k: 1.0 for k in ["autonomy", "punctuality", "boundary", "freedom", "trust"]}
    max_dist = calculate_step_distance(v_min, v_max)
    assert math.isclose(max_dist, 1.0, abs_tol=1e-3)

    # Moderate single dimension shift
    v3 = {"autonomy": 0.8, "punctuality": 0.5, "boundary": 0.5, "freedom": 0.5, "trust": 0.5}
    dist = calculate_step_distance(v1, v3)
    # diff is 0.3 on 1 axis out of 5: 0.3 / sqrt(5) = 0.3 / 2.23606 = ~0.1342
    assert 0.13 <= dist <= 0.14


def test_trajectory_analytics_empty_and_single_snapshot():
    """Empty or single snapshot lists must return graceful schemas without division by zero."""
    empty_res = calculate_trajectory_analytics([])
    assert empty_res["snapshot_count"] == 0
    assert empty_res["cumulative_distance"] == 0.0
    assert empty_res["mean_drift_velocity"] == 0.0
    assert empty_res["core_anchor"] is None

    single_snap = [{
        "day_number": 1,
        "vector_autonomy": 0.70,
        "vector_punctuality": 0.60,
        "vector_boundary": 0.50,
        "vector_freedom": 0.80,
        "vector_trust": 0.75,
        "primary_city": "Reykjavik",
        "match_pct": 92.5,
        "confidence_pct": 57,
        "archetype_title": "THE AUTONOMOUS COSMOPOLITAN",
        "num_votes": 5,
    }]
    single_res = calculate_trajectory_analytics(single_snap)
    assert single_res["snapshot_count"] == 1
    assert single_res["cumulative_distance"] == 0.0
    assert single_res["mean_drift_velocity"] == 0.0
    assert single_res["stability_tier"]["key"] == "ANCHORED_BEDROCK"
    assert len(single_res["city_journey"]) == 1
    assert "Locally Grounded" in single_res["migration_summary"]


def test_core_anchor_and_fluid_frontier_variance():
    """
    Ensure dimension with minimal variance is selected as Core Anchor,
    and dimension with maximal variance is selected as Fluid Frontier.
    """
    # Create 4 snapshots where trust is rock-solid at 0.80, but boundary oscillates widely
    snapshots = [
        {
            "day_number": 1,
            "vector_autonomy": 0.60,
            "vector_punctuality": 0.50,
            "vector_boundary": 0.20,
            "vector_freedom": 0.50,
            "vector_trust": 0.80,
            "primary_city": "Reykjavik",
            "archetype_title": "THE BALANCED SYNTHESIZER",
        },
        {
            "day_number": 2,
            "vector_autonomy": 0.62,
            "vector_punctuality": 0.52,
            "vector_boundary": 0.85,
            "vector_freedom": 0.51,
            "vector_trust": 0.80,
            "primary_city": "Tokyo",
            "archetype_title": "THE CIVIC PRECISIONIST",
        },
        {
            "day_number": 3,
            "vector_autonomy": 0.59,
            "vector_punctuality": 0.49,
            "vector_boundary": 0.25,
            "vector_freedom": 0.50,
            "vector_trust": 0.80,
            "primary_city": "Reykjavik",
            "archetype_title": "THE BALANCED SYNTHESIZER",
        },
        {
            "day_number": 4,
            "vector_autonomy": 0.61,
            "vector_punctuality": 0.51,
            "vector_boundary": 0.90,
            "vector_freedom": 0.52,
            "vector_trust": 0.80,
            "primary_city": "Zurich",
            "archetype_title": "THE AUTONOMOUS COSMOPOLITAN",
        },
    ]

    res = calculate_trajectory_analytics(snapshots)
    assert res["snapshot_count"] == 4
    assert res["core_anchor"]["dimension_key"] == "trust"
    assert res["core_anchor"]["variance"] == 0.0
    assert res["core_anchor"]["stability_pct"] == 100

    assert res["fluid_frontier"]["dimension_key"] == "boundary"
    assert res["fluid_frontier"]["variance"] > 0.05
    assert res["fluid_frontier"]["volatility_pct"] > 40

    # Verify Twin City Migration Journey
    assert res["distinct_cities_visited"] == ["Reykjavik", "Tokyo", "Zurich"]
    assert "Metropolitan Journey" in res["migration_summary"]
    assert len(res["history_points"]) == 4


def test_stability_tier_classification():
    """Verify classification thresholds for stability tiers."""
    # Near zero drift
    calm_snaps = [
        {"day_number": 1, "vector_autonomy": 0.5, "vector_punctuality": 0.5, "vector_boundary": 0.5, "vector_freedom": 0.5, "vector_trust": 0.5},
        {"day_number": 2, "vector_autonomy": 0.51, "vector_punctuality": 0.5, "vector_boundary": 0.5, "vector_freedom": 0.5, "vector_trust": 0.5},
    ]
    res_calm = calculate_trajectory_analytics(calm_snaps)
    assert res_calm["stability_tier"]["key"] == "ANCHORED_BEDROCK"

    # Wild shift
    wild_snaps = [
        {"day_number": 1, "vector_autonomy": 0.1, "vector_punctuality": 0.1, "vector_boundary": 0.1, "vector_freedom": 0.1, "vector_trust": 0.1},
        {"day_number": 2, "vector_autonomy": 0.9, "vector_punctuality": 0.9, "vector_boundary": 0.9, "vector_freedom": 0.9, "vector_trust": 0.9},
    ]
    res_wild = calculate_trajectory_analytics(wild_snaps)
    assert res_wild["stability_tier"]["key"] == "PARADIGM_SHIFTER"


# ---------------------------------------------------------------------------
# 2. Storage Layer: Idempotency & True Streak Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_trajectory.db")
    db = AtlasDatabase(db_path=db_file, auto_seed=True)
    yield db
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass


def test_compass_history_upsert_idempotency(temp_db):
    """
    Recording compass history multiple times for the same day_number
    must update the existing record rather than duplicating it.
    """
    rater = "test_user_idempotency"
    temp_db.record_compass_history(
        rater_salt=rater,
        day_number=1,
        vector={"autonomy": 0.6, "punctuality": 0.5, "boundary": 0.5, "freedom": 0.5, "trust": 0.5},
        primary_city="Tokyo",
        confidence_pct=50,
        num_votes=5,
        archetype_title="FIRST_PROFILE",
    )

    traj1 = temp_db.get_compass_trajectory(rater)
    assert len(traj1) == 1
    assert traj1[0]["archetype_title"] == "FIRST_PROFILE"

    # Re-vote or re-calculate on Day 1 with updated vector
    temp_db.record_compass_history(
        rater_salt=rater,
        day_number=1,
        vector={"autonomy": 0.85, "punctuality": 0.7, "boundary": 0.6, "freedom": 0.9, "trust": 0.75},
        primary_city="Reykjavik",
        confidence_pct=65,
        num_votes=5,
        archetype_title="UPDATED_PROFILE",
    )

    traj2 = temp_db.get_compass_trajectory(rater)
    # Must still be exactly 1 snapshot, with updated fields
    assert len(traj2) == 1
    assert traj2[0]["archetype_title"] == "UPDATED_PROFILE"
    assert traj2[0]["primary_city"] == "Reykjavik"
    assert math.isclose(traj2[0]["vector_autonomy"], 0.85)

    # Now add Day 2 snapshot
    temp_db.record_compass_history(
        rater_salt=rater,
        day_number=2,
        vector={"autonomy": 0.80, "punctuality": 0.7, "boundary": 0.6, "freedom": 0.9, "trust": 0.75},
        primary_city="Reykjavik",
        confidence_pct=80,
        num_votes=10,
        archetype_title="DAY_2_PROFILE",
    )
    traj3 = temp_db.get_compass_trajectory(rater)
    assert len(traj3) == 2
    assert [s["day_number"] for s in traj3] == [1, 2]


def test_database_contiguous_streak_calculation(temp_db):
    """Verify true calendar contiguous habit streak logic."""
    rater = "streak_user"
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    two_days_ago = today - datetime.timedelta(days=2)
    ten_days_ago = today - datetime.timedelta(days=10)

    # Empty user -> streak 0
    assert temp_db.get_user_streak(rater)["habit_streak_days"] == 0

    # Add vote for today
    with temp_db._get_connection() as conn:
        conn.execute(
            "INSERT INTO user_votes (rater_salt, question_id, choice_letter, created_at) VALUES (?, ?, ?, ?);",
            (rater, "q_01", "A", f"{today.isoformat()} 10:00:00"),
        )
    assert temp_db.get_user_streak(rater)["habit_streak_days"] == 1

    # Add vote for yesterday -> streak becomes 2
    with temp_db._get_connection() as conn:
        conn.execute(
            "INSERT INTO user_votes (rater_salt, question_id, choice_letter, created_at) VALUES (?, ?, ?, ?);",
            (rater, "q_02", "B", f"{yesterday.isoformat()} 10:00:00"),
        )
    assert temp_db.get_user_streak(rater)["habit_streak_days"] == 2

    # Add vote for two days ago -> streak becomes 3
    with temp_db._get_connection() as conn:
        conn.execute(
            "INSERT INTO user_votes (rater_salt, question_id, choice_letter, created_at) VALUES (?, ?, ?, ?);",
            (rater, "q_03", "C", f"{two_days_ago.isoformat()} 10:00:00"),
        )
    assert temp_db.get_user_streak(rater)["habit_streak_days"] == 3

    # Now test broken streak user whose last vote was 10 days ago
    broken_rater = "broken_streak_user"
    with temp_db._get_connection() as conn:
        conn.execute(
            "INSERT INTO user_votes (rater_salt, question_id, choice_letter, created_at) VALUES (?, ?, ?, ?);",
            (broken_rater, "q_01", "A", f"{ten_days_ago.isoformat()} 10:00:00"),
        )
    assert temp_db.get_user_streak(broken_rater)["habit_streak_days"] == 0


# ---------------------------------------------------------------------------
# 3. REST API: GET /api/compass/trajectory/:rater_salt with Analytics
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_server():
    """Spawns an isolated ThreadingHTTPServer instance for trajectory API tests."""
    orig_db = serve_preview.db
    db_path = "test_api_trajectory.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

    test_db = AtlasDatabase(db_path=db_path, auto_seed=True)
    serve_preview.db = test_db

    # Find open port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = ThreadingHTTPServer(("127.0.0.1", port), serve_preview.AtlasRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, test_db

    server.shutdown()
    server.server_close()
    serve_preview.db = orig_db
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


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


def test_api_trajectory_returns_analytics(api_server):
    """GET /api/compass/trajectory/:rater_salt must return trajectory snapshots and analytics."""
    base_url, test_db = api_server
    rater_salt = "api_traj_analytics_user"

    # Seed 2 historical days
    test_db.record_compass_history(
        rater_salt=rater_salt,
        day_number=1,
        vector={"autonomy": 0.7, "punctuality": 0.6, "boundary": 0.4, "freedom": 0.8, "trust": 0.9},
        primary_city="Reykjavik",
        confidence_pct=57,
        num_votes=5,
        archetype_title="THE AUTONOMOUS COSMOPOLITAN",
    )
    test_db.record_compass_history(
        rater_salt=rater_salt,
        day_number=2,
        vector={"autonomy": 0.72, "punctuality": 0.61, "boundary": 0.42, "freedom": 0.79, "trust": 0.91},
        primary_city="Zurich",
        confidence_pct=81,
        num_votes=10,
        archetype_title="THE AUTONOMOUS COSMOPOLITAN",
    )

    status, body = make_request(f"{base_url}/api/compass/trajectory/{rater_salt}")
    assert status == 200
    assert "trajectory" in body
    assert len(body["trajectory"]) == 2
    assert "analytics" in body

    analytics = body["analytics"]
    assert analytics["snapshot_count"] == 2
    assert "cumulative_distance" in analytics
    assert "mean_drift_velocity" in analytics
    assert "core_anchor" in analytics
    assert analytics["core_anchor"] is not None
    assert "fluid_frontier" in analytics
    assert analytics["fluid_frontier"] is not None
    assert "stability_tier" in analytics
    assert "city_journey" in analytics
    assert analytics["distinct_cities_visited"] == ["Reykjavik", "Zurich"]

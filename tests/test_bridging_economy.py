"""
Automated unit and integration test suite for the Strategy-Proof Bridging Economy & Epistemic Reputation System.
Tests:
- Weighted continuous Wilson score intervals with cross-cohort stance weighting.
- Dyadic harmonic effective sample size and brigading defense.
- Bridging b-index, square-root rank decay, and reputation tiers.
- Peer prediction karma deltas, epistemic humility dividend, and CCI weighting.
- Database reputation ledger and review deck methods.
- REST API endpoints and Rawlsian Veil of Ignorance enforcement.
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
from atlas.algorithms.bridging_economy import (
    calculate_weighted_wilson_lower,
    calculate_perspective_bridging_capital,
    calculate_author_bridging_score,
    calculate_rater_karma_delta,
    PerspectiveRatingInput,
    BridgingYieldResult,
    AuthorReputationResult,
)


# -----------------------------------------------------------------
# 1. Algorithmic Unit Tests: Weighted Wilson Interval
# -----------------------------------------------------------------

def test_weighted_wilson_empty_and_bounds():
    """Verify empty input returns safe zero bound and effective sample size."""
    lower, n_eff = calculate_weighted_wilson_lower([], "A")
    assert lower == 0.0
    assert n_eff == 0.0


def test_weighted_wilson_sample_size_monotonicity():
    """Verify that lower bound increases monotonically with sample size for high utility."""
    # 5 ratings vs 50 ratings of HELPFUL_BRIDGE
    r_small = [
        PerspectiveRatingInput(rater_salt=f"r_{i}", rater_cohort="GEN_Z", rater_stance="B", rating_category="HELPFUL_BRIDGE")
        for i in range(5)
    ]
    r_large = [
        PerspectiveRatingInput(rater_salt=f"r_{i}", rater_cohort="GEN_Z", rater_stance="B", rating_category="HELPFUL_BRIDGE")
        for i in range(50)
    ]
    lower_small, n_small = calculate_weighted_wilson_lower(r_small, "A")
    lower_large, n_large = calculate_weighted_wilson_lower(r_large, "A")
    assert 0.0 < lower_small < lower_large <= 1.0
    assert n_small < n_large


def test_weighted_wilson_cross_cohort_stance_weighting():
    """
    Verify cross-cohort counter-stance weighting (1.60x) versus in-group weighting (0.65x).
    Counter-stance endorsements yield higher utility than in-group cheerleading with the same raw counts.
    """
    # 3 HELPFUL (counter-stance, weight 1.60) + 2 UNHELPFUL (in-group, weight 0.65)
    r_counter = [
        PerspectiveRatingInput(rater_salt=f"r_pos_{i}", rater_cohort="GEN_Z", rater_stance="B", rating_category="HELPFUL_BRIDGE")
        for i in range(3)
    ] + [
        PerspectiveRatingInput(rater_salt=f"r_neg_{i}", rater_cohort="GEN_Z", rater_stance="A", rating_category="UNHELPFUL")
        for i in range(2)
    ]

    # 3 HELPFUL (in-group, weight 0.65) + 2 UNHELPFUL (counter-stance, weight 1.60)
    r_ingroup = [
        PerspectiveRatingInput(rater_salt=f"r_pos_{i}", rater_cohort="GEN_Z", rater_stance="A", rating_category="HELPFUL_BRIDGE")
        for i in range(3)
    ] + [
        PerspectiveRatingInput(rater_salt=f"r_neg_{i}", rater_cohort="GEN_Z", rater_stance="B", rating_category="UNHELPFUL")
        for i in range(2)
    ]

    lower_counter, _ = calculate_weighted_wilson_lower(r_counter, "A")
    lower_ingroup, _ = calculate_weighted_wilson_lower(r_ingroup, "A")
    assert lower_counter > lower_ingroup


# -----------------------------------------------------------------
# 2. Algorithmic Unit Tests: Perspective Bridging Capital & Brigading Defense
# -----------------------------------------------------------------

def test_perspective_bridging_capital_brigading_defense():
    """
    Verify Dyadic Harmonic Sample Size defends against single-cohort brigading.
    When Cohort A has 100 votes but Cohort B has only 2 (< min_quorum 5), quorum fails.
    """
    r_a = [
        PerspectiveRatingInput(rater_salt=f"a_{i}", rater_cohort="GEN_Z", rater_stance="A", rating_category="HELPFUL_BRIDGE")
        for i in range(100)
    ]
    r_b = [
        PerspectiveRatingInput(rater_salt=f"b_{i}", rater_cohort="BOOMER_PLUS", rater_stance="B", rating_category="HELPFUL_BRIDGE")
        for i in range(2)
    ]
    res = calculate_perspective_bridging_capital(
        perspective_id="p_test_brigade",
        perspective_stance="A",
        ratings_cohort_a=r_a,
        ratings_cohort_b=r_b,
        min_quorum=5,
    )
    assert res.has_quorum is False
    assert res.bc_yield == 0.0


def test_perspective_bridging_capital_balanced_quorum_pass():
    """Verify balanced cohorts pass the quorum gate and produce high bridging capital."""
    r_a = [
        PerspectiveRatingInput(rater_salt=f"a_{i}", rater_cohort="GEN_Z", rater_stance="B", rating_category="HELPFUL_BRIDGE")
        for i in range(20)
    ]
    r_b = [
        PerspectiveRatingInput(rater_salt=f"b_{i}", rater_cohort="BOOMER_PLUS", rater_stance="B", rating_category="HELPFUL_BRIDGE")
        for i in range(20)
    ]
    res = calculate_perspective_bridging_capital(
        perspective_id="p_test_balanced",
        perspective_stance="A",
        ratings_cohort_a=r_a,
        ratings_cohort_b=r_b,
        min_quorum=5,
    )
    assert res.has_quorum is True
    assert res.bc_yield > 15.0
    assert res.effective_sample_size >= 10.0


def test_perspective_bridging_capital_polarization_damping():
    """Verify deep polarization delta strongly damps bridging capital."""
    # Cohort A strongly likes (all HELPFUL_BRIDGE)
    r_a = [
        PerspectiveRatingInput(rater_salt=f"a_{i}", rater_cohort="GEN_Z", rater_stance="B", rating_category="HELPFUL_BRIDGE")
        for i in range(25)
    ]
    # Cohort B dislikes (all UNHELPFUL)
    r_b = [
        PerspectiveRatingInput(rater_salt=f"b_{i}", rater_cohort="BOOMER_PLUS", rater_stance="B", rating_category="UNHELPFUL")
        for i in range(25)
    ]
    res = calculate_perspective_bridging_capital(
        perspective_id="p_test_polarized",
        perspective_stance="A",
        ratings_cohort_a=r_a,
        ratings_cohort_b=r_b,
        min_quorum=5,
    )
    assert res.polarization_delta >= 0.35
    assert res.bc_yield == 0.0


# -----------------------------------------------------------------
# 3. Algorithmic Unit Tests: Author Bridging Score & b-Index
# -----------------------------------------------------------------

def test_author_bridging_b_index_calculation():
    """
    Verify Bridging b-index: b items with BC >= 15 * b.
    b=1: 1 item >= 15.
    b=2: 2 items >= 30.
    b=3: 3 items >= 45.
    """
    # 2 items >= 30, 3rd is 25 (not >= 45) -> b-index = 2
    items = [
        {"bc_yield": 50.0, "age_days": 1.0, "is_echo": False},
        {"bc_yield": 35.0, "age_days": 2.0, "is_echo": False},
        {"bc_yield": 25.0, "age_days": 3.0, "is_echo": False},
        {"bc_yield": 5.0, "age_days": 4.0, "is_echo": False},
    ]
    rep = calculate_author_bridging_score(items)
    assert rep.bridging_b_index == 2
    assert rep.active_abs > 0.0


def test_author_reputation_tiers():
    """Verify reputation tier transitions based on score and b-index."""
    # High score items
    high_items = [
        {"bc_yield": 95.0, "age_days": 0.5, "is_echo": False},
        {"bc_yield": 90.0, "age_days": 1.0, "is_echo": False},
        {"bc_yield": 85.0, "age_days": 1.5, "is_echo": False},
        {"bc_yield": 80.0, "age_days": 2.0, "is_echo": False},
        {"bc_yield": 75.0, "age_days": 2.5, "is_echo": False},
    ]
    rep = calculate_author_bridging_score(high_items)
    assert rep.reputation_tier in ("CULTURAL_DIPLOMAT", "SACRED_ARBITER", "CONSENSUS_BUILDER")

    # Citizen Deliberator for empty or low scores
    low_rep = calculate_author_bridging_score([])
    assert low_rep.reputation_tier == "CITIZEN_DELIBERATOR"
    assert low_rep.bridging_b_index == 0


def test_author_lifetime_peak_preservation():
    """Verify lifetime peak score preserves guarantee."""
    old_peak = 120.0
    items = [{"bc_yield": 10.0, "age_days": 10.0, "is_echo": False}]
    rep = calculate_author_bridging_score(items, lifetime_peak_abs=old_peak)
    assert rep.lifetime_peak_abs >= old_peak


# -----------------------------------------------------------------
# 4. Algorithmic Unit Tests: Peer Prediction Karma Deltas
# -----------------------------------------------------------------

def test_rater_karma_epistemic_humility_dividend():
    """Verify endorsing a counter-attitudinal perspective awards +2.0 humility dividend."""
    delta_counter = calculate_rater_karma_delta(
        rating_category="HELPFUL_BRIDGE",
        rater_stance="A",
        perspective_stance="B",
        cohort_a_lower=0.75,
        cohort_b_lower=0.75,
        rater_cci=750,
    )
    delta_same = calculate_rater_karma_delta(
        rating_category="HELPFUL_BRIDGE",
        rater_stance="A",
        perspective_stance="A",
        cohort_a_lower=0.75,
        cohort_b_lower=0.75,
        rater_cci=750,
    )
    # Counter-stance endorsement must exceed same-stance endorsement
    assert delta_counter > delta_same + 1.5


def test_rater_karma_cci_multiplier():
    """Verify high Cultural Calibration Index (CCI) scales karma rewards."""
    delta_high_cci = calculate_rater_karma_delta(
        rating_category="HELPFUL_BRIDGE",
        rater_stance="A",
        perspective_stance="B",
        cohort_a_lower=0.70,
        cohort_b_lower=0.70,
        rater_cci=950,
    )
    delta_low_cci = calculate_rater_karma_delta(
        rating_category="HELPFUL_BRIDGE",
        rater_stance="A",
        perspective_stance="B",
        cohort_a_lower=0.70,
        cohort_b_lower=0.70,
        rater_cci=100,
    )
    assert delta_high_cci > delta_low_cci


# -----------------------------------------------------------------
# 5. Database Integration Tests
# -----------------------------------------------------------------

def test_database_bridging_economy_workflow():
    """Verify schema migrations, user reputation, review deck, and deck item rating."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        db = AtlasDatabase(db_path=db_path, auto_seed=True)

        # 1. Check user reputation retrieval
        rep = db.get_user_reputation("new_user_123")
        assert rep["rater_salt"] == "new_user_123"
        assert rep["reputation_tier"] == "CITIZEN_DELIBERATOR"
        assert rep["calibration_karma"] == 0.0

        # 2. Check review deck retrieval
        deck = db.get_review_deck(
            question_id="q_01",
            viewer_salt="test_viewer_salt",
            viewer_generation="GEN_Z",
            limit=3,
        )
        assert len(deck) > 0
        assert "perspective_id" in deck[0]
        assert "karma_reward" in deck[0]

        # 3. Rate a deck item
        target_pid = deck[0]["perspective_id"]
        rate_res = db.rate_deck_item(
            perspective_id=target_pid,
            rater_salt="test_viewer_salt",
            rating_category="HELPFUL_BRIDGE",
            rater_generation="GEN_Z",
            rater_urbanicity="URBAN",
        )
        assert rate_res["status"] == "ok"
        assert rate_res["karma_awarded"] > 0.0
        assert rate_res["total_karma"] > 0.0

        # Verify rater reputation updated
        updated_rater_rep = db.get_user_reputation("test_viewer_salt")
        assert updated_rater_rep["calibration_karma"] > 0.0

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


# -----------------------------------------------------------------
# 6. REST API Integration Tests (including Rawlsian Veil of Ignorance)
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
    req.add_header("Content-Type", "application/json")
    body = json.dumps(data).encode("utf-8") if data else None
    with urllib.request.urlopen(req, data=body, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_api_user_reputation_endpoint(api_server):
    base_url, _ = api_server
    url = f"{base_url}/api/user/reputation/test_salt_api_456"
    status, res = make_request(url)
    assert status == 200
    assert res["status"] == "ok"
    assert "reputation" in res
    assert res["reputation"]["reputation_tier"] == "CITIZEN_DELIBERATOR"


def test_api_review_deck_endpoint(api_server):
    base_url, _ = api_server
    url = f"{base_url}/api/perspectives/q_01/review_deck?rater_salt=api_user_99&cohort_val=GEN_Z&limit=2"
    status, res = make_request(url)
    assert status == 200
    assert res["status"] == "ok"
    assert "review_deck" in res
    assert len(res["review_deck"]) <= 2


def test_api_rate_deck_endpoint(api_server):
    base_url, _ = api_server
    deck_url = f"{base_url}/api/perspectives/q_01/review_deck?rater_salt=api_rater_deck"
    _, deck_res = make_request(deck_url)
    assert len(deck_res["review_deck"]) > 0
    pid = deck_res["review_deck"][0]["perspective_id"]

    rate_url = f"{base_url}/api/perspectives/rate_deck"
    payload = {
        "perspective_id": pid,
        "rater_salt": "api_rater_deck",
        "rating_category": "HELPFUL_BRIDGE",
        "rater_generation": "GEN_Z",
        "rater_urbanicity": "URBAN",
    }
    status, rate_res = make_request(rate_url, method="POST", data=payload)
    assert status == 200
    assert rate_res["status"] == "ok"
    assert rate_res["karma_awarded"] > 0.0
    assert rate_res["total_karma"] > 0.0


def test_api_rawlsian_veil_of_ignorance(api_server):
    """
    Verify Rawlsian Veil of Ignorance:
    - Perspectives without bridge quorum have is_veiled = True and tier = 'CALIBRATING'.
    - Validated SACRED_BRIDGE perspectives have is_veiled = False and display author insignia.
    """
    base_url, _ = api_server
    url = f"{base_url}/api/perspectives/q_01/cohorts?axis=generation&c1=GEN_Z&c2=BOOMER_PLUS"
    status, res = make_request(url)
    assert status == 200
    perspectives = res["perspectives"]
    assert len(perspectives) > 0

    for p in perspectives:
        assert "is_veiled" in p
        assert "author_reputation_tier" in p
        assert "author_tier_insignia" in p
        if p["is_veiled"]:
            assert p["author_reputation_tier"] == "CALIBRATING"
            assert "Veil Active" in p["author_tier_insignia"]

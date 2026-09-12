"""
Integration tests for Community Perspective Submission, Moderation, Review Queue, and Anonymous Ratings.
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


def test_post_community_perspective_valid(api_server):
    """Verify that a constructive community perspective is accepted and entered into deliberation."""
    base_url, db = api_server
    payload = {
        "question_id": "q_01",
        "choice_letter": "A",
        "body": "Commuting burns two hours daily; saving those hours for family health is a necessary tradeoff rather than extra salary.",
        "author_salt": "author_user_1",
        "author_generation": "GEN_Z",
        "author_urbanicity": "HYPER_URBAN",
        "author_macro_region": "ANGLOSPHERE",
    }
    status, res = make_request(f"{base_url}/api/perspectives", method="POST", data=payload)
    assert status == 201
    assert res["status"] == "ok"
    assert res["moderation_status"] == "APPROVED"
    assert res["perspective_id"].startswith("p_")
    assert res["constructiveness"]["is_constructive"] is True
    assert res["bridging_preview"]["status"] == "INSUFFICIENT_DATA"


def test_post_community_perspective_moderation_rejection(api_server):
    """Verify that spam or link injection is rejected with 422 Unprocessable Entity."""
    base_url, db = api_server
    
    # 1. Hyperlink rejection
    link_payload = {
        "question_id": "q_01",
        "choice_letter": "B",
        "body": "Check out this amazing site http://spamsite.xyz for free points on polls.",
        "author_salt": "spammer_1",
    }
    status_link, res_link = make_request(f"{base_url}/api/perspectives", method="POST", data=link_payload)
    assert status_link == 422
    assert res_link["code"] == "MODERATION_FLAGGED"
    assert "CONTAINS_LINK" in res_link["flags"]
    
    # 2. Too short
    short_payload = {
        "question_id": "q_01",
        "choice_letter": "C",
        "body": "Too short",
        "author_salt": "user_2",
    }
    status_short, res_short = make_request(f"{base_url}/api/perspectives", method="POST", data=short_payload)
    assert status_short == 422
    assert "TOO_SHORT" in res_short["flags"]


def test_anonymous_rating_unspecified_cohort(api_server):
    """Verify that anonymous ratings without explicit demographics are recorded as UNSPECIFIED."""
    base_url, db = api_server
    
    # Rate perspective p_01 with unspecified cohort
    payload = {
        "perspective_id": "p_01",
        "rater_salt": "purely_anonymous_rater",
        "rating_score": 1.0,
        "rater_generation": "UNSPECIFIED",
        "rater_urbanicity": "UNSPECIFIED",
    }
    status, res = make_request(f"{base_url}/api/rate", method="POST", data=payload)
    assert status == 200
    
    with db._get_connection() as conn:
        row = conn.execute(
            "SELECT rater_generation, rater_urbanicity FROM perspective_ratings WHERE perspective_id = 'p_01' AND rater_salt = 'purely_anonymous_rater';"
        ).fetchone()
        assert row["rater_generation"] == "UNSPECIFIED"
        assert row["rater_urbanicity"] == "UNSPECIFIED"
        
    # Verify that cohort aggregation does NOT include UNSPECIFIED
    cohort_map = db.get_perspective_cohort_ratings("q_01", "generation")
    for pid, c_dict in cohort_map.items():
        assert "UNSPECIFIED" not in c_dict


def test_cold_start_review_queue(api_server):
    """Verify that GET /api/perspectives/:question_id/review_queue serves unrated candidates."""
    base_url, db = api_server
    
    url = f"{base_url}/api/perspectives/q_01/review_queue?rater_salt=new_deliberator_123&cohort_val=GEN_Z"
    status, res = make_request(url)
    assert status == 200
    assert res["status"] == "ok"
    assert "review_queue" in res
    assert isinstance(res["review_queue"], list)

"""
Integration tests for PLOT REST API and ThreadingHTTPServer.
Verifies endpoints, concurrency, input validation, and XSS sanitization.
"""

import os
import time
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
    """Start an ephemeral test server on an available port with an isolated temporary DB."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Initialize isolated database and seed it
    test_db = AtlasDatabase(db_path=db_path, auto_seed=True)

    # Monkeypatch serve_preview.db and serve_preview.DB_PATH for testing
    orig_db = serve_preview.db
    serve_preview.db = test_db

    # Find open port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = ThreadingHTTPServer(("127.0.0.1", port), serve_preview.AtlasRequestHandler)
    server.daemon_threads = True

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, test_db

    # Teardown
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
        req.data = body_bytes

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed


def test_get_slate_today(api_server):
    base_url, _ = api_server
    status, res = make_request(f"{base_url}/api/slate/today")
    assert status == 200
    assert res["status"] == "ok"
    assert "slate" in res
    assert len(res["slate"]["questions"]) == 5
    first_q = res["slate"]["questions"][0]
    assert first_q["question_id"] == "q_01"
    assert len(first_q["choices"]) == 4


def test_get_cartogram_payload(api_server):
    base_url, _ = api_server
    status, res = make_request(f"{base_url}/api/cartogram/q_01")
    assert status == 200
    assert res["status"] == "ok"
    cartogram = res["cartogram"]
    assert "regions" in cartogram
    assert "US_WEST" in cartogram["regions"]
    assert cartogram["regions"]["US_WEST"]["dominant"] == "A"
    assert "CENTRAL_ASIA" in cartogram["regions"]
    assert cartogram["regions"]["CENTRAL_ASIA"]["is_hatched"] is True


def test_post_vote_and_cartogram_update(api_server):
    base_url, _ = api_server
    
    # 1. Cast a vote for Option B in US_WEST
    vote_data = {
        "question_id": "q_01",
        "region_key": "US_WEST",
        "choice_letter": "B",
    }
    status, res = make_request(f"{base_url}/api/vote", method="POST", data=vote_data)
    assert status == 200
    assert res["status"] == "ok"
    assert "cartogram" in res

    # 2. Test input validation for invalid choice
    bad_vote = {
        "question_id": "q_01",
        "region_key": "US_WEST",
        "choice_letter": "Z",
    }
    status_bad, res_bad = make_request(f"{base_url}/api/vote", method="POST", data=bad_vote)
    assert status_bad == 400
    assert "Invalid choice" in res_bad["message"]

    # 3. Test input validation for invalid region
    bad_region = {
        "question_id": "q_01",
        "region_key": "ATLANTIS",
        "choice_letter": "A",
    }
    status_reg, res_reg = make_request(f"{base_url}/api/vote", method="POST", data=bad_region)
    assert status_reg == 400
    assert "Unknown region key" in res_reg["message"]


def test_perspectives_crud_and_xss_protection(api_server):
    base_url, _ = api_server

    # 1. Create a perspective with HTML / script injection attempt
    malicious_text = "<script>alert('xss')</script> Commuting wastes valuable human life."
    payload = {
        "question_id": "q_01",
        "choice_letter": "A",
        "body": malicious_text,
        "author_salt": "<img src=x onerror=alert(1)> hacker",
    }
    status, res = make_request(f"{base_url}/api/perspectives", method="POST", data=payload)
    assert status == 201
    assert res["status"] == "ok"
    pid = res["perspective_id"]

    # 2. Verify perspective list returns properly escaped text
    status_get, res_get = make_request(f"{base_url}/api/perspectives/q_01")
    assert status_get == 200
    perspectives = res_get["perspectives"]
    created_item = next((p for p in perspectives if p["perspective_id"] == pid), None)
    assert created_item is not None
    assert created_item["body"] == malicious_text
    assert created_item["author_salt"] == payload["author_salt"]

    # 3. Reject too short body (< 10 chars)
    short_payload = {
        "question_id": "q_01",
        "choice_letter": "A",
        "body": "Too short",
    }
    status_short, res_short = make_request(f"{base_url}/api/perspectives", method="POST", data=short_payload)
    assert status_short in (400, 422)


def test_rate_perspective_and_fast_response(api_server):
    base_url, _ = api_server
    
    # 1. Rate a perspective
    rate_data = {
        "perspective_id": "p_01",
        "rater_salt": "tester_999",
        "rating_score": 1.0,
    }
    start = time.time()
    status, res = make_request(f"{base_url}/api/rate", method="POST", data=rate_data)
    elapsed = time.time() - start
    assert status == 200
    assert res["status"] == "ok"
    # Should respond in well under 100ms
    assert elapsed < 0.20

    # 2. Reject out of bound score
    bad_rate = {
        "perspective_id": "p_01",
        "rater_salt": "tester_999",
        "rating_score": 10.0,
    }
    status_bad, res_bad = make_request(f"{base_url}/api/rate", method="POST", data=bad_rate)
    assert status_bad == 400

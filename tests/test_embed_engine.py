"""
Unit and Integration Tests for Phase 2: Embeddable Dilemma Card Engine.
Verifies /embed, /embed.js, framing headers, CORS, query routing, and stance tabs.
"""

import pytest
import os
import urllib.request
import urllib.parse
import json
import threading
import time
from http.server import ThreadingHTTPServer

from atlas.storage.database import AtlasDatabase
from serve_preview import AtlasRequestHandler, ROOT_DIR, PREVIEW_DIR


@pytest.fixture(scope="module")
def embed_test_server():
    """Spin up a local AtlasRequestHandler server on an ephemeral port for testing."""
    test_db_path = os.path.join(ROOT_DIR, "test_embed.db")
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

    # Bind to ephemeral port
    server = ThreadingHTTPServer(("127.0.0.1", 0), AtlasRequestHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.3)
    yield base_url

    server.shutdown()
    server.server_close()
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass


def test_embed_js_delivery(embed_test_server):
    """Verify /embed.js returns 200 with javascript Content-Type and auto-resize logic."""
    url = f"{embed_test_server}/embed.js"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "application/javascript" in content_type
        body = resp.read().decode("utf-8")
        assert "plot:resize" in body
        assert "addEventListener('message'" in body


def test_embed_html_delivery_and_framing_headers(embed_test_server):
    """Verify /embed returns 200, Content-Security-Policy allows framing (frame-ancestors *), and contains embed DOM."""
    url = f"{embed_test_server}/embed?id=q_01&theme=parchment"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "text/html" in content_type

        # Verify CSP frame-ancestors is permissive for third-party embeds
        csp = resp.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors *" in csp

        # Verify CORS allow origin
        cors = resp.headers.get("Access-Control-Allow-Origin", "")
        assert cors == "*"

        body = resp.read().decode("utf-8")
        assert 'id="embed-container"' in body
        assert 'id="question-prompt"' in body
        assert 'id="choices-container"' in body
        assert 'id="stance-tabs-strip"' in body
        assert 'plot:resize' in body


def test_embed_path_routing_aliases(embed_test_server):
    """Verify path-based routing /embed/q_01 and /preview/embed.html."""
    for path in ["/embed/q_01", "/preview/embed.html", "/embed"]:
        url = f"{embed_test_server}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")


def test_embed_cartogram_and_stance_api_integration(embed_test_server):
    """Verify /api/cartogram and /api/perspectives endpoints return valid data for the embed card."""
    # 1. Fetch cartogram for dilemma
    q_url = f"{embed_test_server}/api/cartogram/q_01"
    with urllib.request.urlopen(q_url) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "question" in data
        assert data["question"]["question_id"] == "q_01"
        assert len(data["question"]["choices"]) == 4

    # 2. Fetch stance-first perspectives for dilemma
    p_url = f"{embed_test_server}/api/perspectives/q_01/by_stance"
    with urllib.request.urlopen(p_url) as resp:
        assert resp.status == 200
        p_data = json.loads(resp.read().decode("utf-8"))
        assert "perspectives_by_stance" in p_data
        assert "A" in p_data["perspectives_by_stance"]
        assert "B" in p_data["perspectives_by_stance"]

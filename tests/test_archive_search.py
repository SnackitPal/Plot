"""
Integration tests for the Atlas Archive Search and Discovery Engine API.
Verifies keyword searching, category filtering, benchmark filters, and pagination.
"""

import os
import json
import socket
import tempfile
import threading
import urllib.request
import urllib.parse
import pytest
from http.server import ThreadingHTTPServer

import serve_preview
from atlas.storage.database import AtlasDatabase


@pytest.fixture(scope="module")
def search_test_server():
    """Start an ephemeral test server on an open port with an isolated temporary DB."""
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


def fetch_json(url: str):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_archive_search_all(search_test_server):
    base_url, _ = search_test_server
    url = f"{base_url}/api/archive/search?limit=150"
    data = fetch_json(url)

    assert data["status"] == "ok"
    assert data["total"] == 150
    assert len(data["results"]) == 150
    sample = data["results"][0]
    assert "question_id" in sample or "id" in sample
    assert "prompt" in sample
    assert "choices" in sample
    assert "category" in sample
    assert "day_number" in sample


def test_archive_search_keyword_filter(search_test_server):
    base_url, _ = search_test_server
    url = f"{base_url}/api/archive/search?q=commute"
    data = fetch_json(url)

    assert data["status"] == "ok"
    assert data["total"] >= 1
    top = data["results"][0]
    assert "commute" in top["prompt"].lower() or "commute" in str(top["choices"]).lower()
    assert top["score"] > 0


def test_archive_search_category_filter(search_test_server):
    base_url, _ = search_test_server
    url = f"{base_url}/api/archive/search?category=WORK_MOBILITY&limit=50"
    data = fetch_json(url)

    assert data["status"] == "ok"
    assert data["total"] > 0
    for item in data["results"]:
        assert item["category"] == "WORK_MOBILITY"


def test_archive_search_benchmark_filter(search_test_server):
    base_url, _ = search_test_server
    url = f"{base_url}/api/archive/search?benchmark_only=true"
    data = fetch_json(url)

    assert data["status"] == "ok"
    assert data["total"] >= 4
    for item in data["results"]:
        assert item["is_benchmark"] is True
        assert "provenance_source" in item
        assert "sample_size_n" in item

"""
Tests for Phase 3: Chrome SidePanel Extension & Ambient Discussion Scraper.
Verifies Manifest V3 compliance, URL canonicalization, draft synthesis,
static route delivery, and full ambient deliberation lifecycle.
"""

import json
import os
import socket
import tempfile
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
import pytest

from atlas.storage.database import AtlasDatabase
import serve_preview

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENSION_DIR = os.path.join(ROOT_DIR, "extension")


@pytest.fixture
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


def make_request(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    if data is not None:
        data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body
            return status, parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return e.code, parsed


def test_manifest_schema_and_mv3_compliance():
    """Verify manifest.json matches Chrome MV3 specification and all referenced assets exist."""
    manifest_path = os.path.join(EXTENSION_DIR, "manifest.json")
    assert os.path.exists(manifest_path), "manifest.json must exist in extension directory"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Core MV3 requirements
    assert manifest.get("manifest_version") == 3, "Must be Manifest V3"
    assert manifest.get("name") == "PLOT: Cultural Atlas & Ambient Deliberation"
    assert "version" in manifest

    # Permissions
    perms = set(manifest.get("permissions", []))
    assert "sidePanel" in perms, "sidePanel permission required"
    assert "activeTab" in perms, "activeTab permission required"
    assert "storage" in perms, "storage permission required"

    # SidePanel declaration
    assert "side_panel" in manifest, "side_panel declaration required in MV3"
    assert manifest["side_panel"].get("default_path") == "sidepanel.html"

    # Background service worker
    assert "background" in manifest
    assert manifest["background"].get("service_worker") == "background.js"

    # Verify all referenced local files actually exist
    expected_files = [
        "background.js",
        "content.js",
        "sidepanel.html",
        "sidepanel.js",
        "sidepanel.css",
        "icon.svg",
    ]
    for fn in expected_files:
        fp = os.path.join(EXTENSION_DIR, fn)
        assert os.path.exists(fp), f"Referenced extension asset {fn} must exist on disk"


def test_canonical_url_normalization_and_hash():
    """Verify that compute_canonical_hash normalizes tracking parameters and URL variants."""
    from serve_preview import compute_canonical_hash

    # 1. Strip tracking params (utm_source, ref, fbclid)
    dirty_url = "https://reddit.com/r/AskEurope/comments/xyz123/quiet_hours?utm_source=twitter&ref=share&fbclid=abc"
    clean_url, h1 = compute_canonical_hash(dirty_url)
    assert "utm_source" not in clean_url
    assert "ref" not in clean_url
    assert "fbclid" not in clean_url
    assert clean_url == "https://reddit.com/r/askeurope/comments/xyz123"

    # 2. Preserve YouTube v= parameter while stripping tracking params
    dirty_yt = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=share&utm_medium=email"
    clean_yt, h2 = compute_canonical_hash(dirty_yt)
    assert "v=dQw4w9WgXcQ" in clean_yt
    assert "feature" not in clean_yt
    assert "utm_medium" not in clean_yt

    # 3. Hash determinism
    _, h3 = compute_canonical_hash("https://reddit.com/r/askeurope/comments/xyz123")
    assert h1 == h3, "Normalized URLs must produce identical SHA-256 hashes"


def test_extract_dilemma_draft_platforms(api_server):
    """Verify that extract_dilemma_draft recognizes platforms and synthesizes 4 MECE choices."""
    from serve_preview import extract_dilemma_draft

    # Reddit Platform
    r_draft = extract_dilemma_draft(
        url="https://reddit.com/r/AskEurope/comments/test1",
        title="Should quiet hours be mandatory after 10 PM?",
        text_excerpt="Discussions on neighbor noise versus personal freedom"
    )
    assert r_draft["platform"] == "REDDIT"
    assert r_draft["category"] == "COMMUNITY"
    assert len(r_draft["choices"]) == 4
    assert r_draft["choices"][0]["letter"] == "A"
    assert "seed_rationale" in r_draft

    # YouTube Platform
    yt_draft = extract_dilemma_draft(
        url="https://youtube.com/watch?v=video123",
        title="Civil Disobedience and Digital Free Speech"
    )
    assert yt_draft["platform"] == "YOUTUBE"
    assert yt_draft["category"] == "DIGITAL_COMMONS"
    assert len(yt_draft["choices"]) == 4

    # Work & Mobility
    work_draft = extract_dilemma_draft(
        url="https://news.ycombinator.com/item?id=123",
        title="Salary vs Remote Work Flexibility",
        text_excerpt="Debating compensation cuts for remote workers"
    )
    assert work_draft["category"] == "WORK_MOBILITY"
    assert len(work_draft["choices"]) == 4


def test_extension_file_delivery_routes(api_server):
    """Verify that serve_preview.py correctly serves extension assets and test workbench."""
    base_url, _ = api_server

    # Manifest delivery
    m_code, m_data = make_request(f"{base_url}/extension/manifest.json")
    assert m_code == 200
    assert m_data.get("manifest_version") == 3

    # Sidepanel HTML delivery
    sp_code, sp_data = make_request(f"{base_url}/extension/sidepanel.html")
    assert sp_code == 200
    assert "<!DOCTYPE html>" in sp_data
    assert "Deliberation SidePanel" in sp_data

    # Sidepanel JS delivery
    js_code, js_data = make_request(f"{base_url}/extension/sidepanel.js")
    assert js_code == 200
    assert "__PLOT_SIDEPANEL" in js_data

    # Sidepanel CSS delivery
    css_code, css_data = make_request(f"{base_url}/extension/sidepanel.css")
    assert css_code == 200
    assert "--paper" in css_data

    # Workbench test page delivery
    wb_code, wb_data = make_request(f"{base_url}/preview/extension_test.html")
    assert wb_code == 200
    assert "PLOT Chrome Extension Test Workbench" in wb_data


def test_full_ambient_deliberation_lifecycle(api_server):
    """Verify end-to-end lifecycle: lookup -> draft extraction -> custom plot publish -> vote & ratify."""
    base_url, _ = api_server
    test_url = "https://reddit.com/r/AskEurope/comments/phase3_lifecycle_test"

    # Step 1: Lookup should return exists: False initially
    l1_code, l1_data = make_request(f"{base_url}/api/plots/lookup?url={urllib.parse.quote(test_url)}")
    assert l1_code == 200
    assert l1_data["exists"] is False
    assert "url_hash" in l1_data

    # Step 2: 1-Tap AI Draft extraction
    d_code, d_data = make_request(
        f"{base_url}/api/plots/extract-draft",
        method="POST",
        data={
            "url": test_url,
            "title": "Urban Quiet Hours vs Cultural Vitality",
            "text_excerpt": "Neighbors debate quiet laws vs late night street vibrancy."
        }
    )
    assert d_code == 200
    draft = d_data["draft"]
    assert draft["platform"] == "REDDIT"
    assert len(draft["choices"]) == 4

    # Step 3: Publish the custom plot from the side panel
    p_code, p_data = make_request(
        f"{base_url}/api/plots/create",
        method="POST",
        data={
            "title": draft["title"],
            "prompt": draft["prompt"],
            "category": draft["category"],
            "choices": draft["choices"],
            "canonical_url": draft["canonical_url"],
            "url_hash": draft["url_hash"],
            "author_salt": "@founding_tester",
            "author_vote": "A",
            "author_rationale": "Sovereignty over sleep is an essential physiological right.",
            "author_moral_lens": "AUTONOMY",
            "author_macro_region": "NORDICS"
        }
    )
    assert p_code == 201
    qid = p_data["question"]["question_id"]
    assert qid.startswith("q_custom_")

    # Step 4: Lookup should now return exists: True with full question
    l2_code, l2_data = make_request(f"{base_url}/api/plots/lookup?url={urllib.parse.quote(test_url)}")
    assert l2_code == 200
    assert l2_data["exists"] is True
    assert l2_data["plot"]["question_id"] == qid
    assert l2_data["plot"]["prompt"] == draft["prompt"]

    # Step 5: Cast another vote and ratify coherence
    v_code, v_data = make_request(
        f"{base_url}/api/vote",
        method="POST",
        data={
            "question_id": qid,
            "region_key": "WEST_EUROPE",
            "choice_letter": "B",
            "rater_salt": "ambient_user_02",
            "tier_level": 1
        }
    )
    assert v_code == 200

    # Retrieve stance dossier
    s_code, s_data = make_request(f"{base_url}/api/perspectives/{qid}/by_stance")
    assert s_code == 200
    assert "A" in s_data["perspectives_by_stance"]

"""
Integration tests for Stance-First Perspective Shelf, URL Canonicalization, Custom Plot Creation, and Mutual Ratification.
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


def test_canonical_url_normalization():
    """Verify that tracking tags, YouTube variants, and Reddit paths normalize to identical hashes."""
    # YouTube watch vs shorts vs youtu.be vs tracking tags
    u1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&utm_source=twitter&si=abc123xyz"
    u2 = "https://youtu.be/dQw4w9WgXcQ?t=45s"
    u3 = "https://youtube.com/watch?v=dQw4w9WgXcQ"

    c1, h1 = serve_preview.compute_canonical_hash(u1)
    c2, h2 = serve_preview.compute_canonical_hash(u2)
    c3, h3 = serve_preview.compute_canonical_hash(u3)

    assert c1 == "https://youtube.com/watch?v=dQw4w9WgXcQ"
    assert c2 == "https://youtube.com/watch?v=dQw4w9WgXcQ"
    assert c3 == "https://youtube.com/watch?v=dQw4w9WgXcQ"
    assert h1 == h2 == h3

    # Reddit thread slug stripping
    r1 = "https://www.reddit.com/r/technology/comments/18xyz/open_source_ai_deliberation/?utm_medium=android_app"
    r2 = "https://reddit.com/r/technology/comments/18xyz/"

    cr1, hr1 = serve_preview.compute_canonical_hash(r1)
    cr2, hr2 = serve_preview.compute_canonical_hash(r2)

    assert cr1 == "https://reddit.com/r/technology/comments/18xyz"
    assert cr2 == "https://reddit.com/r/technology/comments/18xyz"
    assert hr1 == hr2


def test_extract_dilemma_draft(api_server):
    """Verify POST /api/plots/extract-draft generates 4 MECE choices."""
    base_url, _ = api_server
    payload = {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "The Future of Autonomous AI Workplaces",
        "text_excerpt": "Remote work, salaries, commute, and office collaboration tradeoffs."
    }
    status, res = make_request(f"{base_url}/api/plots/extract-draft", method="POST", data=payload)
    assert status == 200
    assert res["status"] == "ok"
    draft = res["draft"]
    assert "prompt" in draft
    assert len(draft["choices"]) == 4
    assert draft["choices"][0]["letter"] == "A"
    assert draft["choices"][1]["letter"] == "B"
    assert draft["choices"][2]["letter"] == "C"
    assert draft["choices"][3]["letter"] == "D"
    assert "url_hash" in draft


def test_create_custom_plot_and_lookup(api_server):
    """Verify creating a custom plot with founding vote and looking it up by canonical hash."""
    base_url, db = api_server

    test_url = "https://example.com/editorial/remote-work-mandates?utm_source=feed"
    payload = {
        "title": "Remote Work Location Pay Cuts",
        "prompt": "Should companies cut salaries when workers move to lower-cost regions?",
        "category": "WORK_MOBILITY",
        "domain": "WORK_MOBILITY",
        "canonical_url": test_url,
        "author_vote": "B",
        "author_macro_region": "WEST_EUROPE",
        "author_salt": "founding_creator_salt_123",
        "rationale": "Value is determined by output and quality, not an employee's personal rent costs.",
        "moral_lens": "ECONOMIC_PRAGMATISM",
        "choices": [
            {"letter": "A", "label": "Yes, pay must match local market rates."},
            {"letter": "B", "label": "No, output value is identical regardless of location."},
            {"letter": "C", "label": "Only if local living costs drop by over 40%."},
            {"letter": "D", "label": "Tie pay to national averages instead of local markets."}
        ]
    }

    status, res = make_request(f"{base_url}/api/plots/create", method="POST", data=payload)
    assert status == 201
    assert res["status"] == "ok"
    qid = res["question_id"]
    assert qid.startswith("q_custom_")

    # Verify lookup by URL
    lookup_url = f"{base_url}/api/plots/lookup?url={urllib.parse.quote(test_url)}"
    l_status, l_res = make_request(lookup_url)
    assert l_status == 200
    assert l_res["exists"] is True
    assert l_res["plot"]["question_id"] == qid
    assert l_res["plot"]["prompt"] == payload["prompt"]


def test_get_perspectives_by_stance_and_mutual_ratification(api_server):
    """Verify 4-bay stance organization and mutual ratification scoring."""
    base_url, db = api_server

    # Create a fresh custom dilemma
    q = db.create_custom_plot(
        title="Urban Quiet Hours",
        prompt="Should cities enforce strict quiet hours after 10 PM?",
        category="CIVIC_TRUST",
        author_vote="A",
        author_salt="creator_01",
        author_macro_region="NORDICS",
        author_rationale="Sleep is a fundamental health necessity that individual noise should not disrupt.",
        author_moral_lens="AUTONOMY",
    )
    qid = q["question_id"]

    # Seed perspective in Bay B
    pid_b = db.create_community_perspective(
        question_id=qid,
        choice_letter="B",
        body="Nightlife and cultural vitality are the economic heartbeat of global cities.",
        author_salt="author_b_1",
        author_macro_region="WEST_EUROPE"
    )

    # In-group ratings for B (Option B voters rate B's perspective)
    db.rate_perspective_coherence(pid_b, "voter_b_1", rater_choice="B", eval_type="FAIR_STEELMAN")
    db.rate_perspective_coherence(pid_b, "voter_b_2", rater_choice="B", eval_type="FAIR_STEELMAN")

    # Out-group ratings for B (Option A voters rate B's perspective)
    db.rate_perspective_coherence(pid_b, "voter_a_1", rater_choice="A", eval_type="FAIR_STEELMAN")
    db.rate_perspective_coherence(pid_b, "voter_a_2", rater_choice="A", eval_type="NUANCED_TRADEOFF")

    # Fetch stance dossier as an Option A viewer
    url = f"{base_url}/api/perspectives/{qid}/by_stance?viewer_stance=A"
    status, res = make_request(url)
    assert status == 200
    assert res["status"] == "ok"
    dossier = res["stance_dossier"]
    assert dossier["viewer_stance"] == "A"
    assert "A" in dossier["bays"]
    assert "B" in dossier["bays"]

    bay_b = dossier["bays"]["B"]
    assert bay_b["total"] >= 1
    best_b = bay_b["bridging_perspective"]
    assert best_b is not None
    assert best_b["is_sacred_bridge"] is True
    assert best_b["is_ratified"] is True
    assert best_b["bridging_score"] > 0.0
    assert best_b["moral_lens"] is not None

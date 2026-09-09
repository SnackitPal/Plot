"""
Unit and integration tests for the Cultural Calibration Game & Epistemic Prediction Engine.
Verifies multi-category Brier scoring, Cultural Calibration Index (CCI), blindspot diagnosis,
and the REST API endpoint POST /api/calibrate.
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
from atlas.algorithms.calibration import CulturalCalibrationScorer, CalibrationResult


def test_calibration_scorer_perfect_prediction():
    scorer = CulturalCalibrationScorer()
    ground_truth = {"A": 0.60, "B": 0.20, "C": 0.15, "D": 0.05}
    predictions = {"A": 0.60, "B": 0.20, "C": 0.15, "D": 0.05}

    result = scorer.evaluate(predictions, ground_truth)
    assert result.brier_score == 0.0
    assert result.calibration_index == 1000
    assert result.rank_tier == "EMPATHIC DIPLOMAT"
    assert result.percentile >= 95
    assert "balanced" in result.blindspot_message.lower()


def test_calibration_scorer_uniform_prediction():
    scorer = CulturalCalibrationScorer()
    ground_truth = {"A": 0.60, "B": 0.20, "C": 0.15, "D": 0.05}
    predictions = {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}

    result = scorer.evaluate(predictions, ground_truth)
    # Uniform guess maps to baseline ~600
    assert 550 <= result.calibration_index <= 650
    assert result.rank_tier in ("CURIOUS OBSERVER", "CULTURAL ANTHROPOLOGIST")
    assert result.blindspot_choice == "A"
    assert result.blindspot_delta < 0  # Underestimated Choice A


def test_calibration_scorer_inverted_prediction():
    scorer = CulturalCalibrationScorer()
    ground_truth = {"A": 0.70, "B": 0.15, "C": 0.10, "D": 0.05}
    # Completely inverted predictions
    predictions = {"A": 0.05, "B": 0.10, "C": 0.15, "D": 0.70}

    result = scorer.evaluate(predictions, ground_truth)
    assert result.brier_score > 0.20
    assert result.calibration_index < 300
    assert result.rank_tier == "ECHO-CHAMBER NATIVE"


@pytest.fixture(scope="module")
def calib_server():
    """Start ephemeral test server with isolated database."""
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

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    base_url = f"http://127.0.0.1:{port}"
    yield base_url, test_db

    server.shutdown()
    server.server_close()
    serve_preview.db = orig_db
    if os.path.exists(db_path):
        os.remove(db_path)


def test_post_calibrate_endpoint_success(calib_server):
    base_url, test_db = calib_server
    url = f"{base_url}/api/calibrate"

    payload = {
        "question_id": "q_01",
        "rater_salt": "tester_forecaster_42",
        "predictions": {
            "A": 0.50,
            "B": 0.25,
            "C": 0.15,
            "D": 0.10,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))

    assert data["status"] == "ok"
    assert "calibration_index" in data
    assert 0 <= data["calibration_index"] <= 1000
    assert "rank_tier" in data
    assert "blindspot" in data
    assert "message" in data["blindspot"]

    # Verify persistence in SQLite
    saved = test_db.get_calibration_guess("q_01", "tester_forecaster_42")
    assert saved is not None
    assert saved["calibration_index"] == data["calibration_index"]


def test_post_calibrate_endpoint_invalid_sum(calib_server):
    base_url, _ = calib_server
    url = f"{base_url}/api/calibrate"

    bad_payload = {
        "question_id": "q_01",
        "rater_salt": "tester_bad",
        "predictions": {
            "A": 0.10,
            "B": 0.10,
            "C": 0.10,
            "D": 0.10,  # Sums to 0.40 != 1.0
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(bad_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(req, timeout=5.0)

    assert excinfo.value.code == 400
    body = json.loads(excinfo.value.read().decode("utf-8"))
    assert "must sum to approximately 1.0" in body["message"]

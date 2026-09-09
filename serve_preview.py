"""
PLOT / The Cultural Atlas - Multi-Threaded Development & API Server
Runs entirely on Python standard library + internal atlas package.
Features:
- ThreadingHTTPServer (daemon_threads = True): SSE live-reload never blocks API requests
- Full REST API integration with SQLite (atlas.db):
  * GET  /api/slate/today
  * GET  /api/cartogram/{question_id}
  * POST /api/vote
  * GET  /api/perspectives/{question_id}
  * POST /api/perspectives
  * POST /api/rate
- Debounced in-memory Matrix Factorization cache for <5ms rating responses
- Input validation & HTML escaping for security
- Live-Reload via Server-Sent Events (SSE)
"""

import os
import sys
import time
import json
import uuid
import socket
import html
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any, Optional, List

# Ensure UTF-8 output encoding on Windows if supported
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PORT = 8000
WATCH_EXTENSIONS = {".html", ".css", ".js", ".json", ".svg", ".md"}
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PREVIEW_DIR = os.path.join(ROOT_DIR, "preview")
SERVE_DIR = PREVIEW_DIR if os.path.exists(PREVIEW_DIR) else ROOT_DIR
DB_PATH = os.path.join(ROOT_DIR, "atlas.db")

# Import PLOT domain modules
from atlas.storage.database import AtlasDatabase
from atlas.geo.regions import (
    REGION_DEFINITIONS,
    compute_cartogram_payload,
    get_h3_cell_for_region,
)
from atlas.algorithms.bridging import CommunityNotesMF
from atlas.algorithms.calibration import CulturalCalibrationScorer
from atlas.algorithms.compass import generate_compass_report, compute_user_vector
from atlas.algorithms.trajectory import calculate_trajectory_analytics
from atlas.algorithms.cohort_bridging import rank_bridging_perspectives
from atlas.algorithms.moderation import screen_perspective_submission
from atlas.algorithms.bandits import ContextualCulturalBandit

# Initialize Singleton Database with automatic bootstrap seeding
db = AtlasDatabase(db_path=DB_PATH, auto_seed=True)

# Contextual Cultural Bandit Discovery Engine
bandit_engine = ContextualCulturalBandit(random_seed=42)
try:
    persisted_arms = db.load_bandit_arms()
    for arm_id, arm_data in persisted_arms.items():
        bandit_engine.arms[arm_id] = [float(arm_data["alpha"]), float(arm_data["beta"])]
        bandit_engine.pull_counts[arm_id] = int(arm_data["pulls"])
except Exception:
    pass

# Shared in-memory state for bridging cache and hot reload
last_modified_timestamp = time.time()

# Cache structure: question_id -> {"timestamp": float, "dirty": bool, "data": dict}
_bridging_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()
_fit_lock = threading.Lock()


def mark_perspectives_dirty(question_id: Optional[str] = None):
    """Mark the bridging evaluation cache as dirty for a given question or all questions."""
    with _cache_lock:
        if question_id:
            if question_id in _bridging_cache:
                _bridging_cache[question_id]["dirty"] = True
        else:
            for entry in _bridging_cache.values():
                entry["dirty"] = True


def get_evaluated_perspectives(question_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve perspectives with bridging classifications.
    Uses cached evaluation if clean and under 3 seconds old;
    otherwise fits CommunityNotesMF lazily with double-checked locking.
    """
    now = time.time()
    with _cache_lock:
        entry = _bridging_cache.get(question_id)
        if entry and not entry["dirty"] and (now - entry["timestamp"] < 3.0):
            return entry["data"]

    # Acquire fit lock to prevent cache stampede
    with _fit_lock:
        now = time.time()
        with _cache_lock:
            entry = _bridging_cache.get(question_id)
            if entry and not entry["dirty"] and (now - entry["timestamp"] < 3.0):
                return entry["data"]

        # 1. Fetch perspectives and ratings from DB
        perspectives = db.get_perspectives_for_question(question_id)
        ratings = db.get_all_ratings_for_question(question_id)

        # 2. Run regularized matrix factorization if sufficient ratings exist
        evaluations = {}
        if len(ratings) >= 4:
            try:
                mf = CommunityNotesMF(
                    n_factors=1,
                    helpfulness_threshold=0.60,
                    polarization_tolerance=0.35,
                    min_ratings=2,
                )
                mf.fit(ratings)
                evaluations = {e.perspective_id: e for e in mf.get_all_evaluations()}
            except Exception as e:
                print(f"[BRIDGING MF ERROR] {e}")

        # 3. Augment perspectives with bridging status
        result = []
        for p in perspectives:
            pid = p["perspective_id"]
            eval_item = evaluations.get(pid)
            if eval_item:
                status = eval_item.status
                quality = round(eval_item.intercept_quality, 3)
                latent = round(eval_item.latent_factor, 3)
            else:
                total_r = p.get("total_ratings", 0)
                if total_r < 2:
                    status = "NEEDS_MORE_RATINGS"
                else:
                    helpful_r = p.get("helpful_ratings", 0)
                    status = "COMMON_GROUND" if (helpful_r / total_r) >= 0.6 else "LOW_RESONANCE"
                quality = round(p.get("helpful_ratings", 0) / max(1, p.get("total_ratings", 1)), 2)
                latent = 0.0

            p_augmented = dict(p)
            p_augmented["bridging_status"] = status
            p_augmented["bridging_quality"] = quality
            p_augmented["latent_factor"] = latent
            result.append(p_augmented)

        # 4. Update cache
        with _cache_lock:
            _bridging_cache[question_id] = {
                "timestamp": now,
                "dirty": False,
                "data": result,
            }

        return result


def find_available_port(start_port=8000, max_attempts=20):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def file_watcher_thread():
    global last_modified_timestamp
    known_mtimes = {}

    while True:
        try:
            changed = False
            for base_dir in [ROOT_DIR, PREVIEW_DIR]:
                if not os.path.exists(base_dir):
                    continue
                for root, _, files in os.walk(base_dir):
                    if ".git" in root or ".agents" in root or ".venv" in root or "__pycache__" in root:
                        continue
                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in WATCH_EXTENSIONS:
                            filepath = os.path.join(root, file)
                            try:
                                mtime = os.path.getmtime(filepath)
                                if filepath in known_mtimes and mtime > known_mtimes[filepath]:
                                    changed = True
                                known_mtimes[filepath] = mtime
                            except OSError:
                                pass
            if changed:
                last_modified_timestamp = time.time()
                print("[HOT-RELOAD] File change detected. Refreshing browser tabs...")
        except Exception:
            pass
        time.sleep(0.5)


class AtlasRequestHandler(SimpleHTTPRequestHandler):
    """
    Multi-Threaded HTTP and REST API Router for PLOT.
    Handles static files from ./preview/ and dynamic JSON endpoints under /api/*.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def _send_json(self, status_code: int, data: Any):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self) -> Optional[Dict[str, Any]]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return {}
            raw_body = self.rfile.read(content_length).decode("utf-8")
            return json.loads(raw_body)
        except Exception:
            return None

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")

        # 1. Hot-Reload SSE endpoint
        if path == "/__livereload__":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            client_subscribed_at = last_modified_timestamp
            while True:
                time.sleep(0.3)
                if last_modified_timestamp > client_subscribed_at:
                    try:
                        self.wfile.write(b"data: reload\n\n")
                        self.wfile.flush()
                        break
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
            return

        # Root / Index HTML handler (prevent 304 navigation failure in Service Worker)
        if path in ("", "/index.html", "/preview", "/preview/index.html"):
            index_path = os.path.join(PREVIEW_DIR, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
                return

        # Favicon alias
        if path == "/favicon.ico":
            self.send_response(302)
            self.send_header("Location", "/icon.svg")
            self.end_headers()
            return

        # PWA Manifest: GET /manifest.json
        if path == "/manifest.json":
            manifest_path = os.path.join(PREVIEW_DIR, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
                return

        # PWA Service Worker: GET /sw.js
        if path == "/sw.js":
            sw_path = os.path.join(PREVIEW_DIR, "sw.js")
            if os.path.exists(sw_path):
                with open(sw_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript; charset=utf-8")
                self.send_header("Service-Worker-Allowed", "/")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content)
                return

        # Adaptive MAB Discovery: GET /api/questions/discover
        if path == "/api/questions/discover":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            rater_salt = query_params.get("rater_salt", [None])[0]
            completed_ids = []
            if rater_salt:
                user_votes = db.get_user_votes(rater_salt)
                completed_ids = list(user_votes.keys())

            candidates = db.get_all_candidate_questions()
            recs = bandit_engine.recommend_discovery_question(
                candidate_questions=candidates,
                user_completed_ids=completed_ids,
                top_k=1
            )
            rec = recs[0] if recs else None
            self._send_json(200, {"status": "ok", "recommendation": rec})
            return

        # 2. REST API: GET /api/slates
        if path == "/api/slates":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            rater_salt = query_params.get("rater_salt", [None])[0]
            slates = db.get_all_slates(rater_salt)
            self._send_json(200, {"status": "ok", "slates": slates})
            return

        # 3. REST API: GET /api/slate/day/:day_num
        if path.startswith("/api/slate/day/"):
            parts = path.split("/")
            if len(parts) >= 5:
                try:
                    day_num = int(parts[4])
                    slate = db.get_slate_by_day(day_num)
                    if slate:
                        self._send_json(200, {"status": "ok", "slate": slate})
                        return
                except ValueError:
                    pass
            self._send_json(404, {"status": "error", "message": "Day slate not found"})
            return

        # 4. REST API: GET /api/user/state/:rater_salt
        if path.startswith("/api/user/state/"):
            parts = path.split("/")
            if len(parts) >= 5:
                rater_salt = parts[4]
                user_state = db.get_user_state(rater_salt)
                self._send_json(200, {"status": "ok", "state": user_state})
                return

        # 5. REST API: GET /api/user/streak/:rater_salt
        if path.startswith("/api/user/streak/"):
            parts = path.split("/")
            if len(parts) >= 5:
                rater_salt = parts[4]
                streak = db.get_user_streak(rater_salt)
                self._send_json(200, {"status": "ok", "streak": streak})
                return

        # 6. REST API: GET /api/compass/trajectory/:rater_salt
        if path.startswith("/api/compass/trajectory/"):
            parts = path.split("/")
            if len(parts) >= 5:
                rater_salt = parts[4]
                snapshots = db.get_compass_trajectory(rater_salt)
                analytics = calculate_trajectory_analytics(snapshots)
                self._send_json(200, {
                    "status": "ok",
                    "trajectory": snapshots,
                    "analytics": analytics,
                })
                return

        # 7. REST API: GET /api/slate/today
        if path == "/api/slate/today":
            slate = db.get_active_slate()
            if not slate:
                self._send_json(404, {"status": "error", "message": "No active slate found"})
                return
            self._send_json(200, {"status": "ok", "slate": slate})
            return

        # 8. REST API: GET /api/cartogram/:question_id
        if path.startswith("/api/cartogram/"):
            parts = path.split("/")
            if len(parts) >= 4:
                question_id = parts[3]
                query_params = urllib.parse.parse_qs(parsed_url.query)
                tier_filter = query_params.get("tier", ["all"])[0]
                mode = query_params.get("mode", ["community"])[0]
                cartogram_data = compute_cartogram_payload(question_id, db, tier_filter=tier_filter, mode=mode)
                self._send_json(200, {"status": "ok", "cartogram": cartogram_data})
                return

        # 8b. REST API: GET /api/aggregates/:question_id
        if path.startswith("/api/aggregates/"):
            parts = path.split("/")
            if len(parts) >= 4:
                question_id = parts[3]
                aggregates = db.get_question_multi_tier_aggregates(question_id)
                self._send_json(200, {"status": "ok", "aggregates": aggregates})
                return

        # 8c. REST API: GET /api/archive/search
        if path == "/api/archive/search":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            q_term = query_params.get("q", [""])[0].strip().lower()
            category = query_params.get("category", ["ALL"])[0].strip().upper()
            benchmark_only = query_params.get("benchmark_only", ["false"])[0].lower() in ("true", "1", "yes")
            try:
                limit = min(int(query_params.get("limit", [50])[0]), 150)
            except ValueError:
                limit = 50
            try:
                offset = int(query_params.get("offset", [0])[0])
            except ValueError:
                offset = 0

            candidates = db.get_all_candidate_questions()
            tokens = [t for t in q_term.split() if t]
            from atlas.content.benchmarks import BENCHMARK_CATALOG

            results = []
            for item in candidates:
                qid = item.get("question_id") or item.get("id")
                q_cat = (item.get("category") or "").upper()
                bm_meta = BENCHMARK_CATALOG.get(qid)
                is_bm = bool(bm_meta)

                if benchmark_only and not is_bm:
                    continue

                if category != "ALL" and q_cat != category:
                    continue

                prompt = (item.get("prompt") or "").lower()
                slate_title = (item.get("slate_title") or "").lower()
                choices_text = " ".join([c.get("label") or c.get("text") or "" for c in item.get("choices", [])]).lower()

                score = 0
                if not q_term:
                    score = 1
                else:
                    if q_term in prompt:
                        score += 100
                    for t in tokens:
                        if t in prompt:
                            score += 30
                        if t in choices_text:
                            score += 15
                        if t in q_cat.lower():
                            score += 20
                        if t in slate_title:
                            score += 10

                if score > 0:
                    entry = dict(item)
                    entry["score"] = score
                    entry["is_benchmark"] = is_bm
                    if is_bm:
                        entry["provenance_source"] = bm_meta.get("provenance_source")
                        entry["sample_size_n"] = bm_meta.get("sample_size_n")
                    results.append(entry)

            # Sort by search score desc, then by day_number asc, step_index asc
            results.sort(key=lambda x: (x["score"], -x.get("day_number", 1), -x.get("step_index", 1)), reverse=True)
            total_matches = len(results)
            paginated = results[offset : offset + limit]

            self._send_json(200, {
                "status": "ok",
                "total": total_matches,
                "limit": limit,
                "offset": offset,
                "results": paginated,
            })
            return

        # 9. REST API: GET /api/perspectives/:question_id/cohorts
        if path.startswith("/api/perspectives/") and "/cohorts" in path:
            parts = path.split("/")
            if len(parts) >= 4:
                question_id = parts[3]
                query_params = urllib.parse.parse_qs(parsed_url.query)
                axis = query_params.get("axis", ["generation"])[0]
                c1 = query_params.get("c1", ["GEN_Z"])[0]
                c2 = query_params.get("c2", ["BOOMER_PLUS"])[0]
                perspectives = get_evaluated_perspectives(question_id)
                cohort_map = db.get_perspective_cohort_ratings(question_id, axis)
                ranked = rank_bridging_perspectives(
                    perspectives, cohort_map, cohort_axis=axis, cohort_a=c1, cohort_b=c2
                )
                # Rawlsian Veil of Ignorance: Shield author prestige while calibrating
                for item in ranked:
                    auth_salt = item.get("author_salt")
                    auth_rep = db.get_user_reputation(auth_salt) if auth_salt else {
                        "reputation_tier": "CITIZEN_DELIBERATOR",
                        "tier_insignia": "Basalt Slate",
                    }
                    has_quorum = item.get("bridging", {}).get("has_quorum", False)
                    is_bridge = item.get("bridging", {}).get("is_sacred_bridge", False)
                    if not has_quorum and not is_bridge:
                        item["is_veiled"] = True
                        item["author_reputation_tier"] = "CALIBRATING"
                        item["author_tier_insignia"] = "🌱 Calibrating · Veil Active"
                    else:
                        item["is_veiled"] = False
                        item["author_reputation_tier"] = auth_rep.get("reputation_tier", "CITIZEN_DELIBERATOR")
                        item["author_tier_insignia"] = auth_rep.get("tier_insignia", "Basalt Slate")

                self._send_json(200, {
                    "status": "ok",
                    "question_id": question_id,
                    "cohort_axis": axis,
                    "cohort_a": c1,
                    "cohort_b": c2,
                    "perspectives": ranked,
                })
                return

        # 9b. REST API: GET /api/perspectives/:question_id/review_deck
        if path.startswith("/api/perspectives/") and "/review_deck" in path:
            parts = path.split("/")
            if len(parts) >= 4:
                question_id = parts[3]
                query_params = urllib.parse.parse_qs(parsed_url.query)
                rater_salt = query_params.get("rater_salt", [""])[0]
                cohort_val = query_params.get("cohort_val", ["UNSPECIFIED"])[0]
                limit_param = int(query_params.get("limit", [3])[0])
                deck = db.get_review_deck(
                    question_id=question_id,
                    viewer_salt=rater_salt,
                    viewer_generation=cohort_val,
                    limit=limit_param,
                )
                self._send_json(200, {
                    "status": "ok",
                    "question_id": question_id,
                    "review_deck": deck,
                })
                return

        # 9c. REST API: GET /api/perspectives/:question_id/review_queue
        if path.startswith("/api/perspectives/") and "/review_queue" in path:
            parts = path.split("/")
            if len(parts) >= 4:
                question_id = parts[3]
                query_params = urllib.parse.parse_qs(parsed_url.query)
                rater_salt = query_params.get("rater_salt", [""])[0]
                cohort_val = query_params.get("cohort_val", ["UNSPECIFIED"])[0]
                queue = db.get_cold_start_review_queue(
                    question_id=question_id,
                    rater_salt=rater_salt,
                    rater_cohort_val=cohort_val,
                    limit=2,
                )
                for item in queue:
                    db.record_perspective_impression(item["perspective_id"], rater_salt, cohort_val)
                self._send_json(200, {
                    "status": "ok",
                    "question_id": question_id,
                    "review_queue": queue,
                })
                return

        # 9d. REST API: GET /api/perspectives/:question_id
        if path.startswith("/api/perspectives/"):
            parts = path.split("/")
            if len(parts) >= 4:
                question_id = parts[3]
                perspectives = get_evaluated_perspectives(question_id)
                self._send_json(200, {"status": "ok", "perspectives": perspectives})
                return

        # 10. REST API: GET /api/user/reputation/:rater_salt
        if path.startswith("/api/user/reputation/"):
            parts = path.split("/")
            if len(parts) >= 5:
                rater_salt = parts[4]
                rep = db.get_user_reputation(rater_salt)
                self._send_json(200, {"status": "ok", "reputation": rep})
                return

        # 10b. REST API: GET /api/user/demographics/:rater_salt
        if path.startswith("/api/user/demographics/"):
            parts = path.split("/")
            if len(parts) >= 5:
                rater_salt = parts[4]
                demo = db.get_user_demographics(rater_salt)
                self._send_json(200, {"status": "ok", "demographics": demo})
                return

        # 10c. REST API: GET /api/user/verification/:rater_salt
        if path.startswith("/api/user/verification/"):
            parts = path.split("/")
            if len(parts) >= 5:
                rater_salt = parts[4]
                ver = db.get_user_verification(rater_salt)
                self._send_json(200, {"status": "ok", "verification": ver})
                return

        # 10. REST API: GET /api/compass/:rater_salt
        if path.startswith("/api/compass/"):
            parts = path.split("/")
            if len(parts) >= 4:
                rater_salt = parts[3]
                votes = db.get_user_votes(rater_salt)
                if not votes:
                    # Provide rich default baseline preview if user hasn't voted
                    votes = {"q_01": "A", "q_02": "C", "q_03": "A", "q_04": "C", "q_05": "B"}
                report = generate_compass_report(rater_salt, votes)
                try:
                    from atlas.algorithms.culture_shock import generate_personalized_dossier
                    report["dossier"] = generate_personalized_dossier(
                        report["vector"],
                        total_votes=report.get("total_votes_considered", len(votes)),
                        archetype_title=report.get("archetype", {}).get("title", "THE AUTONOMOUS COSMOPOLITAN"),
                    )
                except Exception as e:
                    print(f"[DOSSIER ERROR] {e}")
                self._send_json(200, {"status": "ok", "compass": report})
                return

        # 11. REST API: GET /api/destinations
        if path == "/api/destinations":
            from atlas.algorithms.compass import GLOBAL_CITY_CENTROIDS
            from atlas.algorithms.culture_shock import CITY_LOCAL_CODES
            destinations = []
            for c in GLOBAL_CITY_CENTROIDS:
                local_info = CITY_LOCAL_CODES.get(c["city_id"], {})
                destinations.append({
                    "city_id": c["city_id"],
                    "city_name": c["city_name"],
                    "country": c["country"],
                    "flag": c["flag"],
                    "tagline": c["tagline"],
                    "narrative": c["narrative"],
                    "vector": c["vector"],
                    "local_maxim": local_info.get("local_maxim", c["tagline"]),
                    "golden_rule": local_info.get("golden_rule", c["narrative"]),
                    "transit_code": local_info.get("transit_code", ""),
                })
            self._send_json(200, {"status": "ok", "destinations": destinations})
            return

        # 12. REST API: GET /api/culture-shock
        if path == "/api/culture-shock":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            dest_id = (query_params.get("destination", ["tokyo"])[0]).strip()
            rater_salt = (query_params.get("rater_salt", [""])[0]).strip()

            votes = db.get_user_votes(rater_salt) if rater_salt else {}
            if not votes:
                votes = {"q_01": "A", "q_02": "C", "q_03": "A", "q_04": "C", "q_05": "B"}

            from atlas.algorithms.compass import compute_user_vector, classify_archetype
            from atlas.algorithms.culture_shock import calculate_culture_shock, generate_personalized_dossier

            user_vec = compute_user_vector(votes)
            shock_result = calculate_culture_shock(user_vec, dest_id)
            archetype = classify_archetype(user_vec)
            dossier = generate_personalized_dossier(
                user_vec,
                total_votes=len([v for v in votes.values() if v]),
                archetype_title=archetype["title"],
            )
            shock_result["dossier"] = dossier
            self._send_json(200, {"status": "ok", "culture_shock": shock_result})
            return

        # 13. Default static file handler
        super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")

        # 1. REST API: POST /api/vote
        if path == "/api/vote":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            question_id = body.get("question_id")
            region_key = body.get("region_key")
            choice_letter = body.get("choice_letter", "").upper()
            rater_salt = (body.get("rater_salt") or "").strip()
            tier_level = int(body.get("tier_level") or 1)
            verification_sig = body.get("verification_sig")

            if not question_id or not region_key or not choice_letter:
                self._send_json(400, {"status": "error", "message": "Missing required fields"})
                return

            if choice_letter not in ("A", "B", "C", "D"):
                self._send_json(400, {"status": "error", "message": f"Invalid choice '{choice_letter}'. Must be A, B, C, or D."})
                return

            if region_key not in REGION_DEFINITIONS:
                self._send_json(400, {"status": "error", "message": f"Unknown region key '{region_key}'."})
                return

            # Check question selectivity gating
            q_info = db.get_question(question_id)
            if q_info:
                min_req = int(q_info.get("min_verification_tier", 1) or 1)
                if tier_level < min_req:
                    self._send_json(403, {
                        "status": "error",
                        "code": "VERIFICATION_REQUIRED",
                        "message": f"This question requires verification tier {min_req} or above.",
                    })
                    return

            h3_cell_id = get_h3_cell_for_region(region_key)
            db.record_tier_hex_vote(question_id, h3_cell_id, choice_letter, tier_level=tier_level, increment=1)
            if rater_salt:
                db.record_user_vote(
                    rater_salt,
                    question_id,
                    choice_letter,
                    region_key,
                    tier_level=tier_level,
                    verification_sig=verification_sig,
                )

            # Return updated cartogram payload and multi-tier comparative aggregates
            updated_cartogram = compute_cartogram_payload(question_id, db)
            aggregates = db.get_question_multi_tier_aggregates(question_id)
            self._send_json(200, {
                "status": "ok",
                "message": "Vote recorded successfully",
                "h3_cell_id": h3_cell_id,
                "cartogram": updated_cartogram,
                "aggregates": aggregates,
            })
            return

        # 1b. REST API: POST /api/vote/upgrade
        if path == "/api/vote/upgrade":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            rater_salt = (body.get("rater_salt") or "").strip()
            target_tier = int(body.get("target_tier") or 2)
            verification_method = body.get("verification_method") or "PASSKEY"
            verification_sig = body.get("verification_sig")
            credential_id = body.get("credential_id")

            if not rater_salt:
                self._send_json(400, {"status": "error", "message": "Missing rater_salt"})
                return

            upgraded_cnt = db.upgrade_user_vote_tier(
                rater_salt=rater_salt,
                new_tier=target_tier,
                verification_method=verification_method,
                verification_sig=verification_sig,
                credential_id=credential_id,
            )
            ver = db.get_user_verification(rater_salt)
            self._send_json(200, {
                "status": "ok",
                "message": f"Successfully upgraded {upgraded_cnt} votes to Tier {target_tier}",
                "upgraded_votes": upgraded_cnt,
                "verification": ver,
            })
            return

        # 1c. REST API: POST /api/user/verify
        if path == "/api/user/verify":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            rater_salt = (body.get("rater_salt") or "").strip()
            tier = int(body.get("tier") or 2)
            method = body.get("method") or "PASSKEY"
            credential_id = body.get("credential_id")
            reputation_weight = float(body.get("reputation_weight") or 1.5)

            if not rater_salt:
                self._send_json(400, {"status": "error", "message": "Missing rater_salt"})
                return

            db.set_user_verification(
                rater_salt=rater_salt,
                current_tier=tier,
                verification_method=method,
                credential_id=credential_id,
                reputation_weight=reputation_weight,
            )
            upgraded_cnt = db.upgrade_user_vote_tier(
                rater_salt=rater_salt,
                new_tier=tier,
                verification_method=method,
                credential_id=credential_id,
            )
            ver = db.get_user_verification(rater_salt)
            self._send_json(200, {
                "status": "ok",
                "message": "User verified successfully",
                "verification": ver,
                "upgraded_votes": upgraded_cnt,
            })
            return

        # 2. REST API: POST /api/perspectives
        if path == "/api/perspectives":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            question_id = body.get("question_id")
            choice_letter = (body.get("choice_letter") or "").upper()
            text = (body.get("body") or "").strip()
            author_salt = (body.get("author_salt") or "").strip()
            author_generation = (body.get("author_generation") or "UNSPECIFIED").strip()
            author_urbanicity = (body.get("author_urbanicity") or "UNSPECIFIED").strip()
            author_macro_region = (body.get("author_macro_region") or "UNSPECIFIED").strip()

            if not question_id or choice_letter not in ("A", "B", "C", "D"):
                self._send_json(400, {"status": "error", "message": "Invalid question_id or choice_letter"})
                return

            # Execute Heuristic Moderation & Epistemic Screening Pipeline
            screen_res = screen_perspective_submission(text)
            if not screen_res["is_approved"]:
                self._send_json(422, {
                    "status": "error",
                    "code": "MODERATION_FLAGGED",
                    "message": screen_res["message"],
                    "flags": screen_res["flags"],
                    "constructiveness": screen_res["constructiveness"],
                })
                return

            safe_author = author_salt if author_salt else f"anon_{uuid.uuid4().hex[:6]}"
            perspective_id = db.create_community_perspective(
                question_id=question_id,
                choice_letter=choice_letter,
                body=text,
                author_salt=safe_author,
                author_generation=author_generation,
                author_urbanicity=author_urbanicity,
                author_macro_region=author_macro_region,
                moderation_status="APPROVED",
                moderation_flags="",
            )
            mark_perspectives_dirty(question_id)

            self._send_json(201, {
                "status": "ok",
                "perspective_id": perspective_id,
                "moderation_status": "APPROVED",
                "message": "Perspective published and entered into cross-cohort deliberation.",
                "constructiveness": screen_res["constructiveness"],
                "bridging_preview": {
                    "status": "INSUFFICIENT_DATA",
                    "badge": "🌱 Needs More Ratings",
                    "votes_needed": 5,
                },
            })
            return

        # 3. REST API: POST /api/rate
        if path == "/api/rate":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            perspective_id = body.get("perspective_id")
            rater_salt = (body.get("rater_salt") or "").strip()
            score_raw = body.get("rating_score", 1.0)
            rating_category = body.get("rating_category")

            if not perspective_id:
                self._send_json(400, {"status": "error", "message": "Missing perspective_id"})
                return

            try:
                score = float(score_raw)
                if not (0.0 <= score <= 1.0):
                    raise ValueError()
            except (ValueError, TypeError):
                self._send_json(400, {"status": "error", "message": "rating_score must be a float between 0.0 and 1.0"})
                return

            if not rating_category:
                rating_category = "HELPFUL_BRIDGE" if score >= 0.5 else "UNHELPFUL"

            if not rater_salt:
                rater_salt = f"rater_{uuid.uuid4().hex[:6]}"

            rater_generation = body.get("rater_generation")
            rater_urbanicity = body.get("rater_urbanicity")

            # Immediate SQLite write (<5ms)
            db.rate_perspective(perspective_id, rater_salt, score, rater_generation, rater_urbanicity, rating_category=rating_category)

            # Extract question_id to mark cache dirty
            with db._get_connection() as conn:
                row = conn.execute("SELECT question_id FROM perspectives WHERE perspective_id = ?;", (perspective_id,)).fetchone()
                if row:
                    mark_perspectives_dirty(row["question_id"])

            self._send_json(200, {
                "status": "ok",
                "message": "Rating recorded successfully",
                "perspective_id": perspective_id,
            })
            return

        # 3b. REST API: POST /api/perspectives/rate_deck
        if path == "/api/perspectives/rate_deck":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            perspective_id = body.get("perspective_id")
            rater_salt = (body.get("rater_salt") or "").strip()
            rating_category = (body.get("rating_category") or "HELPFUL_BRIDGE").strip().upper()
            rater_generation = body.get("rater_generation", "UNSPECIFIED")
            rater_urbanicity = body.get("rater_urbanicity", "UNSPECIFIED")

            if not perspective_id:
                self._send_json(400, {"status": "error", "message": "Missing perspective_id"})
                return

            if not rater_salt:
                rater_salt = f"rater_{uuid.uuid4().hex[:6]}"

            valid_categories = {"HELPFUL_BRIDGE", "INFORMATIVE", "ECHO_ONLY", "UNHELPFUL"}
            if rating_category not in valid_categories:
                self._send_json(400, {
                    "status": "error",
                    "message": f"Invalid rating_category '{rating_category}'. Must be one of: {', '.join(valid_categories)}",
                })
                return

            rate_res = db.rate_deck_item(
                perspective_id=perspective_id,
                rater_salt=rater_salt,
                rating_category=rating_category,
                rater_generation=rater_generation,
                rater_urbanicity=rater_urbanicity,
            )

            # Mark perspectives cache dirty for this question
            with db._get_connection() as conn:
                row = conn.execute("SELECT question_id FROM perspectives WHERE perspective_id = ?;", (perspective_id,)).fetchone()
                if row:
                    mark_perspectives_dirty(row["question_id"])

            self._send_json(200, rate_res)
            return

        # 4. REST API: POST /api/calibrate (Epistemic Prediction Challenge)
        if path == "/api/calibrate":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            question_id = body.get("question_id")
            rater_salt = (body.get("rater_salt") or "").strip()
            predictions_raw = body.get("predictions")

            if not question_id or not isinstance(predictions_raw, dict):
                self._send_json(400, {"status": "error", "message": "Missing question_id or predictions dictionary"})
                return

            try:
                predictions = {
                    c: float(predictions_raw.get(c, 0.0)) for c in ("A", "B", "C", "D")
                }
            except (ValueError, TypeError):
                self._send_json(400, {"status": "error", "message": "Predictions must contain valid numbers for A, B, C, D"})
                return

            pred_sum = sum(predictions.values())
            if not (0.85 <= pred_sum <= 1.15):
                self._send_json(400, {
                    "status": "error",
                    "message": f"Predictions must sum to approximately 1.0 (got {pred_sum:.2f})"
                })
                return

            # Normalize to sum exactly to 1.0
            predictions = {c: round(predictions[c] / pred_sum, 4) for c in ("A", "B", "C", "D")}

            if not rater_salt:
                rater_salt = f"rater_{uuid.uuid4().hex[:6]}"

            # Fetch live empirical ground truth
            ground_truth = db.get_question_ground_truth(question_id)

            scorer = CulturalCalibrationScorer()
            eval_res = scorer.evaluate(predictions, ground_truth)

            guess_id = f"g_{uuid.uuid4().hex[:8]}"
            db.record_calibration_guess(
                guess_id=guess_id,
                question_id=question_id,
                rater_salt=rater_salt,
                pred_a=predictions["A"],
                pred_b=predictions["B"],
                pred_c=predictions["C"],
                pred_d=predictions["D"],
                brier_score=eval_res.brier_score,
                calibration_index=eval_res.calibration_index,
            )

            self._send_json(200, {
                "status": "ok",
                "guess_id": guess_id,
                "brier_score": eval_res.brier_score,
                "calibration_index": eval_res.calibration_index,
                "rank_tier": eval_res.rank_tier,
                "rank_description": eval_res.rank_description,
                "percentile": eval_res.percentile,
                "blindspot": {
                    "choice": eval_res.blindspot_choice,
                    "delta": eval_res.blindspot_delta,
                    "message": eval_res.blindspot_message,
                },
                "ground_truth": eval_res.ground_truth,
                "predictions": eval_res.predictions,
            })
            return

        # 4. REST API: POST /api/compass/recalculate
        if path == "/api/compass/recalculate":
            body = self._read_json_body()
            if body is None:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            rater_salt = (body.get("rater_salt") or "").strip()
            if not rater_salt:
                rater_salt = f"user_{uuid.uuid4().hex[:8]}"

            votes = body.get("votes")
            if not isinstance(votes, dict) or not votes:
                votes = db.get_user_votes(rater_salt)
            if not votes:
                votes = {"q_01": "A", "q_02": "C", "q_03": "A", "q_04": "C", "q_05": "B"}

            report = generate_compass_report(rater_salt, votes)
            try:
                from atlas.algorithms.culture_shock import generate_personalized_dossier
                report["dossier"] = generate_personalized_dossier(
                    report["vector"],
                    total_votes=report.get("total_votes_considered", len(votes)),
                    archetype_title=report.get("archetype", {}).get("title", "THE AUTONOMOUS COSMOPOLITAN"),
                )
            except Exception as e:
                print(f"[DOSSIER ERROR] {e}")

            db.save_archetype_profile({
                "rater_salt": rater_salt,
                "archetype_title": report["archetype"]["title"],
                "primary_city": report["primary_twin"]["city_name"],
                "primary_city_country": report["primary_twin"]["country"],
                "primary_city_flag": report["primary_twin"]["flag"],
                "match_pct": report["primary_twin"]["match_pct"],
                "counter_city": report["counter_twin"]["city_name"],
                "counter_city_country": report["counter_twin"]["country"],
                "counter_city_flag": report["counter_twin"]["flag"],
                "counter_match_pct": report["counter_twin"]["match_pct"],
                "vector_autonomy": report["vector"]["autonomy"],
                "vector_punctuality": report["vector"]["punctuality"],
                "vector_boundary": report["vector"]["boundary"],
                "vector_freedom": report["vector"]["freedom"],
                "vector_trust": report["vector"]["trust"],
                "summary_narrative": report["archetype"]["summary"],
            })

            # Record historical trajectory snapshot
            if rater_salt:
                day_num = body.get("day_number", 1)
                try:
                    db.record_compass_history(
                        rater_salt=rater_salt,
                        slate_id=f"slate_daily_{day_num:02d}",
                        day_number=day_num,
                        vector=report["vector"],
                        primary_city=report["primary_twin"]["city_name"],
                        match_pct=report["primary_twin"]["match_pct"],
                        confidence_pct=report.get("confidence_pct", 50),
                        num_votes=report.get("total_votes_considered", len(votes)),
                        archetype_title=report["archetype"]["title"],
                    )
                except Exception as e:
                    print(f"[TRAJECTORY] Log error: {e}")

            # Fetch updated trajectory snapshots and analytics
            snapshots = db.get_compass_trajectory(rater_salt)
            analytics = calculate_trajectory_analytics(snapshots)

            self._send_json(200, {
                "status": "ok",
                "compass": report,
                "trajectory": snapshots,
                "analytics": analytics,
            })
            return

        # 6. REST API: POST /api/user/demographics
        if path == "/api/user/demographics":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            rater_salt = (body.get("rater_salt") or "").strip()
            if not rater_salt:
                self._send_json(400, {"status": "error", "message": "Missing rater_salt"})
                return

            gen = body.get("generation_cohort", "UNSPECIFIED")
            urb = body.get("urbanicity", "UNSPECIFIED")
            reg = body.get("macro_region", "UNSPECIFIED")

            db.save_user_demographics(rater_salt, gen, urb, reg)
            mark_perspectives_dirty(None)
            updated_demo = db.get_user_demographics(rater_salt)
            self._send_json(200, {
                "status": "ok",
                "message": "Demographics saved successfully",
                "demographics": updated_demo,
            })
            return

        # 7. REST API: POST /api/discovery/feedback
        if path == "/api/discovery/feedback":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            qid = body.get("question_id")
            if not qid:
                self._send_json(400, {"status": "error", "message": "Missing question_id"})
                return

            completion = float(body.get("completion", 1.0))
            h = float(body.get("entropy_norm", 0.8))
            v = float(body.get("regional_variance", 0.05))
            reward = ContextualCulturalBandit.calculate_composite_epistemic_reward(completion, h, v)
            bandit_engine.update(qid, reward)

            stats = bandit_engine.get_stats(qid)
            db.save_bandit_arm(qid, stats["alpha"], stats["beta"], stats["pulls"])
            self._send_json(200, {
                "status": "ok",
                "question_id": qid,
                "arm_stats": stats,
                "reward_applied": reward,
            })
            return

        # 8. REST API: POST /api/sync/batch
        if path == "/api/sync/batch":
            body = self._read_json_body()
            if not body:
                self._send_json(400, {"status": "error", "message": "Invalid JSON body"})
                return

            rater_salt = (body.get("rater_salt") or "").strip()
            actions = body.get("actions", [])
            batch_id = body.get("batch_id")
            if not rater_salt or not isinstance(actions, list):
                self._send_json(400, {"status": "error", "message": "rater_salt and actions list required"})
                return

            mark_perspectives_dirty(None)
            res = db.execute_batch_sync(rater_salt, actions, batch_id)
            self._send_json(200, {
                "status": "ok",
                "processed": res.get("processed", len(actions)),
                "sync_result": res,
            })
            return

        self._send_json(404, {"status": "error", "message": "Endpoint not found"})


def run_server(port: int = PORT, open_browser: bool = False):
    actual_port = find_available_port(port)

    # Start file watcher for hot-reload
    watcher = threading.Thread(target=file_watcher_thread, daemon=True)
    watcher.start()

    # Use ThreadingHTTPServer so SSE connections do not block API endpoints
    server = ThreadingHTTPServer(("127.0.0.1", actual_port), AtlasRequestHandler)
    server.daemon_threads = True

    url = f"http://127.0.0.1:{actual_port}"
    print("=" * 64)
    print("   🌐 PLOT: The Cultural Atlas — Multi-Threaded Dev Server")
    print(f"   📍 Local Preview: {url}")
    print(f"   📂 Serving Root : {SERVE_DIR}")
    print("   ⚡ Concurrency  : ThreadingHTTPServer (daemon_threads = True)")
    print("   🗄️ Database     : SQLite WAL mode + PRAGMA busy_timeout = 5000")
    print("   ✨ Features     : Live REST API + Bridging Matrix Factorization")
    print("   🔄 Live-Reload  : Active via Server-Sent Events (SSE)")
    print("   🛑 To stop      : Press Ctrl + C in this terminal")
    print("=" * 64)

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down gracefully...")
        server.server_close()


if __name__ == "__main__":
    auto_open = "--no-open" not in sys.argv
    run_server(port=PORT, open_browser=auto_open)

"""
SQLite Database Repository Layer for PLOT.
Thread-safe, local-first data storage for slates, questions, hex aggregates, and bridging perspectives.
Configured with WAL mode and busy timeout for concurrent threaded access.
"""

import os
import json
import sqlite3
import datetime
import uuid
from typing import List, Dict, Tuple, Any, Optional
from contextlib import contextmanager

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


class AtlasDatabase:
    """Thread-safe SQLite database manager for PLOT."""

    def __init__(self, db_path: str = "atlas.db", auto_seed: bool = False):
        self.db_path = db_path
        self.init_db()
        if auto_seed:
            self.seed_default_data_if_empty()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def init_db(self):
        """Execute schema.sql to ensure all tables and indices exist, with safe migrations."""
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        with self._get_connection() as conn:
            conn.executescript(schema_sql)
            # Safe column additions for pre-existing databases
            try:
                conn.execute("ALTER TABLE slates ADD COLUMN day_number INTEGER;")
            except Exception:
                pass
            try:
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_slates_day ON slates(day_number);")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE slates ADD COLUMN domain_tags TEXT DEFAULT '[]';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE questions ADD COLUMN domain TEXT DEFAULT 'WORK_MOBILITY';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE questions ADD COLUMN axis TEXT DEFAULT 'autonomy';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE user_compass_history ADD COLUMN num_votes INTEGER DEFAULT 0;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE user_compass_history ADD COLUMN archetype_title TEXT DEFAULT '';")
            except Exception:
                pass
            try:
                conn.execute("""
                    DELETE FROM user_compass_history
                    WHERE history_id NOT IN (
                        SELECT MAX(history_id)
                        FROM user_compass_history
                        GROUP BY rater_salt, day_number
                    );
                """)
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_compass_history_user_day ON user_compass_history(rater_salt, day_number);")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspective_ratings ADD COLUMN rater_generation TEXT DEFAULT 'UNSPECIFIED';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspective_ratings ADD COLUMN rater_urbanicity TEXT DEFAULT 'UNSPECIFIED';")
            except Exception:
                pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_perspective_ratings_cohort ON perspective_ratings(perspective_id, rater_generation);")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN author_generation TEXT DEFAULT 'UNSPECIFIED';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN author_urbanicity TEXT DEFAULT 'UNSPECIFIED';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN author_macro_region TEXT DEFAULT 'UNSPECIFIED';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN moderation_status TEXT DEFAULT 'APPROVED';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN moderation_flags TEXT DEFAULT '';")
            except Exception:
                pass
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS perspective_impressions (
                        impression_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        perspective_id TEXT NOT NULL,
                        rater_salt TEXT NOT NULL,
                        cohort_val TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(perspective_id) REFERENCES perspectives(perspective_id) ON DELETE CASCADE,
                        UNIQUE(perspective_id, rater_salt)
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_perspectives_mod ON perspectives(question_id, moderation_status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_perspective_impressions_p ON perspective_impressions(perspective_id, cohort_val);")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspective_ratings ADD COLUMN rating_category TEXT DEFAULT 'HELPFUL_BRIDGE';")
            except Exception:
                pass
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS author_reputation (
                        rater_salt TEXT PRIMARY KEY,
                        active_abs REAL NOT NULL DEFAULT 0.0,
                        lifetime_peak_abs REAL NOT NULL DEFAULT 0.0,
                        bridging_b_index INTEGER NOT NULL DEFAULT 0,
                        calibration_karma REAL NOT NULL DEFAULT 0.0,
                        reputation_tier TEXT NOT NULL DEFAULT 'CITIZEN_DELIBERATOR',
                        tier_insignia TEXT NOT NULL DEFAULT 'Basalt Slate',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reputation_salt ON author_reputation(rater_salt);")
            except Exception:
                pass
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reputation_ledger (
                        entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rater_salt TEXT NOT NULL,
                        perspective_id TEXT,
                        event_type TEXT NOT NULL,
                        delta_amount REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(perspective_id) REFERENCES perspectives(perspective_id) ON DELETE SET NULL
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reputation_ledger_salt ON reputation_ledger(rater_salt);")
            except Exception:
                pass
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS bandit_arms (
                        arm_id TEXT PRIMARY KEY,
                        alpha REAL NOT NULL DEFAULT 1.0,
                        beta REAL NOT NULL DEFAULT 1.0,
                        pulls INTEGER NOT NULL DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sync_logs (
                        batch_id TEXT PRIMARY KEY,
                        rater_salt TEXT NOT NULL,
                        action_count INTEGER NOT NULL,
                        status TEXT NOT NULL DEFAULT 'SUCCESS',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE questions ADD COLUMN tier_mode TEXT DEFAULT 'MULTI_TIER';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE questions ADD COLUMN allowed_tiers TEXT DEFAULT '[1,2,3]';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE questions ADD COLUMN min_verification_tier INTEGER DEFAULT 1;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE questions ADD COLUMN is_multi_tier INTEGER DEFAULT 1;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE user_votes ADD COLUMN tier_level INTEGER DEFAULT 1;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE user_votes ADD COLUMN verification_sig TEXT DEFAULT NULL;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE user_votes ADD COLUMN verified_at TIMESTAMP DEFAULT NULL;")
            except Exception:
                pass
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS hex_tier_aggregates (
                        question_id TEXT NOT NULL,
                        h3_cell_id TEXT NOT NULL,
                        tier_level INTEGER NOT NULL DEFAULT 1,
                        choice_letter TEXT NOT NULL,
                        vote_count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY(question_id, h3_cell_id, tier_level, choice_letter),
                        FOREIGN KEY(question_id) REFERENCES questions(question_id) ON DELETE CASCADE
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_hex_tier_q ON hex_tier_aggregates(question_id, tier_level);")
            except Exception:
                pass
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_verifications (
                        rater_salt TEXT PRIMARY KEY,
                        current_tier INTEGER NOT NULL DEFAULT 1,
                        verification_method TEXT DEFAULT 'ANONYMOUS',
                        credential_id TEXT,
                        verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        reputation_weight REAL NOT NULL DEFAULT 1.0
                    );
                """)
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE questions ADD COLUMN canonical_url TEXT DEFAULT NULL;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE questions ADD COLUMN url_hash TEXT DEFAULT NULL;")
            except Exception:
                pass
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_url_hash ON questions(url_hash);")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN moral_lens TEXT DEFAULT 'AUTONOMY';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN in_group_helpful INTEGER NOT NULL DEFAULT 0;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN in_group_total INTEGER NOT NULL DEFAULT 0;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN out_group_helpful INTEGER NOT NULL DEFAULT 0;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE perspectives ADD COLUMN out_group_total INTEGER NOT NULL DEFAULT 0;")
            except Exception:
                pass
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS perspective_evaluations (
                        evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        perspective_id TEXT NOT NULL,
                        evaluator_salt TEXT NOT NULL,
                        evaluator_choice TEXT NOT NULL,
                        eval_type TEXT NOT NULL,
                        is_out_group INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(perspective_id) REFERENCES perspectives(perspective_id) ON DELETE CASCADE,
                        UNIQUE(perspective_id, evaluator_salt)
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_p ON perspective_evaluations(perspective_id, is_out_group);")
            except Exception:
                pass




    # -------------------------------------------------------------
    # Slates & Questions
    # -------------------------------------------------------------
    def create_slate(self, slate_id: str, release_date: str, title: str, is_active: int = 1) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO slates (slate_id, release_date, title, is_active) 
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(slate_id) DO UPDATE SET 
                       release_date = excluded.release_date,
                       title = excluded.title,
                       is_active = excluded.is_active;""",
                (slate_id, release_date, title, is_active),
            )

    def add_question(
        self, question_id: str, slate_id: str, order_idx: int, category: str, prompt: str
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO questions 
                   (question_id, slate_id, order_idx, category, prompt) 
                   VALUES (?, ?, ?, ?, ?);""",
                (question_id, slate_id, order_idx, category, prompt),
            )

    def add_choice(
        self,
        choice_id: str,
        question_id: str,
        letter: str,
        label: str,
        shape_symbol: str,
        color_hex: str,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO choices 
                   (choice_id, question_id, letter, label, shape_symbol, color_hex) 
                   VALUES (?, ?, ?, ?, ?, ?);""",
                (choice_id, question_id, letter, label, shape_symbol, color_hex),
            )

    def create_custom_plot(
        self,
        title: str,
        prompt: str,
        category: str = "CULTURE",
        domain: str = "CIVIC_TRUST",
        choices: Optional[List[Dict[str, Any]]] = None,
        canonical_url: Optional[str] = None,
        url_hash: Optional[str] = None,
        author_salt: Optional[str] = None,
        author_vote: Optional[str] = None,
        author_macro_region: Optional[str] = None,
        author_rationale: Optional[str] = None,
        author_moral_lens: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a custom dilemma from a URL or topic, seeds choices, founding vote, and initial rationale."""
        question_id = f"q_custom_{uuid.uuid4().hex[:8]}"
        slate_id = "slate_community_custom"

        # 1. Ensure community slate exists
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO slates (slate_id, day_number, release_date, title, is_active)
                   VALUES (?, 9999, '2099-12-31', 'Community Custom Plots', 1);""",
                (slate_id,),
            )

        # 2. Add question
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO questions
                   (question_id, slate_id, order_idx, category, domain, prompt, canonical_url, url_hash)
                   VALUES (?, ?, 1, ?, ?, ?, ?, ?);""",
                (question_id, slate_id, category, domain, prompt, canonical_url, url_hash),
            )

        # 3. Add 4 choices
        default_choices = [
            {"letter": "A", "label": "Prioritize Individual Sovereignty", "shape_symbol": "circle", "color_hex": "#C85A17"},
            {"letter": "B", "label": "Safeguard Communitarian Cohesion", "shape_symbol": "triangle", "color_hex": "#003153"},
            {"letter": "C", "label": "Contextual & Measured Compromise", "shape_symbol": "square", "color_hex": "#2E7D32"},
            {"letter": "D", "label": "Institutional Precedent & Stability", "shape_symbol": "diamond", "color_hex": "#8E24AA"},
        ]
        chosen_list = choices if choices and len(choices) >= 2 else default_choices
        for idx, c in enumerate(chosen_list[:4]):
            let = c.get("letter") or chr(65 + idx)
            lbl = c.get("label") or c.get("text") or f"Option {let}"
            sym = c.get("shape_symbol") or default_choices[idx]["shape_symbol"]
            col = c.get("color_hex") or default_choices[idx]["color_hex"]
            self.add_choice(
                choice_id=f"c_{question_id}_{let}",
                question_id=question_id,
                letter=let,
                label=lbl,
                shape_symbol=sym,
                color_hex=col,
            )

        # 4. Founding vote if cast
        if author_vote and author_vote in ("A", "B", "C", "D"):
            from atlas.geo.regions import get_h3_cell_for_region
            reg = author_macro_region or "WEST_EUROPE"
            cell = get_h3_cell_for_region(reg)
            self.record_tier_hex_vote(question_id, cell, author_vote, tier_level=1, increment=1)
            if author_salt:
                self.record_user_vote(author_salt, question_id, author_vote, reg, tier_level=1)

        # 5. Founding perspective if provided
        if author_rationale and author_vote and author_salt:
            lens = author_moral_lens or "AUTONOMY"
            pid = f"p_{uuid.uuid4().hex[:8]}"
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO perspectives
                       (perspective_id, question_id, choice_letter, body, author_salt,
                        author_macro_region, moral_lens, in_group_helpful, in_group_total, moderation_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 'APPROVED');""",
                    (pid, question_id, author_vote, author_rationale[:280], author_salt, author_macro_region or "WEST_EUROPE", lens),
                )

        return self.get_question(question_id)

    def lookup_plot_by_url(self, url_hash: str) -> Optional[Dict[str, Any]]:
        """Look up an existing question by canonical URL hash."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT question_id FROM questions WHERE url_hash = ? LIMIT 1;",
                (url_hash,),
            ).fetchone()
            if row:
                return self.get_question(row["question_id"])
        return None

    def get_active_slate(self, slate_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch the active slate and all of its questions and choices."""
        with self._get_connection() as conn:
            if slate_id:
                s_row = conn.execute(
                    "SELECT * FROM slates WHERE slate_id = ?;", (slate_id,)
                ).fetchone()
            else:
                s_row = conn.execute(
                    "SELECT * FROM slates WHERE is_active = 1 ORDER BY release_date DESC LIMIT 1;"
                ).fetchone()

            if not s_row:
                return None

            slate_dict = dict(s_row)
            q_rows = conn.execute(
                "SELECT * FROM questions WHERE slate_id = ? ORDER BY order_idx ASC;",
                (slate_dict["slate_id"],),
            ).fetchall()

            questions = []
            for qr in q_rows:
                q_dict = dict(qr)
                c_rows = conn.execute(
                    "SELECT * FROM choices WHERE question_id = ? ORDER BY letter ASC;",
                    (q_dict["question_id"],),
                ).fetchall()
                q_dict["choices"] = [dict(cr) for cr in c_rows]
                questions.append(q_dict)

            slate_dict["questions"] = questions
            return slate_dict

    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific question and its choices."""
        with self._get_connection() as conn:
            q_row = conn.execute(
                "SELECT * FROM questions WHERE question_id = ?;", (question_id,)
            ).fetchone()
            if not q_row:
                return None
            q_dict = dict(q_row)
            c_rows = conn.execute(
                "SELECT * FROM choices WHERE question_id = ? ORDER BY letter ASC;",
                (question_id,),
            ).fetchall()
            q_dict["choices"] = [dict(cr) for cr in c_rows]
            return q_dict

    def get_all_candidate_questions(self) -> List[Dict[str, Any]]:
        """Returns all questions with choices and metadata for discovery routing."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT q.question_id, q.slate_id, q.order_idx, q.category, q.prompt, s.title as slate_title
                FROM questions q
                LEFT JOIN slates s ON q.slate_id = s.slate_id
                ORDER BY q.slate_id ASC, q.order_idx ASC;
            """).fetchall()

            # Pre-fetch all choices mapped by question_id
            choice_rows = conn.execute("SELECT question_id, letter, label FROM choices ORDER BY letter ASC;").fetchall()
            choices_by_q = {}
            for cr in choice_rows:
                qid = cr["question_id"]
                if qid not in choices_by_q:
                    choices_by_q[qid] = []
                choices_by_q[qid].append({"letter": cr["letter"], "text": cr["label"]})

            result = []
            for r in rows:
                qid = r["question_id"]
                day_num = 1
                if "_" in r["slate_id"]:
                    try:
                        day_num = int(r["slate_id"].split("_")[-1])
                    except ValueError:
                        day_num = 1

                q_choices = choices_by_q.get(qid, [])
                gt = self.get_question_ground_truth(qid)
                dist = [
                    int(round(gt.get("A", 0.25) * 100)),
                    int(round(gt.get("B", 0.25) * 100)),
                    int(round(gt.get("C", 0.25) * 100)),
                    int(round(gt.get("D", 0.25) * 100)),
                ]

                result.append({
                    "id": qid,
                    "question_id": qid,
                    "slate_id": r["slate_id"],
                    "day_number": day_num,
                    "step_index": r["order_idx"],
                    "category": r["category"],
                    "prompt": r["prompt"],
                    "slate_title": r["slate_title"],
                    "choices": q_choices,
                    "baseline_dist": dist,
                })
            return result

    # -------------------------------------------------------------
    # Spatial Hex Aggregates
    # -------------------------------------------------------------
    def record_hex_vote(
        self, question_id: str, h3_cell_id: str, choice_letter: str, increment: int = 1
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO hex_aggregates (question_id, h3_cell_id, choice_letter, vote_count)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(question_id, h3_cell_id, choice_letter) 
                   DO UPDATE SET vote_count = vote_count + ?;""",
                (question_id, h3_cell_id, choice_letter, increment, increment),
            )

    def get_cell_distribution(self, question_id: str, h3_cell_id: str) -> Dict[str, int]:
        """Return {choice_letter: vote_count} for a given question and cell."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT choice_letter, vote_count FROM hex_aggregates 
                   WHERE question_id = ? AND h3_cell_id = ?;""",
                (question_id, h3_cell_id),
            ).fetchall()
        return {r["choice_letter"]: r["vote_count"] for r in rows}

    def get_cell_total_votes(self, question_id: str, h3_cell_id: str) -> int:
        """Return total votes recorded in a cell across all choices."""
        dist = self.get_cell_distribution(question_id, h3_cell_id)
        return sum(dist.values())

    def get_all_hex_aggregates(self, question_id: str) -> List[Dict[str, Any]]:
        """Return all hex aggregates for a question."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT h3_cell_id, choice_letter, vote_count 
                   FROM hex_aggregates WHERE question_id = ?;""",
                (question_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def record_tier_hex_vote(
        self, question_id: str, h3_cell_id: str, choice_letter: str, tier_level: int = 1, increment: int = 1
    ) -> None:
        """Records a vote in tier-partitioned spatial aggregates and updates global hex_aggregates."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO hex_tier_aggregates (question_id, h3_cell_id, tier_level, choice_letter, vote_count)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(question_id, h3_cell_id, tier_level, choice_letter) 
                   DO UPDATE SET vote_count = vote_count + ?;""",
                (question_id, h3_cell_id, tier_level, choice_letter, increment, increment),
            )
            # Synchronize to global hex_aggregates
            conn.execute(
                """INSERT INTO hex_aggregates (question_id, h3_cell_id, choice_letter, vote_count)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(question_id, h3_cell_id, choice_letter) 
                   DO UPDATE SET vote_count = vote_count + ?;""",
                (question_id, h3_cell_id, choice_letter, increment, increment),
            )

    def get_tier_hex_aggregates(self, question_id: str, min_tier: int = 1) -> List[Dict[str, Any]]:
        """Return hex aggregates for a question filtered by minimum verification tier."""
        with self._get_connection() as conn:
            if min_tier <= 1:
                rows = conn.execute(
                    """SELECT h3_cell_id, choice_letter, vote_count 
                       FROM hex_aggregates WHERE question_id = ?;""",
                    (question_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT h3_cell_id, choice_letter, SUM(vote_count) as vote_count 
                       FROM hex_tier_aggregates 
                       WHERE question_id = ? AND tier_level >= ?
                       GROUP BY h3_cell_id, choice_letter;""",
                    (question_id, min_tier),
                ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------
    # Perspectives & Ratings (Bridging Consensus)
    # -------------------------------------------------------------
    def add_perspective(
        self,
        perspective_id: str,
        question_id: str,
        choice_letter: str,
        body: str,
        author_salt: str,
        author_generation: str = "UNSPECIFIED",
        author_urbanicity: str = "UNSPECIFIED",
        author_macro_region: str = "UNSPECIFIED",
        moderation_status: str = "APPROVED",
        moderation_flags: str = "",
        moral_lens: str = "AUTONOMY",
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO perspectives 
                   (perspective_id, question_id, choice_letter, body, author_salt,
                    author_generation, author_urbanicity, author_macro_region,
                    moderation_status, moderation_flags, moral_lens)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    perspective_id,
                    question_id,
                    choice_letter,
                    body,
                    author_salt,
                    author_generation,
                    author_urbanicity,
                    author_macro_region,
                    moderation_status,
                    moderation_flags,
                    moral_lens,
                ),
            )

    def create_community_perspective(
        self,
        question_id: str,
        choice_letter: str,
        body: str,
        author_salt: str,
        author_generation: str = "UNSPECIFIED",
        author_urbanicity: str = "UNSPECIFIED",
        author_macro_region: str = "UNSPECIFIED",
        moderation_status: str = "APPROVED",
        moderation_flags: str = "",
        moral_lens: str = "AUTONOMY",
    ) -> str:
        """Generates unique perspective_id, saves community submission, and returns the id."""
        perspective_id = f"p_{uuid.uuid4().hex[:8]}"
        self.add_perspective(
            perspective_id=perspective_id,
            question_id=question_id,
            choice_letter=choice_letter,
            body=body,
            author_salt=author_salt,
            author_generation=author_generation,
            author_urbanicity=author_urbanicity,
            author_macro_region=author_macro_region,
            moderation_status=moderation_status,
            moderation_flags=moderation_flags,
            moral_lens=moral_lens,
        )
        return perspective_id

    def rate_perspective(
        self,
        perspective_id: str,
        rater_salt: str,
        rating_score: float,
        rater_generation: Optional[str] = None,
        rater_urbanicity: Optional[str] = None,
        rating_category: str = "HELPFUL_BRIDGE",
    ) -> None:
        gen = rater_generation
        urb = rater_urbanicity
        if not gen or not urb or gen == "UNSPECIFIED" or urb == "UNSPECIFIED":
            demo = self.get_user_demographics(rater_salt)
            if not gen or gen == "UNSPECIFIED":
                gen = demo.get("generation_cohort", "UNSPECIFIED")
            if not urb or urb == "UNSPECIFIED":
                urb = demo.get("urbanicity", "UNSPECIFIED")

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO perspective_ratings 
                   (perspective_id, rater_salt, rating_score, rating_category, rater_generation, rater_urbanicity)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(perspective_id, rater_salt) 
                   DO UPDATE SET 
                       rating_score = excluded.rating_score,
                       rating_category = excluded.rating_category,
                       rater_generation = CASE WHEN excluded.rater_generation != 'UNSPECIFIED' THEN excluded.rater_generation ELSE perspective_ratings.rater_generation END,
                       rater_urbanicity = CASE WHEN excluded.rater_urbanicity != 'UNSPECIFIED' THEN excluded.rater_urbanicity ELSE perspective_ratings.rater_urbanicity END;""",
                (perspective_id, rater_salt, rating_score, rating_category, gen, urb),
            )

    def save_user_demographics(
        self,
        rater_salt: str,
        generation_cohort: str = "UNSPECIFIED",
        urbanicity: str = "UNSPECIFIED",
        macro_region: str = "UNSPECIFIED",
    ) -> None:
        """Saves user demographic self-identification and backfills past ratings."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO user_demographics (rater_salt, generation_cohort, urbanicity, macro_region, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(rater_salt) DO UPDATE SET
                       generation_cohort = excluded.generation_cohort,
                       urbanicity = excluded.urbanicity,
                       macro_region = excluded.macro_region,
                       updated_at = CURRENT_TIMESTAMP;""",
                (rater_salt, generation_cohort, urbanicity, macro_region),
            )
            if generation_cohort != "UNSPECIFIED":
                conn.execute(
                    """UPDATE perspective_ratings 
                       SET rater_generation = ? 
                       WHERE rater_salt = ? AND (rater_generation = 'UNSPECIFIED' OR rater_generation IS NULL);""",
                    (generation_cohort, rater_salt),
                )
            if urbanicity != "UNSPECIFIED":
                conn.execute(
                    """UPDATE perspective_ratings 
                       SET rater_urbanicity = ? 
                       WHERE rater_salt = ? AND (rater_urbanicity = 'UNSPECIFIED' OR rater_urbanicity IS NULL);""",
                    (urbanicity, rater_salt),
                )

    def get_user_demographics(self, rater_salt: str) -> Dict[str, str]:
        """Retrieves user demographic profile."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT generation_cohort, urbanicity, macro_region 
                   FROM user_demographics WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchone()
        if row:
            return {
                "rater_salt": rater_salt,
                "generation_cohort": row["generation_cohort"] or "UNSPECIFIED",
                "urbanicity": row["urbanicity"] or "UNSPECIFIED",
                "macro_region": row["macro_region"] or "UNSPECIFIED",
            }
        return {
            "rater_salt": rater_salt,
            "generation_cohort": "UNSPECIFIED",
            "urbanicity": "UNSPECIFIED",
            "macro_region": "UNSPECIFIED",
        }

    def get_perspective_cohort_ratings(
        self, question_id: str, cohort_axis: str = "generation"
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Aggregates perspective ratings grouped by demographic cohort.
        Returns: { perspective_id: { cohort_value: { 'total_ratings': int, 'helpful_ratings': int, 'helpful_pct': float } } }
        """
        if cohort_axis in ("urbanicity", "rater_urbanicity"):
            col_name = "pr.rater_urbanicity"
        elif cohort_axis in ("macro_region", "region"):
            col_name = "COALESCE(ud.macro_region, 'UNSPECIFIED')"
        else:
            col_name = "pr.rater_generation"

        with self._get_connection() as conn:
            sql = f"""
                SELECT pr.perspective_id,
                       {col_name} as cohort_val,
                       COUNT(pr.rating_id) as total_ratings,
                       COALESCE(SUM(CASE WHEN pr.rating_score >= 0.5 THEN 1 ELSE 0 END), 0) as helpful_ratings
                FROM perspective_ratings pr
                JOIN perspectives p ON pr.perspective_id = p.perspective_id
                LEFT JOIN user_demographics ud ON pr.rater_salt = ud.rater_salt
                WHERE p.question_id = ? AND {col_name} != 'UNSPECIFIED' AND {col_name} IS NOT NULL
                GROUP BY pr.perspective_id, cohort_val;
            """
            rows = conn.execute(sql, (question_id,)).fetchall()

        result: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for r in rows:
            pid = r["perspective_id"]
            c_val = r["cohort_val"]
            tot = int(r["total_ratings"])
            hlp = int(r["helpful_ratings"])
            pct = round(hlp / tot, 3) if tot > 0 else 0.0
            if pid not in result:
                result[pid] = {}
            result[pid][c_val] = {
                "total_ratings": tot,
                "helpful_ratings": hlp,
                "helpful_pct": pct,
            }
        return result

    def get_all_ratings_for_question(
        self, question_id: str
    ) -> List[Tuple[str, str, float]]:
        """Return list of (rater_salt, perspective_id, rating_score) for bridging model fit."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT pr.rater_salt, pr.perspective_id, pr.rating_score
                   FROM perspective_ratings pr
                   JOIN perspectives p ON pr.perspective_id = p.perspective_id
                   WHERE p.question_id = ?;""",
                (question_id,),
            ).fetchall()
        return [(r["rater_salt"], r["perspective_id"], float(r["rating_score"])) for r in rows]

    def get_perspectives_for_question(self, question_id: str) -> List[Dict[str, Any]]:
        """Return perspectives for a question with rating statistics, filtering approved only."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT p.perspective_id, p.question_id, p.choice_letter, p.body, p.author_salt,
                          COALESCE(p.author_generation, 'UNSPECIFIED') as author_generation,
                          COALESCE(p.author_urbanicity, 'UNSPECIFIED') as author_urbanicity,
                          COALESCE(p.author_macro_region, 'UNSPECIFIED') as author_macro_region,
                          COALESCE(p.moderation_status, 'APPROVED') as moderation_status,
                          p.created_at,
                          COUNT(pr.rating_id) as total_ratings,
                          COALESCE(SUM(CASE WHEN pr.rating_score >= 0.5 THEN 1 ELSE 0 END), 0) as helpful_ratings
                   FROM perspectives p
                   LEFT JOIN perspective_ratings pr ON p.perspective_id = pr.perspective_id
                   WHERE p.question_id = ? AND (p.moderation_status = 'APPROVED' OR p.moderation_status IS NULL)
                   GROUP BY p.perspective_id
                   ORDER BY helpful_ratings DESC, p.created_at ASC;""",
                (question_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_perspectives_by_stance(
        self, question_id: str, viewer_stance: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Partitions perspectives into 4 stance bays (A, B, C, D) with
        Two-Sided Mutual Ratification math (in-group legitimacy + out-group steelman approval)
        and identifies the sacred bridging perspective for each bay.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT p.perspective_id, p.question_id, p.choice_letter, p.body, p.author_salt,
                          COALESCE(p.author_generation, 'UNSPECIFIED') as author_generation,
                          COALESCE(p.author_urbanicity, 'UNSPECIFIED') as author_urbanicity,
                          COALESCE(p.author_macro_region, 'WEST_EUROPE') as author_macro_region,
                          COALESCE(p.moral_lens, 'AUTONOMY') as moral_lens,
                          COALESCE(p.in_group_helpful, 0) as in_group_helpful,
                          COALESCE(p.in_group_total, 0) as in_group_total,
                          COALESCE(p.out_group_helpful, 0) as out_group_helpful,
                          COALESCE(p.out_group_total, 0) as out_group_total,
                          COALESCE(p.moderation_status, 'APPROVED') as moderation_status,
                          p.created_at
                   FROM perspectives p
                   WHERE p.question_id = ? AND (p.moderation_status = 'APPROVED' OR p.moderation_status IS NULL)
                   ORDER BY p.created_at ASC;""",
                (question_id,),
            ).fetchall()

        bays: Dict[str, Dict[str, Any]] = {
            "A": {"choice_letter": "A", "total": 0, "perspectives": [], "bridging_perspective": None},
            "B": {"choice_letter": "B", "total": 0, "perspectives": [], "bridging_perspective": None},
            "C": {"choice_letter": "C", "total": 0, "perspectives": [], "bridging_perspective": None},
            "D": {"choice_letter": "D", "total": 0, "perspectives": [], "bridging_perspective": None},
        }

        region_to_city = {
            "US_WEST": "San Francisco",
            "US_EAST": "New York",
            "CANADA": "Toronto",
            "MEXICO": "Mexico City",
            "BRAZIL": "São Paulo",
            "SOUTHERN_CONE": "Buenos Aires",
            "UK_IRELAND": "London",
            "WEST_EUROPE": "Berlin",
            "SOUTH_EUROPE": "Rome",
            "NORDICS": "Stockholm",
            "EAST_EUROPE": "Warsaw",
            "NORTH_AFRICA": "Cairo",
            "SUB_SAHARAN_AFRICA": "Nairobi",
            "SOUTH_AFRICA": "Cape Town",
            "MIDDLE_EAST": "Dubai",
            "CENTRAL_ASIA": "Almaty",
            "SOUTH_ASIA": "Mumbai",
            "EAST_ASIA": "Tokyo",
            "SOUTHEAST_ASIA": "Singapore",
            "OCEANIA": "Sydney",
        }

        for r in rows:
            item = dict(r)
            letter = item["choice_letter"].upper()
            if letter not in bays:
                continue

            in_h = item["in_group_helpful"]
            in_t = item["in_group_total"]
            out_h = item["out_group_helpful"]
            out_t = item["out_group_total"]

            in_cohesion = (in_h + 1.0) / (in_t + 2.0)
            out_approval = (out_h + 1.0) / (out_t + 2.0)
            is_ratified = in_cohesion >= 0.60
            bridging_score = 2.0 * (out_approval * in_cohesion) / (out_approval + in_cohesion + 0.001)

            reg = item["author_macro_region"]
            city = region_to_city.get(reg, "Global Centroid")
            item["city_centroid"] = city
            item["in_cohesion"] = round(in_cohesion, 2)
            item["out_approval"] = round(out_approval, 2)
            item["is_ratified"] = is_ratified
            item["bridging_score"] = round(bridging_score, 3)
            item["is_sacred_bridge"] = False

            bays[letter]["perspectives"].append(item)
            bays[letter]["total"] += 1

        for letter, bay in bays.items():
            plist = bay["perspectives"]
            if not plist:
                continue

            plist.sort(key=lambda x: (x["is_ratified"], x["bridging_score"], x["out_approval"]), reverse=True)
            best = plist[0]
            best["is_sacred_bridge"] = True
            bay["bridging_perspective"] = best

        return {
            "question_id": question_id,
            "viewer_stance": viewer_stance,
            "bays": bays
        }

    def rate_perspective_coherence(
        self,
        perspective_id: str,
        rater_salt: str,
        rater_choice: str,
        eval_type: str = "FAIR_STEELMAN"
    ) -> Dict[str, Any]:
        """
        Records a coherence rating (FAIR_STEELMAN, NUANCED_TRADEOFF, UNSUBSTANTIATED)
        and updates the mutual ratification tallies.
        """
        eval_type = eval_type.upper()
        if eval_type not in ("FAIR_STEELMAN", "NUANCED_TRADEOFF", "UNSUBSTANTIATED"):
            eval_type = "FAIR_STEELMAN"

        with self._get_connection() as conn:
            p_row = conn.execute(
                "SELECT perspective_id, choice_letter FROM perspectives WHERE perspective_id = ?;",
                (perspective_id,)
            ).fetchone()
            if not p_row:
                return {"status": "error", "message": "Perspective not found"}

            p_choice = p_row["choice_letter"]
            is_out_group = 1 if (rater_choice and rater_choice != p_choice) else 0

            conn.execute(
                """INSERT INTO perspective_evaluations
                   (perspective_id, evaluator_salt, evaluator_choice, eval_type, is_out_group, created_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(perspective_id, evaluator_salt) DO UPDATE SET
                       evaluator_choice = excluded.evaluator_choice,
                       eval_type = excluded.eval_type,
                       is_out_group = excluded.is_out_group;""",
                (perspective_id, rater_salt, rater_choice, eval_type, is_out_group)
            )

            # Re-aggregate counts
            in_h = conn.execute(
                """SELECT COUNT(*) FROM perspective_evaluations
                   WHERE perspective_id = ? AND is_out_group = 0 AND eval_type IN ('FAIR_STEELMAN', 'NUANCED_TRADEOFF');""",
                (perspective_id,)
            ).fetchone()[0]
            in_t = conn.execute(
                "SELECT COUNT(*) FROM perspective_evaluations WHERE perspective_id = ? AND is_out_group = 0;",
                (perspective_id,)
            ).fetchone()[0]
            out_h = conn.execute(
                """SELECT COUNT(*) FROM perspective_evaluations
                   WHERE perspective_id = ? AND is_out_group = 1 AND eval_type IN ('FAIR_STEELMAN', 'NUANCED_TRADEOFF');""",
                (perspective_id,)
            ).fetchone()[0]
            out_t = conn.execute(
                "SELECT COUNT(*) FROM perspective_evaluations WHERE perspective_id = ? AND is_out_group = 1;",
                (perspective_id,)
            ).fetchone()[0]

            conn.execute(
                """UPDATE perspectives SET
                   in_group_helpful = ?,
                   in_group_total = ?,
                   out_group_helpful = ?,
                   out_group_total = ?
                   WHERE perspective_id = ?;""",
                (in_h, in_t, out_h, out_t, perspective_id)
            )

        return {
            "status": "ok",
            "perspective_id": perspective_id,
            "eval_type": eval_type,
            "is_out_group": bool(is_out_group),
            "in_group_helpful": in_h,
            "in_group_total": in_t,
            "out_group_helpful": out_h,
            "out_group_total": out_t
        }

    def record_perspective_impression(
        self, perspective_id: str, rater_salt: str, cohort_val: str
    ) -> None:
        """Records that a perspective was exposed to rater_salt in cohort_val."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO perspective_impressions (perspective_id, rater_salt, cohort_val)
                   VALUES (?, ?, ?)
                   ON CONFLICT(perspective_id, rater_salt) DO NOTHING;""",
                (perspective_id, rater_salt, cohort_val),
            )

    def get_cold_start_review_queue(
        self,
        question_id: str,
        rater_salt: str,
        rater_cohort_val: str = "UNSPECIFIED",
        limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves up to `limit` perspectives needing calibration ratings.
        Excludes perspectives authored or already rated by rater_salt.
        Prioritizes items with lowest impressions in rater_cohort_val.
        Fixes the cold-start review queue depletion bug by filtering on cohort evaluation depth.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT p.perspective_id, p.question_id, p.choice_letter, p.body,
                          COALESCE(p.author_generation, 'UNSPECIFIED') as author_generation,
                          COALESCE(p.author_urbanicity, 'UNSPECIFIED') as author_urbanicity,
                          COALESCE(p.author_macro_region, 'UNSPECIFIED') as author_macro_region,
                          p.created_at,
                          COUNT(pr.rating_id) as total_ratings,
                          (SELECT COUNT(*) FROM perspective_impressions pi 
                           WHERE pi.perspective_id = p.perspective_id AND pi.cohort_val = ?) as cohort_impressions,
                          (SELECT COUNT(*) FROM perspective_ratings pr_c
                           WHERE pr_c.perspective_id = p.perspective_id 
                             AND (pr_c.rater_generation = ? OR ? = 'UNSPECIFIED')) as cohort_ratings
                   FROM perspectives p
                   LEFT JOIN perspective_ratings pr ON p.perspective_id = pr.perspective_id
                   WHERE p.question_id = ?
                     AND (p.moderation_status = 'APPROVED' OR p.moderation_status IS NULL)
                     AND p.author_salt != ?
                     AND p.perspective_id NOT IN (
                         SELECT perspective_id FROM perspective_ratings WHERE rater_salt = ?
                     )
                   GROUP BY p.perspective_id
                   ORDER BY (CASE WHEN cohort_ratings < 5 THEN 0 ELSE 1 END) ASC,
                            cohort_impressions ASC, cohort_ratings ASC, p.created_at ASC
                   LIMIT ?;""",
                (rater_cohort_val, rater_cohort_val, rater_cohort_val, question_id, rater_salt, rater_salt, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_user_reputation(self, rater_salt: str) -> Dict[str, Any]:
        """Retrieves an author or rater's reputation record."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT rater_salt, active_abs, lifetime_peak_abs, bridging_b_index,
                          calibration_karma, reputation_tier, tier_insignia, updated_at
                   FROM author_reputation WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchone()
        if row:
            tier_labels = {
                "CITIZEN_DELIBERATOR": "Citizen Deliberator",
                "CONSENSUS_BUILDER": "Consensus Builder",
                "CULTURAL_DIPLOMAT": "Cultural Diplomat",
                "SACRED_ARBITER": "Sacred Arbiter",
            }
            tier = row["reputation_tier"] or "CITIZEN_DELIBERATOR"
            return {
                "rater_salt": rater_salt,
                "active_abs": float(row["active_abs"]),
                "lifetime_peak_abs": float(row["lifetime_peak_abs"]),
                "bridging_b_index": int(row["bridging_b_index"]),
                "calibration_karma": round(float(row["calibration_karma"]), 2),
                "reputation_tier": tier,
                "tier_insignia": row["tier_insignia"] or "Basalt Slate",
                "tier_label": tier_labels.get(tier, "Citizen Deliberator"),
                "updated_at": row["updated_at"],
            }
        return {
            "rater_salt": rater_salt,
            "active_abs": 0.0,
            "lifetime_peak_abs": 0.0,
            "bridging_b_index": 0,
            "calibration_karma": 0.0,
            "reputation_tier": "CITIZEN_DELIBERATOR",
            "tier_insignia": "Basalt Slate",
            "tier_label": "Citizen Deliberator",
            "updated_at": None,
        }

    def record_reputation_event(
        self,
        rater_salt: str,
        perspective_id: Optional[str],
        event_type: str,
        delta_amount: float,
    ) -> None:
        """Records an auditable entry in the reputation ledger."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO reputation_ledger (rater_salt, perspective_id, event_type, delta_amount)
                   VALUES (?, ?, ?, ?);""",
                (rater_salt, perspective_id, event_type, delta_amount),
            )

    def update_author_reputation(self, author_salt: str) -> Dict[str, Any]:
        """
        Recomputes Author Bridging Score ($ABS$) and tier across all authored perspectives.
        Saves result to author_reputation table and returns reputation profile.
        """
        from atlas.algorithms.bridging_economy import (
            calculate_author_bridging_score,
            calculate_perspective_bridging_capital,
            PerspectiveRatingInput,
        )

        with self._get_connection() as conn:
            perspectives = conn.execute(
                """SELECT p.perspective_id, p.choice_letter, p.created_at,
                          julianday('now') - julianday(p.created_at) as age_days
                   FROM perspectives p
                   WHERE p.author_salt = ?;""",
                (author_salt,),
            ).fetchall()

            if not perspectives:
                needs_fallback = True
            else:
                needs_fallback = False
                curr = conn.execute(
                    """SELECT lifetime_peak_abs, calibration_karma FROM author_reputation WHERE rater_salt = ?;""",
                    (author_salt,),
                ).fetchone()
                lifetime_peak = float(curr["lifetime_peak_abs"]) if curr else 0.0
                karma = float(curr["calibration_karma"]) if curr else 0.0

                authored_payload = []
                for p in perspectives:
                    pid = p["perspective_id"]
                    stance = p["choice_letter"]
                    age = float(p["age_days"] or 0.0)

                    ratings_rows = conn.execute(
                        """SELECT pr.rater_salt, COALESCE(pr.rater_generation, 'UNSPECIFIED') as rater_generation,
                                  COALESCE(uv.choice_letter, 'UNSPECIFIED') as rater_stance,
                                  COALESCE(pr.rating_category, 'HELPFUL_BRIDGE') as rating_category
                           FROM perspective_ratings pr
                           LEFT JOIN user_votes uv ON pr.rater_salt = uv.rater_salt
                           WHERE pr.perspective_id = ?;""",
                        (pid,),
                    ).fetchall()

                    ratings_gen_z = []
                    ratings_boomer = []
                    for r in ratings_rows:
                        item = PerspectiveRatingInput(
                            rater_salt=r["rater_salt"],
                            rater_cohort=r["rater_generation"],
                            rater_stance=r["rater_stance"],
                            rating_category=r["rating_category"],
                        )
                        if r["rater_generation"] == "GEN_Z":
                            ratings_gen_z.append(item)
                        elif r["rater_generation"] in ("BOOMER_PLUS", "GEN_X"):
                            ratings_boomer.append(item)

                    yield_res = calculate_perspective_bridging_capital(
                        perspective_id=pid,
                        perspective_stance=stance,
                        ratings_cohort_a=ratings_gen_z,
                        ratings_cohort_b=ratings_boomer,
                    )
                    is_echo = (yield_res.polarization_delta >= 0.35 and yield_res.conservative_bridge < 0.30)

                    authored_payload.append({
                        "bc_yield": yield_res.bc_yield,
                        "is_echo": is_echo,
                        "age_days": age,
                    })

                rep_res = calculate_author_bridging_score(
                    authored_perspectives=authored_payload,
                    lifetime_peak_abs=lifetime_peak,
                )

                conn.execute(
                    """INSERT INTO author_reputation 
                       (rater_salt, active_abs, lifetime_peak_abs, bridging_b_index, calibration_karma, reputation_tier, tier_insignia, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(rater_salt) DO UPDATE SET
                           active_abs = excluded.active_abs,
                           lifetime_peak_abs = excluded.lifetime_peak_abs,
                           bridging_b_index = excluded.bridging_b_index,
                           reputation_tier = excluded.reputation_tier,
                           tier_insignia = excluded.tier_insignia,
                           updated_at = CURRENT_TIMESTAMP;""",
                    (author_salt, rep_res.active_abs, rep_res.lifetime_peak_abs, rep_res.bridging_b_index, karma, rep_res.reputation_tier, rep_res.tier_insignia),
                )

        return self.get_user_reputation(author_salt)

    def get_review_deck(
        self,
        question_id: str,
        viewer_salt: str,
        viewer_generation: str = "UNSPECIFIED",
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves an interactive 3-card calibration review deck.
        Prioritizes items authored by other cohorts and not yet rated by viewer.
        """
        candidates = self.get_cold_start_review_queue(
            question_id=question_id,
            rater_salt=viewer_salt,
            rater_cohort_val=viewer_generation,
            limit=limit * 2,
        )
        results = []
        for c in candidates:
            self.record_perspective_impression(
                perspective_id=c["perspective_id"],
                rater_salt=viewer_salt,
                cohort_val=viewer_generation,
            )
            results.append({
                "perspective_id": c["perspective_id"],
                "question_id": c["question_id"],
                "choice_letter": c["choice_letter"],
                "body": c["body"],
                "author_generation": c.get("author_generation", "UNSPECIFIED"),
                "author_urbanicity": c.get("author_urbanicity", "UNSPECIFIED"),
                "author_macro_region": c.get("author_macro_region", "UNSPECIFIED"),
                "total_ratings": c.get("total_ratings", 0),
                "karma_reward": 0.50,
            })
            if len(results) >= limit:
                break
        return results

    def rate_deck_item(
        self,
        perspective_id: str,
        rater_salt: str,
        rating_category: str,
        rater_generation: str = "UNSPECIFIED",
        rater_urbanicity: str = "UNSPECIFIED",
    ) -> Dict[str, Any]:
        """
        Ingests a multi-dimensional perspective evaluation from the review deck,
        calculates peer-predictive karma, updates reviewer karma and author reputation.
        """
        from atlas.algorithms.bridging_economy import calculate_rater_karma_delta

        category_scores = {
            "HELPFUL_BRIDGE": 1.0,
            "INFORMATIVE": 0.8,
            "ECHO_ONLY": 0.2,
            "UNHELPFUL": 0.0,
        }
        score = category_scores.get(rating_category, 1.0)

        self.rate_perspective(
            perspective_id=perspective_id,
            rater_salt=rater_salt,
            rating_score=score,
            rater_generation=rater_generation,
            rater_urbanicity=rater_urbanicity,
            rating_category=rating_category,
        )

        with self._get_connection() as conn:
            persp = conn.execute(
                """SELECT question_id, choice_letter, author_salt FROM perspectives WHERE perspective_id = ?;""",
                (perspective_id,),
            ).fetchone()
            if not persp:
                return {"status": "ok", "karma_awarded": 0.50}

            persp_stance = persp["choice_letter"]
            author_salt = persp["author_salt"]
            qid = persp["question_id"]

            vote_row = conn.execute(
                """SELECT choice_letter FROM user_votes WHERE rater_salt = ? AND question_id = ?;""",
                (rater_salt, qid),
            ).fetchone()
            rater_stance = vote_row["choice_letter"] if vote_row else "UNSPECIFIED"

            calib_row = conn.execute(
                """SELECT calibration_index FROM calibration_guesses WHERE rater_salt = ? ORDER BY created_at DESC LIMIT 1;""",
                (rater_salt,),
            ).fetchone()
            rater_cci = int(calib_row["calibration_index"]) if calib_row else 500

        cohort_ratings = self.get_perspective_cohort_ratings(qid, "generation")
        stats = cohort_ratings.get(perspective_id, {})
        z_stats = stats.get("GEN_Z", {})
        b_stats = stats.get("BOOMER_PLUS", stats.get("GEN_X", {}))
        w_a = z_stats.get("helpful_pct", 0.50)
        w_b = b_stats.get("helpful_pct", 0.50)

        karma_delta = calculate_rater_karma_delta(
            rating_category=rating_category,
            rater_stance=rater_stance,
            perspective_stance=persp_stance,
            cohort_a_lower=w_a,
            cohort_b_lower=w_b,
            rater_cci=rater_cci,
        )

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO author_reputation (rater_salt, calibration_karma)
                   VALUES (?, ?)
                   ON CONFLICT(rater_salt) DO UPDATE SET
                       calibration_karma = author_reputation.calibration_karma + excluded.calibration_karma,
                       updated_at = CURRENT_TIMESTAMP;""",
                (rater_salt, karma_delta),
            )
            conn.execute(
                """INSERT INTO reputation_ledger (rater_salt, perspective_id, event_type, delta_amount)
                   VALUES (?, ?, ?, ?);""",
                (rater_salt, perspective_id, "KARMA_AWARD", karma_delta),
            )

        author_rep = self.update_author_reputation(author_salt)
        rater_rep = self.get_user_reputation(rater_salt)

        return {
            "status": "ok",
            "perspective_id": perspective_id,
            "rating_category": rating_category,
            "karma_awarded": karma_delta,
            "total_karma": rater_rep["calibration_karma"],
            "rater_tier": rater_rep["reputation_tier"],
            "author_tier": author_rep["reputation_tier"],
            "author_tier_insignia": author_rep["tier_insignia"],
        }

    # -------------------------------------------------------------
    # Cultural Calibration Guesses (Epistemic Game)
    # -------------------------------------------------------------
    def record_calibration_guess(
        self,
        guess_id: str,
        question_id: str,
        rater_salt: str,
        pred_a: float,
        pred_b: float,
        pred_c: float,
        pred_d: float,
        brier_score: float,
        calibration_index: int,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO calibration_guesses 
                   (guess_id, question_id, rater_salt, pred_a, pred_b, pred_c, pred_d, brier_score, calibration_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(question_id, rater_salt) DO UPDATE SET
                       pred_a = excluded.pred_a,
                       pred_b = excluded.pred_b,
                       pred_c = excluded.pred_c,
                       pred_d = excluded.pred_d,
                       brier_score = excluded.brier_score,
                       calibration_index = excluded.calibration_index;""",
                (guess_id, question_id, rater_salt, pred_a, pred_b, pred_c, pred_d, brier_score, calibration_index),
            )

    def get_calibration_guess(self, question_id: str, rater_salt: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user's calibration guess for a question."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM calibration_guesses 
                   WHERE question_id = ? AND rater_salt = ?;""",
                (question_id, rater_salt),
            ).fetchone()
        return dict(row) if row else None

    def get_question_ground_truth(self, question_id: str) -> Dict[str, float]:
        """Compute the empirical ground-truth global distribution for a question."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT choice_letter, SUM(vote_count) as total_v
                   FROM hex_aggregates
                   WHERE question_id = ?
                   GROUP BY choice_letter;""",
                (question_id,),
            ).fetchall()

        counts = {r["choice_letter"]: int(r["total_v"]) for r in rows}
        total = sum(counts.values())
        if total <= 0:
            return {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25}

        return {
            "A": round(counts.get("A", 0) / total, 3),
            "B": round(counts.get("B", 0) / total, 3),
            "C": round(counts.get("C", 0) / total, 3),
            "D": max(0.0, round(1.0 - (round(counts.get("A", 0) / total, 3) + round(counts.get("B", 0) / total, 3) + round(counts.get("C", 0) / total, 3)), 3)),
        }

    # -------------------------------------------------------------
    # User Votes & Compass Archetype Profiles
    # -------------------------------------------------------------
    def record_user_vote(
        self,
        rater_salt: str,
        question_id: str,
        choice_letter: str,
        region_key: Optional[str] = None,
        tier_level: int = 1,
        verification_sig: Optional[str] = None,
    ) -> None:
        """Store an individual user vote mapped to their pseudonymous salt with verification tier."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO user_votes (rater_salt, question_id, choice_letter, region_key, tier_level, verification_sig, verified_at)
                   VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? > 1 THEN CURRENT_TIMESTAMP ELSE NULL END)
                   ON CONFLICT(rater_salt, question_id) DO UPDATE SET
                       choice_letter = excluded.choice_letter,
                       region_key = excluded.region_key,
                       tier_level = MAX(user_votes.tier_level, excluded.tier_level),
                       verification_sig = COALESCE(excluded.verification_sig, user_votes.verification_sig),
                       verified_at = CASE WHEN excluded.tier_level > user_votes.tier_level THEN CURRENT_TIMESTAMP ELSE user_votes.verified_at END;""",
                (rater_salt, question_id, choice_letter, region_key, tier_level, verification_sig, tier_level),
            )

    def get_user_votes(self, rater_salt: str) -> Dict[str, str]:
        """Fetch all recorded question choices for a user salt."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT question_id, choice_letter FROM user_votes WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchall()
        return {r["question_id"]: r["choice_letter"] for r in rows}

    def get_user_vote_details(self, rater_salt: str) -> Dict[str, Dict[str, Any]]:
        """Fetch full vote records including tier_level and verification status."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT question_id, choice_letter, region_key, tier_level, verification_sig, verified_at, created_at
                   FROM user_votes WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchall()
        return {
            r["question_id"]: {
                "choice_letter": r["choice_letter"],
                "region_key": r["region_key"],
                "tier_level": int(r["tier_level"] or 1),
                "is_verified": int(r["tier_level"] or 1) >= 2,
                "verification_sig": r["verification_sig"],
                "verified_at": r["verified_at"],
                "created_at": r["created_at"],
            }
            for r in rows
        }

    def upgrade_user_vote_tier(
        self,
        rater_salt: str,
        new_tier: int = 2,
        verification_method: str = "PASSKEY",
        verification_sig: Optional[str] = None,
        credential_id: Optional[str] = None,
    ) -> int:
        """
        Atomically upgrades all prior votes of rater_salt to new_tier in user_votes
        and transitions the spatial counts in hex_tier_aggregates from Tier 1 to new_tier.
        Guarantees zero double-counting.
        Returns count of upgraded votes.
        """
        from atlas.geo.regions import get_h3_cell_for_region

        with self._get_connection() as conn:
            # 1. Update/upsert user_verifications
            conn.execute(
                """INSERT INTO user_verifications (rater_salt, current_tier, verification_method, credential_id, verified_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(rater_salt) DO UPDATE SET
                       current_tier = MAX(user_verifications.current_tier, excluded.current_tier),
                       verification_method = excluded.verification_method,
                       credential_id = COALESCE(excluded.credential_id, user_verifications.credential_id),
                       verified_at = CURRENT_TIMESTAMP;""",
                (rater_salt, new_tier, verification_method, credential_id),
            )

            # 2. Find votes eligible for tier upgrade
            votes_to_upgrade = conn.execute(
                """SELECT question_id, choice_letter, region_key, tier_level
                   FROM user_votes
                   WHERE rater_salt = ? AND tier_level < ?;""",
                (rater_salt, new_tier),
            ).fetchall()

            upgraded_count = len(votes_to_upgrade)
            for v in votes_to_upgrade:
                qid = v["question_id"]
                letter = v["choice_letter"]
                reg_key = v["region_key"]
                old_tier = v["tier_level"] or 1

                if reg_key:
                    try:
                        h3_cell = get_h3_cell_for_region(reg_key)
                        # Decrement old tier in hex_tier_aggregates
                        conn.execute(
                            """UPDATE hex_tier_aggregates
                               SET vote_count = MAX(0, vote_count - 1)
                               WHERE question_id = ? AND h3_cell_id = ? AND tier_level = ? AND choice_letter = ?;""",
                            (qid, h3_cell, old_tier, letter),
                        )
                        # Increment new tier in hex_tier_aggregates
                        conn.execute(
                            """INSERT INTO hex_tier_aggregates (question_id, h3_cell_id, tier_level, choice_letter, vote_count)
                               VALUES (?, ?, ?, ?, 1)
                               ON CONFLICT(question_id, h3_cell_id, tier_level, choice_letter)
                               DO UPDATE SET vote_count = vote_count + 1;""",
                            (qid, h3_cell, new_tier, letter),
                        )
                    except Exception:
                        pass

            # 3. Batch update user_votes
            if upgraded_count > 0:
                conn.execute(
                    """UPDATE user_votes
                       SET tier_level = ?,
                           verification_sig = COALESCE(?, verification_sig),
                           verified_at = CURRENT_TIMESTAMP
                       WHERE rater_salt = ? AND tier_level < ?;""",
                    (new_tier, verification_sig, rater_salt, new_tier),
                )

            return upgraded_count

    def get_user_verification(self, rater_salt: str) -> Dict[str, Any]:
        """Fetch verification status for a user."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT current_tier, verification_method, credential_id, verified_at, reputation_weight
                   FROM user_verifications WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchone()
        if row:
            return {
                "rater_salt": rater_salt,
                "current_tier": int(row["current_tier"]),
                "verification_method": row["verification_method"] or "ANONYMOUS",
                "credential_id": row["credential_id"],
                "verified_at": row["verified_at"],
                "reputation_weight": float(row["reputation_weight"]),
                "is_verified": int(row["current_tier"]) >= 2,
            }
        return {
            "rater_salt": rater_salt,
            "current_tier": 1,
            "verification_method": "ANONYMOUS",
            "credential_id": None,
            "verified_at": None,
            "reputation_weight": 1.0,
            "is_verified": False,
        }

    def set_user_verification(
        self,
        rater_salt: str,
        current_tier: int = 2,
        verification_method: str = "PASSKEY",
        credential_id: Optional[str] = None,
        reputation_weight: float = 1.0,
    ) -> None:
        """Store or update user verification state."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO user_verifications (rater_salt, current_tier, verification_method, credential_id, reputation_weight, verified_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(rater_salt) DO UPDATE SET
                       current_tier = excluded.current_tier,
                       verification_method = excluded.verification_method,
                       credential_id = COALESCE(excluded.credential_id, user_verifications.credential_id),
                       reputation_weight = excluded.reputation_weight,
                       verified_at = CURRENT_TIMESTAMP;""",
                (rater_salt, current_tier, verification_method, credential_id, reputation_weight),
            )

    def get_question_multi_tier_aggregates(self, question_id: str) -> Dict[str, Any]:
        """
        Computes comparative distributions for Option B (All Voices vs. Verified Only).
        Returns total counts, percentages per choice, and divergence delta statistics.
        """
        with self._get_connection() as conn:
            # 1. Check question selectivity
            q_row = conn.execute(
                """SELECT tier_mode, allowed_tiers, min_verification_tier, is_multi_tier
                   FROM questions WHERE question_id = ?;""",
                (question_id,),
            ).fetchone()

            tier_mode = q_row["tier_mode"] if q_row and "tier_mode" in q_row.keys() and q_row["tier_mode"] else "MULTI_TIER"
            is_multi_tier = bool(q_row["is_multi_tier"]) if q_row and "is_multi_tier" in q_row.keys() and q_row["is_multi_tier"] is not None else True
            min_tier = int(q_row["min_verification_tier"]) if q_row and "min_verification_tier" in q_row.keys() and q_row["min_verification_tier"] else 1

            # 2. Get All Votes
            all_rows = conn.execute(
                """SELECT choice_letter, SUM(vote_count) as total_c
                   FROM hex_aggregates
                   WHERE question_id = ?
                   GROUP BY choice_letter;""",
                (question_id,),
            ).fetchall()

            # 3. Get Verified Votes (Tier >= 2)
            verified_rows = conn.execute(
                """SELECT choice_letter, SUM(vote_count) as total_c
                   FROM hex_tier_aggregates
                   WHERE question_id = ? AND tier_level >= 2
                   GROUP BY choice_letter;""",
                (question_id,),
            ).fetchall()

        all_counts = {r["choice_letter"]: int(r["total_c"]) for r in all_rows}
        verified_counts = {r["choice_letter"]: int(r["total_c"]) for r in verified_rows}

        total_all = sum(all_counts.values())
        total_ver = sum(verified_counts.values())

        # Proportions for All
        if total_all > 0:
            pct_all = {k: round((all_counts.get(k, 0) / total_all) * 100) for k in ("A", "B", "C", "D")}
        else:
            pct_all = {"A": 25, "B": 25, "C": 25, "D": 25}

        # Proportions for Verified
        if total_ver > 0:
            pct_ver = {k: round((verified_counts.get(k, 0) / total_ver) * 100) for k in ("A", "B", "C", "D")}
        else:
            pct_ver = {k: pct_all[k] for k in ("A", "B", "C", "D")}

        # Normalize percentages to 100
        sum_all = sum(pct_all.values())
        if sum_all != 100 and total_all > 0:
            pct_all["D"] = max(0, 100 - (pct_all["A"] + pct_all["B"] + pct_all["C"]))
        sum_ver = sum(pct_ver.values())
        if sum_ver != 100 and total_ver > 0:
            pct_ver["D"] = max(0, 100 - (pct_ver["A"] + pct_ver["B"] + pct_ver["C"]))

        # Calculate Divergence (Delta = Verified - All)
        deltas = {k: pct_ver[k] - pct_all[k] for k in ("A", "B", "C", "D")}
        max_div_choice = max(deltas.keys(), key=lambda k: abs(deltas[k]))
        max_delta = deltas[max_div_choice]

        dom_all = max(pct_all.keys(), key=lambda k: pct_all[k])
        dom_ver = max(pct_ver.keys(), key=lambda k: pct_ver[k])

        return {
            "question_id": question_id,
            "tier_mode": tier_mode,
            "is_multi_tier": is_multi_tier,
            "min_verification_tier": min_tier,
            "all": {
                "total_votes": total_all,
                "counts": all_counts,
                "distribution": [pct_all["A"], pct_all["B"], pct_all["C"], pct_all["D"]],
                "dominant_choice": dom_all,
            },
            "verified": {
                "total_votes": total_ver,
                "counts": verified_counts,
                "distribution": [pct_ver["A"], pct_ver["B"], pct_ver["C"], pct_ver["D"]],
                "dominant_choice": dom_ver,
            },
            "diff": {
                "dominant_choice": dom_all,
                "delta_dominant": deltas[dom_all],
                "max_divergence_choice": max_div_choice,
                "delta_max_divergence": max_delta,
                "deltas": deltas,
                "has_significant_split": abs(max_delta) >= 8,
            },
        }

    def save_archetype_profile(self, profile: Dict[str, Any]) -> None:
        """Persist or update a user's calculated 5D compass archetype profile."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO user_archetype_profiles 
                   (rater_salt, archetype_title, primary_city, primary_city_country, primary_city_flag,
                    match_pct, counter_city, counter_city_country, counter_city_flag, counter_match_pct,
                    vector_autonomy, vector_punctuality, vector_boundary, vector_freedom, vector_trust,
                    summary_narrative, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(rater_salt) DO UPDATE SET
                       archetype_title = excluded.archetype_title,
                       primary_city = excluded.primary_city,
                       primary_city_country = excluded.primary_city_country,
                       primary_city_flag = excluded.primary_city_flag,
                       match_pct = excluded.match_pct,
                       counter_city = excluded.counter_city,
                       counter_city_country = excluded.counter_city_country,
                       counter_city_flag = excluded.counter_city_flag,
                       counter_match_pct = excluded.counter_match_pct,
                       vector_autonomy = excluded.vector_autonomy,
                       vector_punctuality = excluded.vector_punctuality,
                       vector_boundary = excluded.vector_boundary,
                       vector_freedom = excluded.vector_freedom,
                       vector_trust = excluded.vector_trust,
                       summary_narrative = excluded.summary_narrative,
                       updated_at = CURRENT_TIMESTAMP;""",
                (
                    profile["rater_salt"],
                    profile["archetype_title"],
                    profile["primary_city"],
                    profile["primary_city_country"],
                    profile["primary_city_flag"],
                    profile["match_pct"],
                    profile["counter_city"],
                    profile["counter_city_country"],
                    profile["counter_city_flag"],
                    profile["counter_match_pct"],
                    profile["vector_autonomy"],
                    profile["vector_punctuality"],
                    profile["vector_boundary"],
                    profile["vector_freedom"],
                    profile["vector_trust"],
                    profile["summary_narrative"],
                ),
            )

    def get_archetype_profile(self, rater_salt: str) -> Optional[Dict[str, Any]]:
        """Retrieve a user's calculated archetype profile."""
        with self._get_connection() as conn:
            row = conn.execute(
                """SELECT * FROM user_archetype_profiles WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchone()
        return dict(row) if row else None

    # -------------------------------------------------------------
    # Default Bootstrap Seeding
    # -------------------------------------------------------------
    def seed_default_data_if_empty(self) -> None:
        """Seed all 30 slates, 150 questions, choices, and hex aggregates in a single fast transaction."""
        with self._get_connection() as conn:
            q_count = conn.execute("SELECT COUNT(*) as c FROM questions;").fetchone()["c"]
            demo_count = conn.execute("SELECT COUNT(*) as c FROM user_demographics;").fetchone()["c"]
            hex_tier_count = conn.execute("SELECT COUNT(*) as c FROM hex_tier_aggregates;").fetchone()["c"]

        if q_count >= 150:
            if demo_count < 24:
                self.seed_demographics_and_ratings()
            if hex_tier_count == 0:
                self.seed_hex_tier_aggregates()
            return

        from atlas.geo.regions import REGION_DEFINITIONS, REGION_TO_H3
        from atlas.content.slates_30d import SLATES_30D

        with self._get_connection() as conn:
            # Temporary performance pragmas for atomic bulk ingest
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA temp_store = MEMORY;")

            slates_batch = []
            questions_batch = []
            choices_batch = []
            hex_aggregates_batch = []
            hex_tier_aggregates_batch = []

            for slate in SLATES_30D:
                day_num = slate.get("day_number", 1)
                is_active = 1 if day_num == 1 else 0
                slates_batch.append((
                    slate["slate_id"],
                    day_num,
                    slate.get("release_date", "2026-09-01"),
                    slate.get("title", f"The Daily Slate #{day_num}"),
                    json.dumps(slate.get("domain_tags", [])),
                    is_active,
                ))

                for q in slate["questions"]:
                    qid = q["question_id"]
                    questions_batch.append((
                        qid,
                        slate["slate_id"],
                        q["order_idx"],
                        q.get("domain", "WORK_MOBILITY"),
                        q.get("domain", "WORK_MOBILITY"),
                        q.get("axis", "autonomy"),
                        q.get("tier_mode", "MULTI_TIER"),
                        json.dumps(q.get("allowed_tiers", [1, 2, 3])),
                        q.get("min_verification_tier", 1),
                        1 if q.get("is_multi_tier", True) else 0,
                        q["prompt"],
                    ))

                    for ch in q["choices"]:
                        cid = f"c_{qid}_{ch['letter']}"
                        choices_batch.append((
                            cid,
                            qid,
                            ch["letter"],
                            ch["label"],
                            ch["shape_symbol"],
                            ch["color_hex"],
                        ))

                    for reg_key, meta in REGION_DEFINITIONS.items():
                        cell_id = REGION_TO_H3[reg_key]
                        sample = meta.get("baseline_sample", 100)
                        dist = meta.get("baseline_dist", [25, 25, 25, 25])
                        cA = int(sample * (dist[0] / 100.0))
                        cB = int(sample * (dist[1] / 100.0))
                        cC = int(sample * (dist[2] / 100.0))
                        cD = max(0, sample - (cA + cB + cC))
                        hex_aggregates_batch.extend([
                            (qid, cell_id, "A", cA),
                            (qid, cell_id, "B", cB),
                            (qid, cell_id, "C", cC),
                            (qid, cell_id, "D", cD),
                        ])

                        # Seed tier partitioned aggregates (Tier 1 Anonymous ~80%, Tier 2 Verified ~20%)
                        ver_sample = max(15, int(sample * 0.20))
                        v_dist_B = min(90, dist[1] + 8)
                        v_dist_A = max(5, dist[0] - 8)
                        v_cA = int(ver_sample * (v_dist_A / 100.0))
                        v_cB = int(ver_sample * (v_dist_B / 100.0))
                        v_cC = int(ver_sample * (dist[2] / 100.0))
                        v_cD = max(0, ver_sample - (v_cA + v_cB + v_cC))

                        a_cA = max(0, cA - v_cA)
                        a_cB = max(0, cB - v_cB)
                        a_cC = max(0, cC - v_cC)
                        a_cD = max(0, cD - v_cD)

                        hex_tier_aggregates_batch.extend([
                            (qid, cell_id, 1, "A", a_cA),
                            (qid, cell_id, 1, "B", a_cB),
                            (qid, cell_id, 1, "C", a_cC),
                            (qid, cell_id, 1, "D", a_cD),
                            (qid, cell_id, 2, "A", v_cA),
                            (qid, cell_id, 2, "B", v_cB),
                            (qid, cell_id, 2, "C", v_cC),
                            (qid, cell_id, 2, "D", v_cD),
                        ])

            conn.executemany(
                """INSERT OR REPLACE INTO slates (slate_id, day_number, release_date, title, domain_tags, is_active)
                   VALUES (?, ?, ?, ?, ?, ?);""",
                slates_batch,
            )
            conn.executemany(
                """INSERT OR REPLACE INTO questions (question_id, slate_id, order_idx, category, domain, axis, tier_mode, allowed_tiers, min_verification_tier, is_multi_tier, prompt)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                questions_batch,
            )
            conn.executemany(
                """INSERT OR REPLACE INTO choices (choice_id, question_id, letter, label, shape_symbol, color_hex)
                   VALUES (?, ?, ?, ?, ?, ?);""",
                choices_batch,
            )
            conn.executemany(
                """INSERT OR REPLACE INTO hex_aggregates (question_id, h3_cell_id, choice_letter, vote_count)
                   VALUES (?, ?, ?, ?);""",
                hex_aggregates_batch,
            )
            conn.executemany(
                """INSERT OR REPLACE INTO hex_tier_aggregates (question_id, h3_cell_id, tier_level, choice_letter, vote_count)
                   VALUES (?, ?, ?, ?, ?);""",
                hex_tier_aggregates_batch,
            )

            # Seed initial perspectives and demographic ratings on the same open connection
            self.seed_demographics_and_ratings(conn=conn)

    def seed_hex_tier_aggregates(self, conn=None) -> None:
        """Backfill hex_tier_aggregates from hex_aggregates if empty."""
        def _do_seed(c):
            rows = c.execute("SELECT question_id, h3_cell_id, choice_letter, vote_count FROM hex_aggregates;").fetchall()
            if not rows:
                return
            tier_batch = []
            for r in rows:
                qid = r["question_id"]
                cell_id = r["h3_cell_id"]
                ch = r["choice_letter"]
                cnt = r["vote_count"]
                # Realistic verified sample ~20% of baseline with divergence on Option A vs B
                pct = 0.28 if ch == "A" else (0.15 if ch == "B" else 0.20)
                ver_cnt = max(1, int(cnt * pct)) if cnt > 0 else 0
                anon_cnt = max(0, cnt - ver_cnt)
                tier_batch.extend([
                    (qid, cell_id, 1, ch, anon_cnt),
                    (qid, cell_id, 2, ch, ver_cnt),
                ])
            c.executemany(
                """INSERT OR REPLACE INTO hex_tier_aggregates (question_id, h3_cell_id, tier_level, choice_letter, vote_count)
                   VALUES (?, ?, ?, ?, ?);""",
                tier_batch
            )
        if conn is not None:
            _do_seed(conn)
        else:
            with self._get_connection() as c:
                _do_seed(c)

    def seed_demographics_and_ratings(self, conn=None) -> None:
        """Seed initial perspectives, 24 demographic users, and calibrated cross-cohort ratings."""
        if conn is not None:
            self._do_seed_demographics_and_ratings(conn)
        else:
            with self._get_connection() as c:
                self._do_seed_demographics_and_ratings(c)

    def _do_seed_demographics_and_ratings(self, conn) -> None:
        perspectives_data = [
                ("p_01", "q_01", "A", "Commuting burns 2 hours of unpaid life every single day. An extra 10 hours a week for sleep and family is worth a 30% pay cut without hesitation.", "@marcus_dev (London, UK)"),
                ("p_02", "q_01", "A", "Gas, car insurance, vehicle depreciation, and mental exhaustion easily equal 20% of net income anyway. You break even in actual quality of life.", "@elena_sf (San Francisco, US)"),
                ("p_03", "q_01", "B", "With rising rent and inflation, sacrificing 30% income severely compromises long-term security and pension. Convenience is a luxury.", "@kenji_tokyo (Tokyo, JP)"),
                ("p_04", "q_01", "B", "Early career compounding matters more. Better to take the commute for 5 years, bank the capital, and buy freedom later.", "@sarah_m (Toronto, CA)"),
                ("p_05", "q_01", "C", "A 20-minute bicycle or train commute is actually pleasant decompression. A 90-minute traffic jam is hell. The threshold makes all the difference.", "@pieter_ams (Amsterdam, NL)"),
                ("p_06", "q_01", "C", "It depends entirely on transit quality. If I can read on the train, commute time is useful life time.", "@clara_b (Berlin, DE)"),
            ]
        conn.executemany(
            """INSERT OR REPLACE INTO perspectives (perspective_id, question_id, choice_letter, body, author_salt)
               VALUES (?, ?, ?, ?, ?);""",
            perspectives_data,
        )

        # 24 seed raters covering cohorts
        demographics_batch = []
        for i in range(24):
            salt = f"seed_rater_{i}"
            if i < 6:
                gen, urb, reg = "GEN_Z", "HYPER_URBAN", "ANGLOSPHERE"
            elif i < 12:
                gen, urb, reg = "MILLENNIAL", "URBAN_SUBURBAN", "EUROPE_WEST"
            elif i < 18:
                gen, urb, reg = "GEN_X", "RURAL", "ANGLOSPHERE"
            else:
                gen, urb, reg = "BOOMER_PLUS", "URBAN_SUBURBAN", "EAST_ASIA"
            demographics_batch.append((salt, gen, urb, reg))

        conn.executemany(
            """INSERT OR REPLACE INTO user_demographics (rater_salt, generation_cohort, urbanicity, macro_region)
               VALUES (?, ?, ?, ?);""",
            demographics_batch,
        )

        ratings_batch = []
        for i in range(24):
            salt = f"seed_rater_{i}"
            gen = demographics_batch[i][1]
            urb = demographics_batch[i][2]

            p05_score = 0.0 if i in (5, 23) else 1.0
            ratings_batch.append(("p_05", salt, p05_score, gen, urb))

            if i < 6:
                p01_score = 0.0 if i == 5 else 1.0
            elif i >= 18:
                p01_score = 1.0 if i == 18 else 0.0
            else:
                p01_score = 1.0 if i % 2 == 0 else 0.0
            ratings_batch.append(("p_01", salt, p01_score, gen, urb))

            if i >= 18:
                p03_score = 0.0 if i == 23 else 1.0
            elif i < 6:
                p03_score = 1.0 if i == 0 else 0.0
            else:
                p03_score = 1.0 if i % 2 == 1 else 0.0
            ratings_batch.append(("p_03", salt, p03_score, gen, urb))

            if urb == "HYPER_URBAN":
                p02_score = 0.0 if i == 5 else 1.0
            elif urb == "RURAL":
                p02_score = 0.0 if i in (16, 17) else 1.0
            else:
                p02_score = 1.0 if i % 2 == 0 else 0.0
            ratings_batch.append(("p_02", salt, p02_score, gen, urb))

            if gen in ("MILLENNIAL", "GEN_X"):
                p04_score = 0.0 if i in (11, 17) else 1.0
            else:
                p04_score = 1.0 if i % 3 == 0 else 0.0
            ratings_batch.append(("p_04", salt, p04_score, gen, urb))

            p06_score = 1.0 if i % 2 == 0 else 0.0
            ratings_batch.append(("p_06", salt, p06_score, gen, urb))

        conn.executemany(
            """INSERT OR REPLACE INTO perspective_ratings 
               (perspective_id, rater_salt, rating_score, rater_generation, rater_urbanicity)
               VALUES (?, ?, ?, ?, ?);""",
            ratings_batch,
        )

        verifications_batch = []
        for i in range(24):
            salt = f"seed_rater_{i}"
            tier = 2 if i % 2 == 0 else 1
            method = "PASSKEY" if i % 2 == 0 else "ANONYMOUS"
            verifications_batch.append((salt, tier, method, f"cred_{salt}", 1.5 if tier == 2 else 1.0))
        conn.executemany(
            """INSERT OR REPLACE INTO user_verifications (rater_salt, current_tier, verification_method, credential_id, reputation_weight)
               VALUES (?, ?, ?, ?, ?);""",
            verifications_batch,
        )



    # -------------------------------------------------------------
    # 30-Day Catalog, State & History Queries
    # -------------------------------------------------------------
    def get_all_slates(self, rater_salt: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return summary of all 30 slates with completion badges for rater_salt."""
        with self._get_connection() as conn:
            slates = conn.execute(
                """SELECT s.slate_id, s.day_number, s.release_date, s.title, s.domain_tags, s.is_active,
                          COUNT(q.question_id) as question_count
                   FROM slates s
                   LEFT JOIN questions q ON s.slate_id = q.slate_id
                   GROUP BY s.slate_id
                   ORDER BY s.day_number ASC;"""
            ).fetchall()

            completed_days = set()
            if rater_salt:
                rows = conn.execute(
                    """SELECT s.day_number, COUNT(uv.question_id) as votes_count
                       FROM slates s
                       JOIN questions q ON s.slate_id = q.slate_id
                       JOIN user_votes uv ON q.question_id = uv.question_id AND uv.rater_salt = ?
                       GROUP BY s.day_number
                       HAVING votes_count >= 5;""",
                    (rater_salt,),
                ).fetchall()
                completed_days = {r["day_number"] for r in rows}

        results = []
        for s in slates:
            item = dict(s)
            day = item.get("day_number") or 1
            item["domain_tags"] = json.loads(item.get("domain_tags") or "[]")
            item["is_completed"] = day in completed_days
            results.append(item)
        return results

    def get_slate_by_day(self, day_number: int) -> Optional[Dict[str, Any]]:
        """Fetch full slate, questions, choices for a given day."""
        with self._get_connection() as conn:
            slate_row = conn.execute(
                """SELECT * FROM slates WHERE day_number = ?;""",
                (day_number,),
            ).fetchone()
            if not slate_row:
                return None

            slate_dict = dict(slate_row)
            slate_dict["domain_tags"] = json.loads(slate_dict.get("domain_tags") or "[]")

            questions_rows = conn.execute(
                """SELECT * FROM questions WHERE slate_id = ? ORDER BY order_idx ASC;""",
                (slate_dict["slate_id"],),
            ).fetchall()

            questions = []
            for qr in questions_rows:
                q = dict(qr)
                choices_rows = conn.execute(
                    """SELECT letter, label, shape_symbol, color_hex
                       FROM choices WHERE question_id = ? ORDER BY letter ASC;""",
                    (q["question_id"],),
                ).fetchall()
                q["choices"] = [dict(c) for c in choices_rows]
                questions.append(q)

            slate_dict["questions"] = questions
            return slate_dict

    def get_user_state(self, rater_salt: str) -> Dict[str, Any]:
        """Fetch all votes, calibrations, and completion metrics for a user."""
        with self._get_connection() as conn:
            votes_rows = conn.execute(
                """SELECT question_id, choice_letter, region_key, created_at
                   FROM user_votes WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchall()
            votes = {r["question_id"]: r["choice_letter"] for r in votes_rows}

            cal_rows = conn.execute(
                """SELECT question_id, pred_a, pred_b, pred_c, pred_d, brier_score, calibration_index
                   FROM calibration_guesses WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchall()
            calibrations = {
                r["question_id"]: {
                    "predictions": {"A": r["pred_a"], "B": r["pred_b"], "C": r["pred_c"], "D": r["pred_d"]},
                    "brier_score": r["brier_score"],
                    "calibration_index": r["calibration_index"],
                }
                for r in cal_rows
            }

            completed_rows = conn.execute(
                """SELECT s.day_number, COUNT(uv.question_id) as vote_cnt
                   FROM slates s
                   JOIN questions q ON s.slate_id = q.slate_id
                   JOIN user_votes uv ON q.question_id = uv.question_id AND uv.rater_salt = ?
                   GROUP BY s.day_number
                   HAVING vote_cnt >= 5;""",
                (rater_salt,),
            ).fetchall()
            completed_days = sorted([r["day_number"] for r in completed_rows])

        streak_stats = self.get_user_streak(rater_salt)
        return {
            "rater_salt": rater_salt,
            "votes": votes,
            "calibrations": calibrations,
            "completed_days": completed_days,
            "total_votes": len(votes),
            "streak": streak_stats,
            "streak_stats": streak_stats,
        }

    def get_user_streak(self, rater_salt: str) -> Dict[str, Any]:
        """Calculates engagement habit streak and slate completion count."""
        with self._get_connection() as conn:
            # Get distinct voting dates
            date_rows = conn.execute(
                """SELECT DISTINCT DATE(created_at) as vote_date 
                   FROM user_votes WHERE rater_salt = ? ORDER BY vote_date DESC;""",
                (rater_salt,),
            ).fetchall()
            dates = [r["vote_date"] for r in date_rows if r["vote_date"]]

            # Total slates completed
            completed_rows = conn.execute(
                """SELECT s.day_number, COUNT(uv.question_id) as vote_cnt
                   FROM slates s
                   JOIN questions q ON s.slate_id = q.slate_id
                   JOIN user_votes uv ON q.question_id = uv.question_id AND uv.rater_salt = ?
                   GROUP BY s.day_number
                   HAVING vote_cnt >= 5;""",
                (rater_salt,),
            ).fetchall()
            completed_slates_count = len(completed_rows)

            total_votes = conn.execute(
                """SELECT COUNT(*) as c FROM user_votes WHERE rater_salt = ?;""",
                (rater_salt,),
            ).fetchone()["c"]

        # True contiguous habit streak
        habit_streak = 0
        if dates:
            try:
                date_objs = sorted(list(set(datetime.date.fromisoformat(d) for d in dates)), reverse=True)
                today = datetime.date.today()
                latest_vote = date_objs[0]

                # If the latest vote was today or yesterday, streak is currently active
                if (today - latest_vote).days <= 1:
                    habit_streak = 1
                    curr = latest_vote
                    for prev in date_objs[1:]:
                        if (curr - prev).days == 1:
                            habit_streak += 1
                            curr = prev
                        elif (curr - prev).days == 0:
                            continue
                        else:
                            break
                else:
                    # More than 1 day elapsed since last vote -> streak inactive
                    habit_streak = 0
            except Exception:
                habit_streak = len(dates)

        return {
            "habit_streak_days": habit_streak,
            "completed_slates_count": completed_slates_count,
            "total_votes": total_votes,
        }

    def record_compass_history(
        self,
        rater_salt: str,
        slate_id: Optional[str] = None,
        day_number: Optional[int] = None,
        vector: Optional[Dict[str, float]] = None,
        primary_city: Optional[str] = None,
        match_pct: Optional[float] = None,
        confidence_pct: int = 0,
        num_votes: Optional[int] = None,
        archetype_title: Optional[str] = None,
        primary_twin_city: Optional[str] = None,
    ) -> None:
        """Appends or updates a snapshot in user_compass_history upon slate completion (idempotent per rater_salt + day_number)."""
        vec = vector or {}
        city = primary_city or primary_twin_city or ""
        d_num = day_number if day_number is not None else 1
        s_id = slate_id or f"slate_daily_{d_num:02d}"
        n_votes = num_votes if num_votes is not None else 5
        arch = archetype_title or ""
        pct = match_pct if match_pct is not None else 90.0

        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO user_compass_history 
                   (rater_salt, slate_id, day_number, num_votes, archetype_title, vector_autonomy, vector_punctuality, 
                    vector_boundary, vector_freedom, vector_trust, primary_city, match_pct, confidence_pct, calculated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(rater_salt, day_number) DO UPDATE SET
                       slate_id = excluded.slate_id,
                       num_votes = excluded.num_votes,
                       archetype_title = excluded.archetype_title,
                       vector_autonomy = excluded.vector_autonomy,
                       vector_punctuality = excluded.vector_punctuality,
                       vector_boundary = excluded.vector_boundary,
                       vector_freedom = excluded.vector_freedom,
                       vector_trust = excluded.vector_trust,
                       primary_city = excluded.primary_city,
                       match_pct = excluded.match_pct,
                       confidence_pct = excluded.confidence_pct,
                       calculated_at = CURRENT_TIMESTAMP;""",
                (
                    rater_salt,
                    s_id,
                    d_num,
                    n_votes,
                    arch,
                    vec.get("autonomy", 0.5),
                    vec.get("punctuality", 0.5),
                    vec.get("boundary", 0.5),
                    vec.get("freedom", 0.5),
                    vec.get("trust", 0.5),
                    city,
                    pct,
                    confidence_pct,
                ),
            )

    def get_compass_trajectory(self, rater_salt: str) -> List[Dict[str, Any]]:
        """Retrieves longitudinal vector snapshots ordered chronologically."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM user_compass_history 
                   WHERE rater_salt = ? 
                   ORDER BY day_number ASC, calculated_at ASC;""",
                (rater_salt,),
            ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------
    # Bandit Arms & PWA Offline Batch Synchronization
    # -------------------------------------------------------------
    def load_bandit_arms(self) -> Dict[str, Dict[str, Any]]:
        """Loads all persisted bandit arms."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT arm_id, alpha, beta, pulls FROM bandit_arms;").fetchall()
        return {
            r["arm_id"]: {
                "alpha": float(r["alpha"]),
                "beta": float(r["beta"]),
                "pulls": int(r["pulls"]),
            }
            for r in rows
        }

    def save_bandit_arm(self, arm_id: str, alpha: float, beta: float, pulls: int) -> None:
        """Persists or updates a bandit arm posterior in SQLite."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO bandit_arms (arm_id, alpha, beta, pulls, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(arm_id) DO UPDATE SET
                       alpha = excluded.alpha,
                       beta = excluded.beta,
                       pulls = excluded.pulls,
                       updated_at = CURRENT_TIMESTAMP;""",
                (arm_id, float(alpha), float(beta), int(pulls)),
            )

    def execute_batch_sync(
        self,
        rater_salt: str,
        actions: List[Dict[str, Any]],
        batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes an atomic batch of queued offline actions from PWA clients.
        Supported actions:
        - 'cast_vote': {'question_id', 'choice_letter', 'region_key'}
        - 'submit_calibration': {'question_id', 'predictions'}
        - 'rate_perspective': {'perspective_id', 'is_helpful', 'rating_category', ...}
        - 'rate_deck_item': {'perspective_id', 'rating_category', ...}
        - 'submit_perspective': {'question_id', 'choice_letter', 'body', ...}
        """
        import uuid
        actual_batch_id = batch_id or f"batch_{uuid.uuid4().hex[:12]}"
        results = []
        errors = []

        for idx, action in enumerate(actions):
            action_type = action.get("action_type") or action.get("type")
            payload = action.get("payload") if "payload" in action else action
            try:
                if action_type == "cast_vote":
                    qid = payload.get("question_id")
                    choice = (payload.get("choice_letter") or "A").upper()
                    region = payload.get("region_key")
                    if qid and region:
                        from atlas.geo.regions import get_h3_cell_for_region
                        h3_cell = get_h3_cell_for_region(region)
                        self.record_hex_vote(qid, h3_cell, choice, increment=1)
                    if qid:
                        self.record_user_vote(rater_salt, qid, choice, region)
                    results.append({"index": idx, "action": action_type, "status": "ok"})

                elif action_type == "submit_calibration":
                    qid = payload.get("question_id")
                    preds = payload.get("predictions", {})
                    if qid and preds:
                        pred_a = float(preds.get("A", 0.25))
                        pred_b = float(preds.get("B", 0.25))
                        pred_c = float(preds.get("C", 0.25))
                        pred_d = float(preds.get("D", 0.25))
                        pred_sum = pred_a + pred_b + pred_c + pred_d
                        if pred_sum > 0:
                            pred_a, pred_b, pred_c, pred_d = pred_a / pred_sum, pred_b / pred_sum, pred_c / pred_sum, pred_d / pred_sum
                        from atlas.algorithms.calibration import CulturalCalibrationScorer
                        ground_truth = self.get_question_ground_truth(qid)
                        scorer = CulturalCalibrationScorer()
                        eval_res = scorer.evaluate({"A": pred_a, "B": pred_b, "C": pred_c, "D": pred_d}, ground_truth)
                        guess_id = f"g_{uuid.uuid4().hex[:8]}"
                        brier_val = eval_res.brier_score if hasattr(eval_res, "brier_score") else eval_res["brier_score"]
                        calib_idx = eval_res.calibration_index if hasattr(eval_res, "calibration_index") else eval_res["calibration_index"]
                        self.record_calibration_guess(
                            guess_id=guess_id,
                            question_id=qid,
                            rater_salt=rater_salt,
                            pred_a=pred_a,
                            pred_b=pred_b,
                            pred_c=pred_c,
                            pred_d=pred_d,
                            brier_score=brier_val,
                            calibration_index=calib_idx,
                        )
                        results.append({"index": idx, "action": action_type, "status": "ok", "brier_score": brier_val, "calibration_index": calib_idx})
                    else:
                        results.append({"index": idx, "action": action_type, "status": "skipped"})

                elif action_type == "rate_deck_item":
                    pid = payload.get("perspective_id")
                    category = payload.get("rating_category", "HELPFUL_BRIDGE")
                    gen = payload.get("rater_generation", "UNSPECIFIED")
                    urb = payload.get("rater_urbanicity", "UNSPECIFIED")
                    reg = payload.get("rater_macro_region", "UNSPECIFIED")
                    if pid:
                        deck_res = self.rate_deck_item(
                            perspective_id=pid,
                            rater_salt=rater_salt,
                            rating_category=category,
                            rater_generation=gen,
                            rater_urbanicity=urb,
                            rater_macro_region=reg,
                        )
                        results.append({"index": idx, "action": action_type, "status": "ok", "result": deck_res})
                    else:
                        results.append({"index": idx, "action": action_type, "status": "skipped"})

                elif action_type == "rate_perspective":
                    pid = payload.get("perspective_id")
                    helpful = bool(payload.get("is_helpful", True))
                    gen = payload.get("rater_generation", "UNSPECIFIED")
                    urb = payload.get("rater_urbanicity", "UNSPECIFIED")
                    reg = payload.get("rater_macro_region", "UNSPECIFIED")
                    category = payload.get("rating_category", "HELPFUL_BRIDGE")
                    if pid:
                        p_res = self.rate_perspective(
                            perspective_id=pid,
                            rater_salt=rater_salt,
                            is_helpful=helpful,
                            rater_generation=gen,
                            rater_urbanicity=urb,
                            rater_macro_region=reg,
                            rating_category=category,
                        )
                        results.append({"index": idx, "action": action_type, "status": "ok", "result": p_res})
                    else:
                        results.append({"index": idx, "action": action_type, "status": "skipped"})

                elif action_type == "submit_perspective":
                    qid = payload.get("question_id")
                    choice = payload.get("choice_letter", "A")
                    body = payload.get("body", "")
                    gen = payload.get("author_generation", "UNSPECIFIED")
                    urb = payload.get("author_urbanicity", "UNSPECIFIED")
                    reg = payload.get("author_macro_region", "UNSPECIFIED")
                    score = float(payload.get("constructiveness_score", 0.5))
                    status_p = payload.get("moderation_status", "APPROVED")
                    if qid and body:
                        p_id = payload.get("perspective_id") or f"p_{uuid.uuid4().hex[:8]}"
                        self.add_perspective(
                            perspective_id=p_id,
                            question_id=qid,
                            choice_letter=choice,
                            author_salt=rater_salt,
                            body=body,
                            author_generation=gen,
                            author_urbanicity=urb,
                            author_macro_region=reg,
                            moderation_status=status_p,
                        )
                        results.append({"index": idx, "action": action_type, "status": "ok", "perspective_id": p_id})
                    else:
                        results.append({"index": idx, "action": action_type, "status": "skipped"})
                else:
                    results.append({"index": idx, "action": action_type, "status": "unrecognized"})

            except Exception as e:
                errors.append({"index": idx, "action": action_type, "error": str(e)})

        # Log batch execution
        batch_status = "SUCCESS" if not errors else ("PARTIAL" if results else "FAILED")
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO sync_logs (batch_id, rater_salt, action_count, status, created_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(batch_id) DO UPDATE SET
                   status = excluded.status,
                   action_count = excluded.action_count;""",
                (actual_batch_id, rater_salt, len(actions), batch_status),
            )

        return {
            "status": "ok" if not errors else "partial",
            "batch_id": actual_batch_id,
            "processed_count": len(results),
            "error_count": len(errors),
            "results": results,
            "errors": errors,
        }



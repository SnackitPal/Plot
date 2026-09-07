-- PLOT / The Cultural Atlas - SQLite Schema
-- Designed for local-first execution, zero cloud dependencies, and fast spatial aggregation.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS slates (
    slate_id TEXT PRIMARY KEY,
    day_number INTEGER UNIQUE,
    release_date TEXT NOT NULL UNIQUE,       -- ISO-8601 YYYY-MM-DD
    title TEXT NOT NULL,
    domain_tags TEXT DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
    question_id TEXT PRIMARY KEY,
    slate_id TEXT NOT NULL,
    order_idx INTEGER NOT NULL,
    category TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'WORK_MOBILITY',
    axis TEXT NOT NULL DEFAULT 'autonomy',
    tier_mode TEXT NOT NULL DEFAULT 'MULTI_TIER',
    allowed_tiers TEXT NOT NULL DEFAULT '[1,2,3]',
    min_verification_tier INTEGER NOT NULL DEFAULT 1,
    is_multi_tier INTEGER NOT NULL DEFAULT 1,
    prompt TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(slate_id) REFERENCES slates(slate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS choices (
    choice_id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    letter TEXT NOT NULL,                    -- 'A', 'B', 'C', 'D'
    label TEXT NOT NULL,
    shape_symbol TEXT NOT NULL,              -- 'circle', 'triangle', 'square', 'diamond'
    color_hex TEXT NOT NULL,
    FOREIGN KEY(question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    UNIQUE(question_id, letter)
);

CREATE TABLE IF NOT EXISTS hex_aggregates (
    question_id TEXT NOT NULL,
    h3_cell_id TEXT NOT NULL,
    choice_letter TEXT NOT NULL,
    vote_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(question_id, h3_cell_id, choice_letter),
    FOREIGN KEY(question_id) REFERENCES questions(question_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS perspectives (
    perspective_id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    choice_letter TEXT NOT NULL,
    body TEXT NOT NULL,
    author_salt TEXT NOT NULL,               -- Pseudonymous rotating client hash
    author_generation TEXT DEFAULT 'UNSPECIFIED',
    author_urbanicity TEXT DEFAULT 'UNSPECIFIED',
    author_macro_region TEXT DEFAULT 'UNSPECIFIED',
    moderation_status TEXT DEFAULT 'APPROVED', -- 'APPROVED', 'FLAGGED', 'REJECTED'
    moderation_flags TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(question_id) REFERENCES questions(question_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS perspective_ratings (
    rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
    perspective_id TEXT NOT NULL,
    rater_salt TEXT NOT NULL,
    rating_score REAL NOT NULL,              -- 1.0 (helpful / agree) or 0.0 (unhelpful)
    rating_category TEXT DEFAULT 'HELPFUL_BRIDGE', -- 'HELPFUL_BRIDGE', 'INFORMATIVE', 'ECHO_ONLY', 'UNHELPFUL'
    rater_generation TEXT DEFAULT 'UNSPECIFIED',
    rater_urbanicity TEXT DEFAULT 'UNSPECIFIED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(perspective_id) REFERENCES perspectives(perspective_id) ON DELETE CASCADE,
    UNIQUE(perspective_id, rater_salt)
);

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

CREATE TABLE IF NOT EXISTS reputation_ledger (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_salt TEXT NOT NULL,
    perspective_id TEXT,
    event_type TEXT NOT NULL, -- 'BRIDGING_YIELD', 'KARMA_AWARD', 'ECHO_DAMPING'
    delta_amount REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(perspective_id) REFERENCES perspectives(perspective_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS user_demographics (
    rater_salt TEXT PRIMARY KEY,
    generation_cohort TEXT NOT NULL DEFAULT 'UNSPECIFIED',
    urbanicity TEXT NOT NULL DEFAULT 'UNSPECIFIED',
    macro_region TEXT NOT NULL DEFAULT 'UNSPECIFIED',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS perspective_impressions (
    impression_id INTEGER PRIMARY KEY AUTOINCREMENT,
    perspective_id TEXT NOT NULL,
    rater_salt TEXT NOT NULL,
    cohort_val TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(perspective_id) REFERENCES perspectives(perspective_id) ON DELETE CASCADE,
    UNIQUE(perspective_id, rater_salt)
);

CREATE INDEX IF NOT EXISTS idx_hex_aggregates_q ON hex_aggregates(question_id);
CREATE INDEX IF NOT EXISTS idx_perspectives_q ON perspectives(question_id);
CREATE INDEX IF NOT EXISTS idx_perspective_ratings_p ON perspective_ratings(perspective_id);
CREATE INDEX IF NOT EXISTS idx_perspective_impressions_p ON perspective_impressions(perspective_id, cohort_val);

CREATE TABLE IF NOT EXISTS calibration_guesses (
    guess_id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    rater_salt TEXT NOT NULL,
    pred_a REAL NOT NULL,
    pred_b REAL NOT NULL,
    pred_c REAL NOT NULL,
    pred_d REAL NOT NULL,
    brier_score REAL NOT NULL,
    calibration_index INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(question_id) REFERENCES questions(question_id) ON DELETE CASCADE,
    UNIQUE(question_id, rater_salt)
);

CREATE INDEX IF NOT EXISTS idx_calibration_q ON calibration_guesses(question_id);
CREATE INDEX IF NOT EXISTS idx_calibration_rater ON calibration_guesses(rater_salt);

CREATE TABLE IF NOT EXISTS user_votes (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_salt TEXT NOT NULL,
    question_id TEXT NOT NULL,
    choice_letter TEXT NOT NULL,
    region_key TEXT,
    tier_level INTEGER NOT NULL DEFAULT 1,
    verification_sig TEXT DEFAULT NULL,
    verified_at TIMESTAMP DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rater_salt, question_id)
);

CREATE INDEX IF NOT EXISTS idx_user_votes_rater ON user_votes(rater_salt);

CREATE TABLE IF NOT EXISTS user_archetype_profiles (
    rater_salt TEXT PRIMARY KEY,
    archetype_title TEXT NOT NULL,
    primary_city TEXT NOT NULL,
    primary_city_country TEXT NOT NULL,
    primary_city_flag TEXT NOT NULL,
    match_pct REAL NOT NULL,
    counter_city TEXT NOT NULL,
    counter_city_country TEXT NOT NULL,
    counter_city_flag TEXT NOT NULL,
    counter_match_pct REAL NOT NULL,
    vector_autonomy REAL NOT NULL,
    vector_punctuality REAL NOT NULL,
    vector_boundary REAL NOT NULL,
    vector_freedom REAL NOT NULL,
    vector_trust REAL NOT NULL,
    summary_narrative TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_compass_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_salt TEXT NOT NULL,
    slate_id TEXT NOT NULL,
    day_number INTEGER NOT NULL,
    num_votes INTEGER DEFAULT 0,
    archetype_title TEXT DEFAULT '',
    vector_autonomy REAL NOT NULL,
    vector_punctuality REAL NOT NULL,
    vector_boundary REAL NOT NULL,
    vector_freedom REAL NOT NULL,
    vector_trust REAL NOT NULL,
    primary_city TEXT NOT NULL,
    match_pct REAL NOT NULL,
    confidence_pct INTEGER NOT NULL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(slate_id) REFERENCES slates(slate_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_compass_history_user ON user_compass_history(rater_salt);
CREATE UNIQUE INDEX IF NOT EXISTS idx_compass_history_user_day ON user_compass_history(rater_salt, day_number);

CREATE TABLE IF NOT EXISTS author_reputation (
    rater_salt TEXT PRIMARY KEY,
    active_abs REAL NOT NULL DEFAULT 0.0,
    lifetime_peak_abs REAL NOT NULL DEFAULT 0.0,
    bridging_b_index INTEGER NOT NULL DEFAULT 0,
    calibration_karma REAL NOT NULL DEFAULT 0.0,
    reputation_tier TEXT NOT NULL DEFAULT 'CITIZEN_DELIBERATOR',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reputation_ledger (
    ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rater_salt TEXT NOT NULL,
    perspective_id TEXT,
    event_type TEXT NOT NULL,
    delta_karma REAL NOT NULL DEFAULT 0.0,
    delta_abs REAL NOT NULL DEFAULT 0.0,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bandit_arms (
    arm_id TEXT PRIMARY KEY,
    alpha REAL NOT NULL DEFAULT 1.0,
    beta REAL NOT NULL DEFAULT 1.0,
    pulls INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_logs (
    batch_id TEXT PRIMARY KEY,
    rater_salt TEXT NOT NULL,
    action_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'SUCCESS',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hex_tier_aggregates (
    question_id TEXT NOT NULL,
    h3_cell_id TEXT NOT NULL,
    tier_level INTEGER NOT NULL DEFAULT 1,
    choice_letter TEXT NOT NULL,
    vote_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(question_id, h3_cell_id, tier_level, choice_letter),
    FOREIGN KEY(question_id) REFERENCES questions(question_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hex_tier_q ON hex_tier_aggregates(question_id, tier_level);

CREATE TABLE IF NOT EXISTS user_verifications (
    rater_salt TEXT PRIMARY KEY,
    current_tier INTEGER NOT NULL DEFAULT 1,
    verification_method TEXT DEFAULT 'ANONYMOUS',
    credential_id TEXT,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reputation_weight REAL NOT NULL DEFAULT 1.0
);


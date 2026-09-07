"""
Unit tests for Beta-Bernoulli Thompson Sampling multi-armed bandit
and Contextual Cultural Epistemic Bandit.
"""

import pytest
import math
from atlas.algorithms.bandits import (
    BetaBernoulliBandit,
    ContextualCulturalBandit,
    calculate_question_entropy,
    calculate_regional_variance,
)
from atlas.storage.database import AtlasDatabase


def test_bandit_arm_addition_and_stats():
    bandit = BetaBernoulliBandit(random_seed=42)
    bandit.add_arm("q1", prior_alpha=2.0, prior_beta=2.0)
    stats = bandit.get_stats("q1")

    assert stats["mean"] == 0.5
    assert stats["alpha"] == 2.0
    assert stats["beta"] == 2.0
    assert stats["pulls"] == 0


def test_bandit_learning_and_selection():
    bandit = BetaBernoulliBandit(random_seed=123)
    bandit.add_arm("arm_good")
    bandit.add_arm("arm_poor")

    # Simulate 150 trials where arm_good gives reward 1.0 80% of the time,
    # and arm_poor gives reward 1.0 only 20% of the time.
    for _ in range(150):
        chosen = bandit.select_arm(["arm_good", "arm_poor"])
        if chosen == "arm_good":
            reward = 1.0 if bandit.rng.random() < 0.8 else 0.0
        else:
            reward = 1.0 if bandit.rng.random() < 0.2 else 0.0
        bandit.update(chosen, reward)

    stats_good = bandit.get_stats("arm_good")
    stats_poor = bandit.get_stats("arm_poor")

    assert stats_good["mean"] > stats_poor["mean"]
    assert stats_good["pulls"] > stats_poor["pulls"]


def test_calculate_question_entropy():
    # 1. Uniform 4 choices -> maximum entropy = 1.0
    uniform = {"A": 25, "B": 25, "C": 25, "D": 25}
    h_uniform = calculate_question_entropy(uniform)
    assert pytest.approx(h_uniform, abs=1e-3) == 1.0

    # 2. Monolithic single choice -> zero entropy = 0.0
    mono = {"A": 100, "B": 0, "C": 0, "D": 0}
    h_mono = calculate_question_entropy(mono)
    assert h_mono == 0.0

    # 3. 2 choices 50/50 out of 4 -> log2(2)/log2(4) = 0.5
    half = {"A": 50, "B": 50, "C": 0, "D": 0}
    h_half = calculate_question_entropy(half)
    assert pytest.approx(h_half, abs=1e-3) == 0.5


def test_calculate_regional_variance():
    # Identical regions -> 0.0 variance
    identical_regions = {
        "NORTH_AMERICA": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
        "EAST_ASIA": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
    }
    var_zero = calculate_regional_variance(identical_regions)
    assert var_zero == 0.0

    # Polarized regions
    polarized_regions = {
        "REGION_A": {"A": 0.9, "B": 0.1, "C": 0.0, "D": 0.0},
        "REGION_B": {"A": 0.1, "B": 0.9, "C": 0.0, "D": 0.0},
    }
    var_high = calculate_regional_variance(polarized_regions)
    assert var_high > 0.1


def test_contextual_cultural_bandit_lifecycle():
    db = AtlasDatabase("atlas.db")
    bandit = ContextualCulturalBandit(random_seed=42)
    candidates = db.get_all_candidate_questions()
    assert len(candidates) > 0

    # Recommend a question
    recs = bandit.recommend_discovery_question(candidates, user_completed_ids=[], top_k=1)
    assert len(recs) == 1
    rec = recs[0]
    assert "question_id" in rec
    assert "entropy_norm" in rec
    assert "regional_variance" in rec
    assert "thompson_sample" in rec
    assert "composite_score" in rec
    assert len(rec["question"]["choices"]) >= 2

    # Exclusion test
    rec_excl = bandit.recommend_discovery_question(candidates, user_completed_ids=[rec["question_id"]], top_k=1)
    assert len(rec_excl) == 1
    assert rec_excl[0]["question_id"] != rec["question_id"]

    # Reward update test
    qid = rec["question_id"]
    initial_pulls = bandit.pull_counts.get(qid, 0)
    reward = ContextualCulturalBandit.calculate_composite_epistemic_reward(
        completion=1.0,
        entropy_norm=rec["entropy_norm"],
        regional_variance=rec["regional_variance"]
    )
    assert 0.0 <= reward <= 1.0
    bandit.update(qid, reward)
    assert bandit.pull_counts.get(qid, 0) >= initial_pulls
    stats = bandit.get_stats(qid)
    assert stats["pulls"] >= 1

import os
import json
import pytest
import sqlite3
import tempfile
from atlas.storage.database import AtlasDatabase
from atlas.geo.regions import compute_cartogram_payload

@pytest.fixture
def test_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    
    db = AtlasDatabase(db_path=db_path, auto_seed=True)
    yield db
    try:
        os.remove(db_path)
    except Exception:
        pass

def test_question_tier_selectivity_metadata(test_db):
    """Verify that questions are seeded with tier_mode, allowed_tiers, and is_multi_tier."""
    q = test_db.get_question("q_01")
    assert q is not None
    assert "tier_mode" in q
    assert q["tier_mode"] in ("MULTI_TIER", "SINGLE_TIER_OPEN", "SINGLE_TIER_VERIFIED")
    assert q["min_verification_tier"] >= 1
    assert q["is_multi_tier"] in (0, 1, True, False)

def test_user_vote_with_tier_and_upgrade(test_db):
    """Verify recording an anonymous vote and then upgrading it to verified without double-counting."""
    test_salt = "test_user_alpha"
    qid = "q_01"
    
    # 1. Anonymous vote (Tier 1)
    test_db.record_user_vote(
        rater_salt=test_salt,
        question_id=qid,
        choice_letter="A",
        region_key="US_WEST",
        tier_level=1,
    )
    
    details = test_db.get_user_vote_details(test_salt)
    assert qid in details
    assert details[qid]["choice_letter"] == "A"
    assert details[qid]["tier_level"] == 1
    assert details[qid]["is_verified"] is False
    
    # 2. Upgrade to Tier 2 (Passkey)
    upgraded_cnt = test_db.upgrade_user_vote_tier(
        rater_salt=test_salt,
        new_tier=2,
        verification_method="PASSKEY",
        verification_sig="sig_mock_ecdsa_999",
    )
    assert upgraded_cnt == 1
    
    # Check details after upgrade
    details_after = test_db.get_user_vote_details(test_salt)
    assert details_after[qid]["tier_level"] == 2
    assert details_after[qid]["is_verified"] is True
    assert details_after[qid]["verification_sig"] == "sig_mock_ecdsa_999"
    assert details_after[qid]["verified_at"] is not None
    
    # Check user verification record
    ver = test_db.get_user_verification(test_salt)
    assert ver["current_tier"] == 2
    assert ver["verification_method"] == "PASSKEY"
    assert ver["is_verified"] is True

def test_multi_tier_comparative_aggregates(test_db):
    """Verify that get_question_multi_tier_aggregates computes All vs Verified distributions and divergence."""
    agg = test_db.get_question_multi_tier_aggregates("q_01")
    assert agg["question_id"] == "q_01"
    assert "all" in agg
    assert "verified" in agg
    assert "diff" in agg
    
    assert agg["all"]["total_votes"] > 0
    assert len(agg["all"]["distribution"]) == 4
    assert sum(agg["all"]["distribution"]) == 100
    
    assert agg["verified"]["total_votes"] > 0
    assert len(agg["verified"]["distribution"]) == 4
    assert sum(agg["verified"]["distribution"]) == 100
    
    # Divergence stats
    diff = agg["diff"]
    assert "dominant_choice" in diff
    assert "max_divergence_choice" in diff
    assert "delta_max_divergence" in diff
    assert isinstance(diff["has_significant_split"], bool)

def test_cartogram_tier_filtering(test_db):
    """Verify that compute_cartogram_payload respects tier_filter='verified'."""
    cart_all = compute_cartogram_payload("q_01", test_db, tier_filter="all")
    cart_ver = compute_cartogram_payload("q_01", test_db, tier_filter="verified")
    
    assert cart_all["tier_filter"] == "all"
    assert cart_ver["tier_filter"] == "verified"
    
    assert cart_all["global_summary"]["total_votes"] >= cart_ver["global_summary"]["total_votes"]
    assert len(cart_ver["regions"]) == len(cart_all["regions"])

"""
Unit tests for SQLite repository layer.
"""

import os
import tempfile
import pytest
from atlas.storage.database import AtlasDatabase


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = AtlasDatabase(db_path=path)
    yield db
    if os.path.exists(path):
        os.remove(path)


def test_database_slates_and_questions(temp_db):
    temp_db.create_slate("slate_01", "2026-09-04", "The Daily Slate #1")
    temp_db.add_question("q_01", "slate_01", 1, "MOBILITY", "Would you take a 30% pay cut?")
    temp_db.add_choice("c_01", "q_01", "A", "Yes", "circle", "#FF5E3A")
    temp_db.add_choice("c_02", "q_01", "B", "No", "triangle", "#3A86FF")

    # Record hex votes
    temp_db.record_hex_vote("q_01", "831207fffffffff", "A", increment=5)
    temp_db.record_hex_vote("q_01", "831207fffffffff", "B", increment=3)

    dist = temp_db.get_cell_distribution("q_01", "831207fffffffff")
    assert dist["A"] == 5
    assert dist["B"] == 3
    assert temp_db.get_cell_total_votes("q_01", "831207fffffffff") == 8


def test_perspectives_and_ratings(temp_db):
    temp_db.create_slate("slate_02", "2026-09-05", "The Daily Slate #2")
    temp_db.add_question("q_02", "slate_02", 1, "ETHICS", "Question 2")
    
    # Add perspective
    temp_db.add_perspective("p_01", "q_02", "A", "Commuting drains life quality.", "user_hash_123")
    
    # Rate perspective
    temp_db.rate_perspective("p_01", "rater_a", 1.0)
    temp_db.rate_perspective("p_01", "rater_b", 1.0)

    ratings = temp_db.get_all_ratings_for_question("q_02")
    assert len(ratings) == 2
    assert ratings[0][1] == "p_01"
    assert ratings[0][2] == 1.0


def test_active_slate_and_seeding(temp_db):
    temp_db.seed_default_data_if_empty()
    slate = temp_db.get_active_slate()
    assert slate is not None
    assert slate["slate_id"] == "slate_daily_01"
    assert len(slate["questions"]) == 5
    assert len(slate["questions"][0]["choices"]) == 4

    # Test cartogram payload generation
    from atlas.geo.regions import compute_cartogram_payload
    payload = compute_cartogram_payload("q_01", temp_db)
    assert "regions" in payload
    assert "US_WEST" in payload["regions"]
    assert payload["regions"]["US_WEST"]["dominant"] == "A"
    assert payload["regions"]["US_WEST"]["sample"] == 12450
    assert payload["regions"]["CENTRAL_ASIA"]["is_hatched"] is True

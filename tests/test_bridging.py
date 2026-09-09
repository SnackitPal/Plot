"""
Unit tests for Twitter Community Notes Matrix Factorization algorithm.
Verifies identification of bridging consensus vs polarized splits.
"""

import pytest
import numpy as np
from atlas.algorithms.bridging import CommunityNotesMF, BridgingPerspective


def test_bridging_consensus_synthetic_data():
    """
    Construct a polarized dataset:
    - Group L (Users L1, L2, L3) with factor ~ -1.0
    - Group R (Users R1, R2, R3) with factor ~ +1.0
    - Perspective 'bridge_1': rated 1.0 by both Group L and Group R (Common Ground)
    - Perspective 'polar_1': rated 1.0 by Group L, 0.0 by Group R (The Split)
    - Perspective 'low_sample': rated by only 2 users (Needs More Ratings)
    """
    ratings = []
    
    # Common Ground: high agreement across both groups
    for u in ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]:
        ratings.append((u, "bridge_1", 1.0))
        
    # Polarizing item: Group L agrees, Group R disagrees
    for u in ["L1", "L2", "L3", "L4"]:
        ratings.append((u, "polar_1", 1.0))
    for u in ["R1", "R2", "R3", "R4"]:
        ratings.append((u, "polar_1", 0.0))

    # Low sample item
    ratings.append(("L1", "low_sample", 1.0))
    ratings.append(("R1", "low_sample", 1.0))

    model = CommunityNotesMF(
        n_factors=1,
        learning_rate=0.08,
        n_epochs=60,
        helpfulness_threshold=0.65,
        polarization_tolerance=0.35,
        min_ratings=5,
        random_seed=42,
    )
    model.fit(ratings)

    # Evaluate bridge perspective
    eval_bridge = model.evaluate_perspective("bridge_1")
    assert eval_bridge.status == "COMMON_GROUND"
    assert eval_bridge.rating_count == 8
    assert eval_bridge.intercept_quality > 0.70

    # Evaluate polar perspective
    eval_polar = model.evaluate_perspective("polar_1")
    assert eval_polar.status == "THE_SPLIT"
    assert eval_polar.rating_count == 8
    assert eval_polar.latent_factor > eval_bridge.latent_factor

    # Evaluate low sample perspective
    eval_low = model.evaluate_perspective("low_sample")
    assert eval_low.status == "NEEDS_MORE_RATINGS"
    assert eval_low.rating_count == 2


def test_predict_bounds():
    """Verify predictions are strictly bounded within [0, 1]."""
    ratings = [("u1", "p1", 1.0), ("u2", "p1", 0.0)]
    model = CommunityNotesMF(n_epochs=5).fit(ratings)
    
    pred = model.predict("u1", "p1")
    assert 0.0 <= pred <= 1.0

    pred_unknown = model.predict("unknown_user", "unknown_item")
    assert 0.0 <= pred_unknown <= 1.0

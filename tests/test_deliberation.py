"""
Unit tests for Polis-style deliberation engine (PCA + K-Means).
"""

import pytest
import numpy as np
from atlas.algorithms.deliberation import PolisDeliberationEngine


def test_deliberation_clustering_and_consensus():
    voters = ["v1", "v2", "v3", "v4", "v5", "v6"]
    perspectives = ["p_consensus", "p_polarizing", "p_neutral"]

    # Construct votes matrix (Shape: 6 voters x 3 perspectives)
    # Voters 0-2 (Cluster A): Agree on p_consensus (1), Agree on p_polarizing (1), Neutral (0)
    # Voters 3-5 (Cluster B): Agree on p_consensus (1), Disagree on p_polarizing (-1), Neutral (0)
    matrix = np.array([
        [1.0,  1.0, 0.0],
        [1.0,  1.0, 0.0],
        [1.0,  1.0, 0.0],
        [1.0, -1.0, 0.0],
        [1.0, -1.0, 0.0],
        [1.0, -1.0, 0.0],
    ])

    engine = PolisDeliberationEngine(n_clusters=2, random_seed=42)
    landscape = engine.analyze(voters, perspectives, matrix)

    assert len(landscape.clusters) == 2
    assert "p_consensus" in landscape.consensus_perspectives
    assert "p_polarizing" in landscape.polarizing_perspectives
    assert len(landscape.voter_coordinates) == 6

    # Verify Cluster separation: voters 0-2 should share a cluster, 3-5 share another
    c_group_a = landscape.voter_clusters["v1"]
    assert landscape.voter_clusters["v2"] == c_group_a
    assert landscape.voter_clusters["v3"] == c_group_a

    c_group_b = landscape.voter_clusters["v4"]
    assert landscape.voter_clusters["v5"] == c_group_b
    assert landscape.voter_clusters["v6"] == c_group_b
    assert c_group_a != c_group_b

"""
Polis-Style Deliberative Clustering and Dimensionality Reduction.
Reference: https://github.com/compdemocracy/polis
Maps participant voting patterns into a 2D opinion landscape using PCA and K-Means.
Surfaces consensus statements vs polarizing fault-line statements across opinion clusters.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any
import numpy as np
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans


@dataclass
class OpinionCluster:
    cluster_id: int
    size: int
    mean_coordinates: Tuple[float, float]
    top_perspectives: List[str]


@dataclass
class DeliberationLandscape:
    voter_coordinates: Dict[str, Tuple[float, float]]  # voter_id -> (x, y)
    voter_clusters: Dict[str, int]                     # voter_id -> cluster_id
    clusters: List[OpinionCluster]
    consensus_perspectives: List[str]                  # Agreed across all clusters
    polarizing_perspectives: List[str]                 # High variance between clusters


class PolisDeliberationEngine:
    """
    Deliberative analysis engine using PCA and K-Means on sparse opinion matrices.
    """

    def __init__(self, n_clusters: int = 2, random_seed: int = 42):
        self.n_clusters = n_clusters
        self.random_seed = random_seed

    def analyze(
        self,
        voters: List[str],
        perspectives: List[str],
        votes_matrix: np.ndarray,  # Shape: (len(voters), len(perspectives)), values in {-1, 0, 1}
    ) -> DeliberationLandscape:
        """
        Analyze the voting matrix:
        -1 = disagree, 0 = pass / unvoted, 1 = agree
        """
        n_voters, n_items = votes_matrix.shape
        if n_voters < 2 or n_items < 2:
            # Fallback for trivial data
            coords = {v: (0.0, 0.0) for v in voters}
            clusts = {v: 0 for v in voters}
            return DeliberationLandscape(
                voter_coordinates=coords,
                voter_clusters=clusts,
                clusters=[OpinionCluster(0, n_voters, (0.0, 0.0), perspectives)],
                consensus_perspectives=perspectives,
                polarizing_perspectives=[],
            )

        # 1. 2D PCA Projection
        n_comp = min(2, min(n_voters, n_items))
        pca = PCA(n_components=n_comp, random_state=self.random_seed)
        coords_2d = pca.fit_transform(votes_matrix)

        if n_comp < 2:
            # Pad with 0 for single component
            coords_2d = np.hstack([coords_2d, np.zeros((n_voters, 1))])

        # 2. K-Means Clustering
        actual_clusters = min(self.n_clusters, n_voters)
        kmeans = KMeans(n_clusters=actual_clusters, random_state=self.random_seed, n_init=10)
        cluster_labels = kmeans.fit_predict(coords_2d)

        # 3. Identify Consensus vs Polarizing Perspectives
        # Compute mean agreement per cluster for each item
        cluster_means: Dict[int, np.ndarray] = {}
        for c in range(actual_clusters):
            members = votes_matrix[cluster_labels == c]
            if len(members) > 0:
                cluster_means[c] = np.mean(members, axis=0)
            else:
                cluster_means[c] = np.zeros(n_items)

        consensus_items = []
        polarizing_items = []

        for idx, item in enumerate(perspectives):
            means = [cluster_means[c][idx] for c in range(actual_clusters)]
            # Consensus: all clusters lean positive (> 0.2)
            if all(m > 0.2 for m in means):
                consensus_items.append(item)
            # Polarizing: large difference between max and min cluster mean (> 0.6)
            elif (max(means) - min(means)) > 0.6:
                polarizing_items.append(item)

        # Build output objects
        voter_coords_map = {
            v: (round(float(coords_2d[i, 0]), 4), round(float(coords_2d[i, 1]), 4))
            for i, v in enumerate(voters)
        }
        voter_clusts_map = {v: int(cluster_labels[i]) for i, v in enumerate(voters)}

        cluster_summaries = []
        for c in range(actual_clusters):
            count = int(np.sum(cluster_labels == c))
            center = (round(float(kmeans.cluster_centers_[c, 0]), 4), round(float(kmeans.cluster_centers_[c, 1]), 4))
            # Sort perspectives by popularity in this cluster
            top_indices = np.argsort(-cluster_means[c])[:3]
            top_items = [perspectives[i] for i in top_indices if cluster_means[c][i] > 0]
            cluster_summaries.append(OpinionCluster(c, count, center, top_items))

        return DeliberationLandscape(
            voter_coordinates=voter_coords_map,
            voter_clusters=voter_clusts_map,
            clusters=cluster_summaries,
            consensus_perspectives=consensus_items,
            polarizing_perspectives=polarizing_items,
        )

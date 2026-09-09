"""
Consensus & Bridging Algorithm
Inspired by the open-source Twitter / X Community Notes Matrix Factorization engine.
Reference: https://github.com/twitter/communitynotes

Decomposes user perspective ratings into:
  r_hat(u, i) = mu + user_bias(u) + note_quality(i) + dot(user_factor(u), note_factor(i))
Surfaces perspectives that achieve cross-cultural / cross-ideological agreement.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import numpy as np


@dataclass
class BridgingPerspective:
    perspective_id: str
    intercept_quality: float      # i_i: Intrinsic bridging helpfulness
    latent_factor: float          # f_i: Polarizing affinity vector (1D)
    rating_count: int
    status: str                   # 'COMMON_GROUND', 'THE_SPLIT', 'NEEDS_MORE_RATINGS', 'LOW_RESONANCE'


class CommunityNotesMF:
    """
    Regularized Matrix Factorization solver for bridging consensus.
    Solves for user factors and perspective quality scores.
    """

    def __init__(
        self,
        n_factors: int = 1,
        lambda_user: float = 0.15,
        lambda_item: float = 0.15,
        learning_rate: float = 0.05,
        n_epochs: int = 40,
        helpfulness_threshold: float = 0.65,
        polarization_tolerance: float = 0.30,
        min_ratings: int = 5,
        random_seed: int = 42,
    ):
        self.n_factors = n_factors
        self.lambda_user = lambda_user
        self.lambda_item = lambda_item
        self.lr = learning_rate
        self.n_epochs = n_epochs
        self.helpfulness_threshold = helpfulness_threshold
        self.polarization_tolerance = polarization_tolerance
        self.min_ratings = min_ratings
        self.rng = np.random.default_rng(random_seed)

        self.global_mean: float = 0.5
        self.user_bias: Dict[str, float] = {}
        self.item_bias: Dict[str, float] = {}
        self.user_factors: Dict[str, np.ndarray] = {}
        self.item_factors: Dict[str, np.ndarray] = {}
        self.raw_ratings: List[Tuple[str, str, float]] = []

    def fit(self, ratings: List[Tuple[str, str, float]]) -> "CommunityNotesMF":
        """
        Fit model on a list of (user_id, perspective_id, rating_score).
        rating_score should be in [0.0, 1.0].
        """
        if not ratings:
            return self

        self.raw_ratings = list(ratings)

        # Extract unique users and items
        users = sorted(list({r[0] for r in ratings}))
        items = sorted(list({r[1] for r in ratings}))

        # Compute item counts and global mean
        self.item_counts = {item: 0 for item in items}
        total_score = 0.0
        for _, item_id, score in ratings:
            self.item_counts[item_id] += 1
            total_score += score
        self.global_mean = total_score / len(ratings)

        # Initialize parameters
        self.user_bias = {u: 0.0 for u in users}
        self.item_bias = {i: 0.0 for i in items}
        self.user_factors = {
            u: self.rng.normal(0.0, 0.05, size=self.n_factors) for u in users
        }
        self.item_factors = {
            i: self.rng.normal(0.0, 0.05, size=self.n_factors) for i in items
        }

        # SGD Optimization loop
        ratings_list = list(ratings)
        for _ in range(self.n_epochs):
            self.rng.shuffle(ratings_list)
            for user_id, item_id, score in ratings_list:
                pred = (
                    self.global_mean
                    + self.user_bias[user_id]
                    + self.item_bias[item_id]
                    + np.dot(self.user_factors[user_id], self.item_factors[item_id])
                )
                err = score - pred

                # Gradients with L2 regularization
                # Intercepts
                self.user_bias[user_id] += self.lr * (
                    err - self.lambda_user * self.user_bias[user_id]
                )
                self.item_bias[item_id] += self.lr * (
                    err - self.lambda_item * self.item_bias[item_id]
                )

                # Latent factors
                u_factors_prev = self.user_factors[user_id].copy()
                i_factors_prev = self.item_factors[item_id].copy()

                self.user_factors[user_id] += self.lr * (
                    err * i_factors_prev - self.lambda_user * u_factors_prev
                )
                self.item_factors[item_id] += self.lr * (
                    err * u_factors_prev - self.lambda_item * i_factors_prev
                )

        return self

    def predict(self, user_id: str, item_id: str) -> float:
        """Predict expected rating for a user-item pair."""
        u_b = self.user_bias.get(user_id, 0.0)
        i_b = self.item_bias.get(item_id, 0.0)
        u_f = self.user_factors.get(user_id, np.zeros(self.n_factors))
        i_f = self.item_factors.get(item_id, np.zeros(self.n_factors))
        pred = self.global_mean + u_b + i_b + float(np.dot(u_f, i_f))
        return float(np.clip(pred, 0.0, 1.0))

    def evaluate_perspective(self, perspective_id: str) -> BridgingPerspective:
        """
        Classify perspective using Community Notes bridging consensus:
        Groups users by their latent coordinates (f_u) and tests whether agreement
        transcends the ideological divide.
        """
        ratings_for_item = [(u, s) for u, i, s in self.raw_ratings if i == perspective_id]
        count = len(ratings_for_item)
        effective_quality = self.global_mean + self.item_bias.get(perspective_id, 0.0)

        if count < self.min_ratings:
            return BridgingPerspective(
                perspective_id=perspective_id,
                intercept_quality=round(effective_quality, 4),
                latent_factor=0.0,
                rating_count=count,
                status="NEEDS_MORE_RATINGS",
            )

        # Partition users into opposing cohorts based on learned latent coordinates
        pos_cohort = [s for u, s in ratings_for_item if self.user_factors.get(u, np.zeros(1))[0] >= 0.0]
        neg_cohort = [s for u, s in ratings_for_item if self.user_factors.get(u, np.zeros(1))[0] < 0.0]

        mean_pos = float(np.mean(pos_cohort)) if pos_cohort else float(effective_quality)
        mean_neg = float(np.mean(neg_cohort)) if neg_cohort else float(effective_quality)

        bridging_agreement = min(mean_pos, mean_neg)
        split_divergence = abs(mean_pos - mean_neg)

        if bridging_agreement >= self.helpfulness_threshold and split_divergence <= self.polarization_tolerance:
            status = "COMMON_GROUND"
        elif split_divergence > self.polarization_tolerance:
            status = "THE_SPLIT"
        else:
            status = "LOW_RESONANCE"

        return BridgingPerspective(
            perspective_id=perspective_id,
            intercept_quality=round(effective_quality, 4),
            latent_factor=round(split_divergence, 4),
            rating_count=count,
            status=status,
        )

    def get_all_evaluations(self) -> List[BridgingPerspective]:
        """Return evaluations for all fitted perspectives."""
        return [self.evaluate_perspective(item_id) for item_id in self.item_bias.keys()]

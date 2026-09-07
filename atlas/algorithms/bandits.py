"""
Multi-Armed Bandit Routing Subsystem
Implements Beta-Bernoulli Thompson Sampling for adaptive question discovery.
Balances exploration of new candidate questions with exploitation of high-resonance slates.
"""

from typing import Any, Dict, List, Optional, Union
import numpy as np


class BetaBernoulliBandit:
    """
    Beta-Bernoulli Thompson Sampling algorithm.
    Used for routing questions to users to maximize engagement and discovery.
    """

    def __init__(self, random_seed: Optional[int] = 42):
        self.rng = np.random.default_rng(random_seed)
        # arm_id -> [alpha, beta]
        self.arms: Dict[str, List[float]] = {}
        # arm_id -> total impressions
        self.pull_counts: Dict[str, int] = {}

    def add_arm(self, arm_id: str, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        """Register a new question / slate arm with uniform or empirical priors."""
        if arm_id not in self.arms:
            self.arms[arm_id] = [prior_alpha, prior_beta]
            self.pull_counts[arm_id] = 0

    def select_arm(self, candidate_arms: Optional[List[str]] = None) -> str:
        """
        Draw a sample from the posterior Beta distribution for each arm,
        and select the arm with the highest drawn sample.
        """
        active_arms = candidate_arms if candidate_arms is not None else list(self.arms.keys())
        if not active_arms:
            raise ValueError("No arms available for selection.")

        # Ensure all candidate arms exist
        for arm in active_arms:
            if arm not in self.arms:
                self.add_arm(arm)

        sampled_values = {}
        for arm in active_arms:
            a, b = self.arms[arm]
            sample = self.rng.beta(a, b)
            sampled_values[arm] = sample

        # Argmax selection
        chosen_arm = max(sampled_values, key=sampled_values.get)
        self.pull_counts[chosen_arm] += 1
        return chosen_arm

    def update(self, arm_id: str, reward: float):
        """
        Update the posterior distribution for an arm given a binary or bounded reward [0, 1].
        Reward = 1.0 (completed answer, shared card, or rated perspective).
        Reward = 0.0 (bounced / skipped question).
        """
        if arm_id not in self.arms:
            self.add_arm(arm_id)

        clipped_reward = float(np.clip(reward, 0.0, 1.0))
        self.arms[arm_id][0] += clipped_reward
        self.arms[arm_id][1] += (1.0 - clipped_reward)

    def get_stats(self, arm_id: str) -> Dict[str, float]:
        """Return expected reward mean and uncertainty (variance) for an arm."""
        if arm_id not in self.arms:
            return {"mean": 0.5, "variance": 0.0833, "pulls": 0}
        a, b = self.arms[arm_id]
        mean = a / (a + b)
        variance = (a * b) / (((a + b) ** 2) * (a + b + 1))
        return {
            "mean": round(mean, 4),
            "variance": round(variance, 6),
            "alpha": round(a, 2),
            "beta": round(b, 2),
            "pulls": self.pull_counts[arm_id],
        }


def calculate_question_entropy(dist: List[float]) -> float:
    """
    Calculate normalized Shannon entropy h(q) in [0.0, 1.0] for a distribution over choices.
    Maximum entropy (h = 1.0) occurs under uniform disagreement (e.g. 25% across 4 options).
    Minimum entropy (h = 0.0) occurs under monolithic consensus (100% on one option).
    """
    if not dist:
        return 0.0
    if isinstance(dist, dict):
        dist = list(dist.values())
    arr = np.array(dist, dtype=float)
    total = np.sum(arr)
    if total <= 0:
        return 0.0
    probs = arr / total
    # Filter non-zeros to avoid log(0)
    pos_probs = probs[probs > 0]
    if len(pos_probs) <= 1:
        return 0.0
    entropy = -float(np.sum(pos_probs * np.log2(pos_probs)))
    max_entropy = float(np.log2(len(probs)))
    return round(float(np.clip(entropy / max_entropy, 0.0, 1.0)), 4)


def calculate_regional_variance(regional_distributions: Dict[str, Any]) -> float:
    """
    Calculate cross-regional cultural variance sigma_geo^2 across geographic regions.
    Measures how strongly cultural stance varies by geography.
    """
    if not regional_distributions or len(regional_distributions) < 2:
        return 0.0

    dists = []
    for d in regional_distributions.values():
        if isinstance(d, dict):
            d = list(d.values())
        arr = np.array(d, dtype=float)
        tot = np.sum(arr)
        if tot > 0:
            dists.append(arr / tot)

    if len(dists) < 2:
        return 0.0

    matrix = np.array(dists)  # Shape (R, K)
    mean_dist = np.mean(matrix, axis=0)  # Shape (K,)
    # Sum of squared deviations per region, averaged across regions
    deviations = matrix - mean_dist
    var = float(np.mean(np.sum(deviations ** 2, axis=1)))
    return round(float(np.clip(var, 0.0, 1.0)), 4)


class ContextualCulturalBandit(BetaBernoulliBandit):
    """
    Contextual Thompson Sampling Bandit for Cultural Dilemma Discovery.
    Optimizes for Epistemic Information Gain rather than clickbait.
    Weights exploration by choice entropy and cross-regional polarization.
    """

    def __init__(self, random_seed: Optional[int] = 42):
        super().__init__(random_seed=random_seed)

    @staticmethod
    def calculate_composite_epistemic_reward(
        completion: float,
        entropy_norm: float,
        regional_variance: float
    ) -> float:
        """
        Compute bounded reward in [0.0, 1.0] balancing:
        - 40% completion / retention engagement
        - 35% normalized choice entropy (discord richness)
        - 25% regional variance (geographic cultural divergence)
        """
        c = float(np.clip(completion, 0.0, 1.0))
        h = float(np.clip(entropy_norm, 0.0, 1.0))
        v = float(np.clip(regional_variance * 4.0, 0.0, 1.0))
        reward = 0.40 * c + 0.35 * h + 0.25 * v
        return round(float(np.clip(reward, 0.0, 1.0)), 4)

    def recommend_discovery_question(
        self,
        candidate_questions: List[Dict],
        user_completed_ids: Optional[List[str]] = None,
        top_k: int = 1
    ) -> List[Dict]:
        """
        Recommend candidate question(s) using Thompson Sampling with epistemic weighting.
        Filters out questions the user has already completed.
        """
        completed_set = set(user_completed_ids or [])
        available = [q for q in candidate_questions if q.get("id") not in completed_set]

        # If user completed everything, fallback to full candidate pool
        if not available:
            available = list(candidate_questions)

        if not available:
            return []

        scored = []
        for q in available:
            qid = q.get("id", "")
            if qid not in self.arms:
                # Prior based on baseline distribution entropy if available
                base_dist = q.get("baseline_dist", [25, 25, 25, 25])
                h = calculate_question_entropy(base_dist)
                prior_a = 1.0 + 2.0 * h
                prior_b = 1.0 + 2.0 * (1.0 - h)
                self.add_arm(qid, prior_alpha=prior_a, prior_beta=prior_b)

            a, b = self.arms[qid]
            sample = float(self.rng.beta(a, b))

            # Epistemic multiplier: questions with richer choice variance get a boost
            base_dist = q.get("baseline_dist", [25, 25, 25, 25])
            h = calculate_question_entropy(base_dist)
            v = q.get("regional_variance", 0.0)

            composite_score = sample * (0.65 + 0.35 * h)
            scored.append((composite_score, sample, h, v, q))

        # Sort descending by composite score
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = scored[:top_k]

        results = []
        for comp_score, sample, h, v, q in selected:
            qid = q.get("id", "")
            self.pull_counts[qid] = self.pull_counts.get(qid, 0) + 1
            reason = "High cultural entropy & cross-regional divergence" if h >= 0.8 else "Exploratory candidate for cultural calibration"
            results.append({
                "question": q,
                "question_id": qid,
                "thompson_sample": round(sample, 4),
                "composite_score": round(comp_score, 4),
                "entropy_norm": h,
                "regional_variance": v,
                "recommendation_reason": reason,
            })

        return results

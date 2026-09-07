"""
Algorithmic Subsystem for PLOT / The Cultural Atlas.
Includes:
- bridging: Twitter Community Notes regularized matrix factorization.
- deliberation: Polis-style sparse PCA and consensus clustering.
- shrinkage: Empirical Bayes shrinkage for sparse geographical cells.
- bandits: Thompson Sampling for exploratory question routing.
"""

from .bridging import CommunityNotesMF, BridgingPerspective
from .deliberation import PolisDeliberationEngine, OpinionCluster, DeliberationLandscape
from .shrinkage import EmpiricalBayesShrinkage, SmoothedCellEstimate
from .bandits import (
    BetaBernoulliBandit,
    ContextualCulturalBandit,
    calculate_question_entropy,
    calculate_regional_variance,
)
from .trajectory import calculate_trajectory_analytics, calculate_step_distance
from .cohort_bridging import (
    calculate_wilson_lower_bound,
    calculate_cohort_helpfulness,
    calculate_harmonic_bridge_score,
    classify_bridging_status,
    rank_bridging_perspectives,
)
from .moderation import (
    screen_perspective_submission,
    calculate_shannon_entropy,
    assess_constructiveness,
)
from .bridging_economy import (
    PerspectiveRatingInput,
    BridgingYieldResult,
    AuthorReputationResult,
    calculate_weighted_wilson_lower,
    calculate_perspective_bridging_capital,
    calculate_author_bridging_score,
    calculate_rater_karma_delta,
)

__all__ = [
    "CommunityNotesMF",
    "BridgingPerspective",
    "PolisDeliberationEngine",
    "OpinionCluster",
    "DeliberationLandscape",
    "EmpiricalBayesShrinkage",
    "SmoothedCellEstimate",
    "BetaBernoulliBandit",
    "ContextualCulturalBandit",
    "calculate_question_entropy",
    "calculate_regional_variance",
    "calculate_trajectory_analytics",
    "calculate_step_distance",
    "calculate_wilson_lower_bound",
    "calculate_cohort_helpfulness",
    "calculate_harmonic_bridge_score",
    "classify_bridging_status",
    "rank_bridging_perspectives",
    "screen_perspective_submission",
    "calculate_shannon_entropy",
    "assess_constructiveness",
    "PerspectiveRatingInput",
    "BridgingYieldResult",
    "AuthorReputationResult",
    "calculate_weighted_wilson_lower",
    "calculate_perspective_bridging_capital",
    "calculate_author_bridging_score",
    "calculate_rater_karma_delta",
]


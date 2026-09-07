"""
Unit tests for Empirical Bayes regional cartography shrinkage.
"""

import pytest
from atlas.algorithms.shrinkage import EmpiricalBayesShrinkage


def test_empirical_bayes_zero_sample():
    estimator = EmpiricalBayesShrinkage(prior_mean=0.50, prior_weight=30.0, min_sample_threshold=30)
    est = estimator.estimate_cell("cell_empty", k=0, n=0)

    assert est.sample_size == 0
    assert est.smoothed_rate == 0.50
    assert est.is_hatched is True
    assert est.weight_data == 0.0


def test_empirical_bayes_small_sample_shrinkage():
    # 2 positive votes out of 2 total (raw rate = 100%)
    estimator = EmpiricalBayesShrinkage(prior_mean=0.50, prior_weight=30.0, min_sample_threshold=30)
    est = estimator.estimate_cell("cell_small", k=2, n=2)

    assert est.raw_rate == 1.0
    # Smoothed = (2 + 15) / (2 + 30) = 17 / 32 = 0.53125
    assert 0.52 < est.smoothed_rate < 0.55
    assert est.is_hatched is True  # Below threshold 30
    assert est.weight_data < 0.10


def test_empirical_bayes_large_sample():
    # 600 positive votes out of 1000 total (raw rate = 60%)
    estimator = EmpiricalBayesShrinkage(prior_mean=0.50, prior_weight=30.0, min_sample_threshold=30)
    est = estimator.estimate_cell("cell_large", k=600, n=1000)

    assert est.raw_rate == 0.60
    # Smoothed should be very close to raw rate (60%)
    assert 0.59 < est.smoothed_rate < 0.61
    assert est.is_hatched is False
    assert est.weight_data > 0.95
    assert est.ci_lower < est.smoothed_rate < est.ci_upper
    # 95% CI should be tight
    assert (est.ci_upper - est.ci_lower) < 0.07

"""
Automated unit tests for the heuristic moderation and epistemic screening engine.
Verifies length limits, link blocking, Shannon entropy spam detection, profanity blocking,
and constructiveness scoring.
"""

import pytest
from atlas.algorithms.moderation import (
    screen_perspective_submission,
    calculate_shannon_entropy,
    assess_constructiveness,
)


def test_valid_constructive_submission():
    """Verify that a well-reasoned, constructive perspective passes screening."""
    text = "Saving two hours on the daily commute gives parents crucial time with family because health and balance matter more than money."
    res = screen_perspective_submission(text)
    
    assert res["status"] == "APPROVED"
    assert res["is_approved"] is True
    assert len(res["flags"]) == 0
    assert res["entropy"] >= 3.2
    assert res["constructiveness"]["is_constructive"] is True
    assert "because" in res["constructiveness"]["markers_detected"]


def test_length_boundaries():
    """Verify too short (< 15) and too long (> 280) rejections."""
    # 1. Too short
    short_res = screen_perspective_submission("Too short")
    assert short_res["status"] == "REJECTED"
    assert "TOO_SHORT" in short_res["flags"]
    
    # 2. Too long (300 chars)
    long_text = "A" * 290
    long_res = screen_perspective_submission(long_text)
    assert long_res["status"] == "REJECTED"
    assert "TOO_LONG" in long_res["flags"]


def test_link_detection():
    """Verify that perspectives with URLs, domains, or tracking links are rejected."""
    urls = [
        "Check out this site http://example.com for better answers.",
        "Go to https://scam-crypto.xyz/register right now!",
        "Visit www.culturalatlas.org to see the full data report.",
        "Read the full debate at substack.com/post/12345 today.",
    ]
    for url_text in urls:
        res = screen_perspective_submission(url_text)
        assert res["status"] == "REJECTED", f"Failed to reject link in: {url_text}"
        assert "CONTAINS_LINK" in res["flags"]


def test_shannon_entropy_spam_detection():
    """Verify that low-entropy spam or repetitive gibberish is flagged."""
    spam_cases = [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "asdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdf",
        "12312312312312312312312312312312312312312312312",
    ]
    for spam in spam_cases:
        entropy = calculate_shannon_entropy(spam)
        assert entropy < 2.8, f"Entropy unexpectedly high: {entropy} for {spam}"
        res = screen_perspective_submission(spam)
        assert res["status"] == "REJECTED"
        assert "LOW_ENTROPY_SPAM" in res["flags"]


def test_profanity_and_abuse_detection():
    """Verify that slurs or severe threats are rejected."""
    abusive_samples = [
        "You should just kys right now because nobody likes you.",
        "Go die in a fire you idiot.",
    ]
    for abuse in abusive_samples:
        res = screen_perspective_submission(abuse)
        assert res["status"] == "REJECTED"
        assert "PROFANITY_OR_ABUSE" in res["flags"]


def test_constructiveness_assessment():
    """Verify that constructiveness markers are identified correctly."""
    text_1 = "I prefer remote work rather than offices because the commute cost is a severe tradeoff."
    meta_1 = assess_constructiveness(text_1)
    assert meta_1["is_constructive"] is True
    assert meta_1["score"] >= 0.50
    assert set(meta_1["markers_detected"]).issuperset({"prefer", "rather than", "because", "cost", "tradeoff"})
    
    text_2 = "This option is simply the best and everyone knows it."
    meta_2 = assess_constructiveness(text_2)
    assert meta_2["score"] == 0.0
    assert meta_2["is_constructive"] is False

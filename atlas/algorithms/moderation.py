"""
Automated Heuristic Moderation and Epistemic Screening Engine for PLOT: The Cultural Atlas.
Zero external dependencies. Performs high-throughput client/server screening of community
perspective submissions:
1. Length boundaries (15 - 280 characters).
2. Hyperlink & phishing detection.
3. Shannon entropy character repetition check (H > 2.8 bits/char).
4. Heuristic toxic token and slur blocklist.
5. Epistemic constructiveness scoring (presence of causal/deliberative rationale markers).
"""

import re
import math
from typing import Dict, List, Any, Set

# Regex patterns for hyperlinks and domain extensions
URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.(?:com|org|net|edu|gov|io|xyz|co|ai|app|me|info|tv)\b(?:/\S*)?)",
    re.IGNORECASE,
)

# Standard toxic and abusive keyword blocklist (regex with word boundaries)
# Focuses on severe slurs, targeted threats, and hate speech
ABUSIVE_TOKENS = [
    r"\bkill\s+yourself\b",
    r"\bkys\b",
    r"\bdie\s+in\s+a\s+fire\b",
    r"\bhate\s+all\s+(?:blacks|whites|jews|muslims|gays|trans)\b",
    r"\bnigger\b",
    r"\bfaggot\b",
    r"\bkike\b",
    r"\bchink\b",
    r"\bspic\b",
    r"\bwhore\b",
    r"\bslut\b",
]
ABUSIVE_REGEX = re.compile("|".join(ABUSIVE_TOKENS), re.IGNORECASE)

# Deliberative & causal markers indicative of constructive reasoning
CONSTRUCTIVE_MARKERS: Set[str] = {
    "because",
    "since",
    "in my experience",
    "tradeoff",
    "trade-off",
    "weigh",
    "prefer",
    "reason",
    "cost",
    "rather than",
    "compromise",
    "personally",
    "perspective",
    "crucial",
    "essential",
    "prioritize",
    "balance",
    "consequence",
    "impact",
    "consider",
    "evidence",
    "historically",
    "societal",
    "generational",
}


def calculate_shannon_entropy(text: str) -> float:
    """
    Computes Shannon entropy in bits per character:
        H = - sum(p_i * log2(p_i))
    Low entropy (< 2.8 for strings > 20 chars) indicates repetitive spam or keyboard mash.
    """
    if not text:
        return 0.0
    
    length = len(text)
    freq: Dict[str, int] = {}
    for char in text.lower():
        freq[char] = freq.get(char, 0) + 1
        
    entropy = 0.0
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
        
    return round(entropy, 3)


def assess_constructiveness(text: str) -> Dict[str, Any]:
    """
    Evaluates presence of constructive rationale markers and reasoning indicators.
    Returns constructiveness score in [0.0, 1.0] and detected markers.
    """
    normalized = text.lower()
    detected = []
    
    for marker in CONSTRUCTIVE_MARKERS:
        if marker in normalized:
            detected.append(marker)
            
    # Score is scaled based on detected markers and reasoning breadth
    score = min(1.0, round(len(detected) * 0.25, 2))
    
    return {
        "score": score,
        "is_constructive": len(detected) > 0,
        "markers_detected": detected,
    }


def screen_perspective_submission(text: str) -> Dict[str, Any]:
    """
    Comprehensive screening pipeline for perspective submissions.
    
    Returns:
        Dict with:
          - 'status': 'APPROVED' | 'REJECTED'
          - 'is_approved': bool
          - 'flags': List[str]
          - 'entropy': float
          - 'constructiveness': Dict[str, Any]
          - 'message': str
    """
    trimmed = text.strip()
    flags: List[str] = []
    
    # 1. Length validation
    length = len(trimmed)
    if length < 15:
        flags.append("TOO_SHORT")
    elif length > 280:
        flags.append("TOO_LONG")
        
    # 2. Hyperlink & URL injection validation
    if URL_PATTERN.search(trimmed):
        flags.append("CONTAINS_LINK")
        
    # 3. Shannon entropy & repetition check
    entropy = calculate_shannon_entropy(trimmed)
    if length > 20 and entropy < 2.8:
        flags.append("LOW_ENTROPY_SPAM")
        
    # 4. Abusive language check
    if ABUSIVE_REGEX.search(trimmed):
        flags.append("PROFANITY_OR_ABUSE")
        
    # 5. Constructive evaluation
    constructive_meta = assess_constructiveness(trimmed)
    
    is_approved = len(flags) == 0
    status = "APPROVED" if is_approved else "REJECTED"
    
    message = "Perspective passed moderation screening." if is_approved else f"Rejected: {', '.join(flags)}"
    
    return {
        "status": status,
        "is_approved": is_approved,
        "flags": flags,
        "entropy": entropy,
        "constructiveness": constructive_meta,
        "message": message,
    }

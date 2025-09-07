"""Validation functions for cc_approver package."""
from typing import Optional
from .constants import VALID_DECISIONS, DEFAULT_DECISION, MAX_REASON_LENGTH

def normalize_decision(decision: Optional[str]) -> str:
    """Normalize and validate decision string.
    
    Args:
        decision: Decision string to normalize
        
    Returns:
        Normalized decision (allow/deny/ask)
    """
    normalized = (decision or "").strip().lower()
    return normalized if normalized in VALID_DECISIONS else DEFAULT_DECISION

def validate_path(path: Optional[str]) -> bool:
    """Validate file path.
    
    Args:
        path: Path string to validate
        
    Returns:
        True if path is valid, False otherwise
    """
    return bool(path and isinstance(path, str) and path.strip())

def validate_history_bytes(n: Optional[int]) -> bool:
    """Validate history byte count.
    
    Args:
        n: Number of bytes
        
    Returns:
        True if valid, False otherwise
    """
    return isinstance(n, int) and n > 0

def normalize_label(label: Optional[str]) -> str:
    """Normalize training label.
    
    Args:
        label: Label string to normalize
        
    Returns:
        Normalized label (allow/deny/ask or empty)
    """
    normalized = (label or "").strip().lower()
    return normalized if normalized in VALID_DECISIONS else ""

def truncate_reason(reason: Optional[str]) -> str:
    """Truncate reason to maximum length.
    
    Args:
        reason: Reason string to truncate
        
    Returns:
        Truncated reason string
    """
    return (reason or "")[:MAX_REASON_LENGTH]
"""
PhysiTutor-AI Utility Functions
"""
from datetime import datetime
from typing import Any, Dict
import json


def format_timestamp(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.isoformat()


def safe_json_loads(text: str, default: Any = None) -> Any:
    """Safely parse JSON string."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def calculate_accuracy(correct: int, total: int) -> float:
    """Calculate accuracy percentage."""
    if total == 0:
        return 0.0
    return correct / total


def format_accuracy(accuracy: float) -> str:
    """Format accuracy as percentage string."""
    return f"{accuracy:.1%}"

"""
ResultType enumeration for dogma phase results
"""

from enum import Enum


class ResultType(Enum):
    """Types of phase execution results"""

    SUCCESS = "success"  # Phase succeeded, continue to next
    INTERACTION = "interaction"  # Phase needs player input
    COMPLETE = "complete"  # Dogma execution complete
    ERROR = "error"  # Phase failed with error

"""
This module defines the `Requirement` dataclass, which represents a single software requirement
with various attributes such as ID, description, priority, and additional details.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class Requirement:
    """
    Represents a single software requirement.

    Attributes:
        requirement_id (str): A unique identifier for the requirement.
        description (str): A detailed description of the requirement.
        priority (Optional[str]): The priority level of the requirement (e.g., "high", "medium", "low"). Defaults to None.
        additional_details (Optional[Dict[str, Any]]): A dictionary for any extra, unstructured details
                                                      related to the requirement. Defaults to an empty dictionary.
    """
    requirement_id: str
    description: str
    priority: Optional[str] = None
    additional_details: Optional[Dict[str, Any]] = field(default_factory=dict)

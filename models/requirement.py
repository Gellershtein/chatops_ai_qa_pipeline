
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class Requirement:
    requirement_id: str
    description: str
    priority: Optional[str] = None
    additional_details: Optional[Dict[str, Any]] = field(default_factory=dict)


import json
from models.requirement import Requirement

def run(ctx):
    try:
        data = json.loads(ctx["txt"])
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")

    if not isinstance(data, list):
        data = [data]

    reqs = []
    for item in data:
        if "requirement_id" not in item or "description" not in item:
            raise ValueError("Each requirement must have a 'requirement_id' and 'description'")
        
        reqs.append(Requirement(
            requirement_id=item["requirement_id"],
            description=item["description"],
            priority=item.get("priority"),
            additional_details=item.get("additional_details")
        ))
    
    ctx["requirements"] = reqs

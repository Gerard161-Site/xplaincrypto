import json
from typing import Any

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles special objects."""
    
    def default(self, obj: Any) -> Any:
        # Import here to avoid circular imports
        from backend.research.core import ResearchNode
        
        # Handle ResearchNode objects
        if isinstance(obj, ResearchNode):
            return obj.to_dict()
            
        # Let the base class handle anything else
        return super().default(obj)

def dumps_with_custom_encoder(obj: Any, **kwargs) -> str:
    """Serialize obj to a JSON formatted str using the custom encoder."""
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)

def dump_with_custom_encoder(obj: Any, fp, **kwargs) -> None:
    """Serialize obj as a JSON formatted stream to fp using the custom encoder."""
    return json.dump(obj, fp, cls=CustomJSONEncoder, **kwargs) 
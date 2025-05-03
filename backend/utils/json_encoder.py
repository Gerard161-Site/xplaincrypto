import json
from typing import Any

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles special objects."""
    
    def default(self, obj: Any) -> Any:
        # Handle dictionary-like objects by checking for to_dict method
        if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
            return obj.to_dict()
            
        # Let the base class handle anything else
        return super().default(obj)

def dumps_with_custom_encoder(obj: Any, **kwargs) -> str:
    """Serialize obj to a JSON formatted str using the custom encoder."""
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)

def dump_with_custom_encoder(obj: Any, fp, **kwargs) -> None:
    """Serialize obj as a JSON formatted stream to fp using the custom encoder."""
    return json.dump(obj, fp, cls=CustomJSONEncoder, **kwargs) 
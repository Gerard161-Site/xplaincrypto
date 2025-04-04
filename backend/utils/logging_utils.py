"""Logging utilities for XplainCrypto."""

def log_safe(obj, max_length=500):
    """Create a safe string representation of an object for logging, truncating if too large."""
    if obj is None:
        return "None"
    
    if isinstance(obj, (str, int, float, bool)):
        str_val = str(obj)
        if len(str_val) > max_length:
            return str_val[:max_length] + f"... [truncated, total length: {len(str_val)}]"
        return str_val
    
    if isinstance(obj, (list, tuple)):
        if len(obj) > 10:
            return f"[{', '.join(log_safe(x, max_length=50) for x in obj[:5])}... and {len(obj)-5} more items]"
        return f"[{', '.join(log_safe(x, max_length=100) for x in obj)}]"
    
    if isinstance(obj, dict):
        if len(obj) > 10:
            entries = list(obj.items())[:5]
            return f"{{{', '.join(f'{k}: {log_safe(v, max_length=50)}' for k, v in entries)}... and {len(obj)-5} more keys}}"
        return f"{{{', '.join(f'{k}: {log_safe(v, max_length=100)}' for k, v in obj.items())}}}"
    
    # For other types, use str() with length check
    str_val = str(obj)
    if len(str_val) > max_length:
        return str_val[:max_length] + f"... [truncated, total length: {len(str_val)}]"
    return str_val 
import json
import os
import logging
from typing import Dict, Any, Optional

def load_config(config_path: str, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.
    
    Args:
        config_path: Path to the configuration file
        logger: Optional logger for logging
        
    Returns:
        Dictionary containing the configuration
    """
    if logger:
        log = logger
    else:
        log = logging.getLogger("ConfigLoader")
    
    try:
        if not os.path.exists(config_path):
            log.error(f"Configuration file not found: {config_path}")
            return {}
            
        with open(config_path, "r") as f:
            config = json.load(f)
            
        log.info(f"Loaded configuration from {config_path}")
        return config
    except json.JSONDecodeError as e:
        log.error(f"Invalid JSON in configuration file {config_path}: {str(e)}")
        return {}
    except Exception as e:
        log.error(f"Error loading configuration from {config_path}: {str(e)}")
        return {}

def save_config(config_data: Dict[str, Any], config_path: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    Save configuration to a JSON file.
    
    Args:
        config_data: Configuration data to save
        config_path: Path where to save the configuration
        logger: Optional logger for logging
        
    Returns:
        True if successful, False otherwise
    """
    if logger:
        log = logger
    else:
        log = logging.getLogger("ConfigLoader")
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
            
        log.info(f"Saved configuration to {config_path}")
        return True
    except Exception as e:
        log.error(f"Error saving configuration to {config_path}: {str(e)}")
        return False

def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two configuration dictionaries, with override_config taking precedence.
    
    Args:
        base_config: Base configuration
        override_config: Configuration that overrides base_config
        
    Returns:
        Merged configuration dictionary
    """
    result = base_config.copy()
    
    for key, value in override_config.items():
        # If both values are dictionaries, merge them recursively
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            # Otherwise, override or add the value
            result[key] = value
            
    return result

def get_config_with_env_override(config_path: str, env_prefix: str, logger: Optional[logging.Logger] = None) -> Dict[str, Any]:
    """
    Load configuration and override with environment variables.
    
    Environment variables should be named ENVPREFIX_SECTION_KEY.
    For example, with env_prefix="XC", the environment variable XC_LOGGING_LEVEL
    would override the config["logging"]["level"] value.
    
    Args:
        config_path: Path to the configuration file
        env_prefix: Prefix for environment variables
        logger: Optional logger for logging
        
    Returns:
        Configuration dictionary with environment overrides
    """
    config = load_config(config_path, logger)
    
    # Look for environment variables with the specified prefix
    override_config = {}
    for env_name, env_value in os.environ.items():
        if env_name.startswith(f"{env_prefix}_"):
            # Remove the prefix
            key_path = env_name[len(env_prefix) + 1:].lower()
            
            # Split by underscore to get the path
            path_parts = key_path.split('_')
            
            # Build the override config structure
            current = override_config
            for i, part in enumerate(path_parts):
                if i == len(path_parts) - 1:
                    # This is the final key, set the value
                    # Try to convert to appropriate type
                    if env_value.lower() == 'true':
                        current[part] = True
                    elif env_value.lower() == 'false':
                        current[part] = False
                    elif env_value.isdigit():
                        current[part] = int(env_value)
                    elif env_value.replace('.', '', 1).isdigit() and env_value.count('.') <= 1:
                        current[part] = float(env_value)
                    else:
                        current[part] = env_value
                else:
                    # This is an intermediate key, create nested dict if needed
                    if part not in current:
                        current[part] = {}
                    current = current[part]
    
    # Merge the base config with the override config
    return merge_configs(config, override_config) 
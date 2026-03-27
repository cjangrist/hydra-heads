"""Auto-discover and register all provider configs from this directory and ~/.hydra/providers.yaml."""

import importlib
import logging
import os
import pkgutil
from pathlib import Path

logger = logging.getLogger("hydra_heads")

REGISTRY = {}
REQUIRED_PROVIDER_KEYS = {"name", "binary", "args", "prompt_flag"}
USER_CONFIG_PATH = Path(os.getenv("HYDRA_PROVIDERS_FILE", str(Path.home() / ".hydra" / "providers.yaml")))


def _validate_provider_config(config: dict, source_name: str) -> bool:
    """Validate a provider config has all required keys and correct types. Returns True if valid."""
    missing_keys = REQUIRED_PROVIDER_KEYS - set(config.keys())
    if missing_keys:
        logger.warning(f"Provider '{source_name}' missing required keys: {missing_keys}, skipping")
        return False
    if not isinstance(config.get("name"), str) or not config["name"]:
        logger.warning(f"Provider '{source_name}' 'name' must be a non-empty string, skipping")
        return False
    import re as _re
    if _re.search(r'[/\\.\s]', config["name"]):
        logger.warning(f"Provider '{source_name}' 'name' contains invalid characters (/, \\, ., space), skipping")
        return False
    if not isinstance(config.get("binary"), str) or not config["binary"]:
        logger.warning(f"Provider '{source_name}' 'binary' must be a non-empty string, skipping")
        return False
    if not isinstance(config.get("args"), list):
        logger.warning(f"Provider '{source_name}' 'args' must be a list, skipping")
        return False
    if not all(isinstance(a, str) for a in config["args"]):
        logger.warning(f"Provider '{source_name}' 'args' must contain only strings, skipping")
        return False
    provider_env = config.get("env")
    if provider_env is not None and not isinstance(provider_env, dict):
        logger.warning(f"Provider '{source_name}' 'env' must be a dict or null, skipping")
        return False
    prompt_flag = config.get("prompt_flag")
    if prompt_flag is not None and not isinstance(prompt_flag, str):
        logger.warning(f"Provider '{source_name}' 'prompt_flag' must be a string or null, skipping")
        return False
    return True


def _discover_providers() -> None:
    """Import every sibling module and register its PROVIDER dict."""
    package_dir = Path(__file__).parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        try:
            module = importlib.import_module(f"hydra_heads.providers.{module_info.name}")
        except Exception as import_error:
            logger.warning(f"Failed to import provider module '{module_info.name}': {import_error}")
            continue
        provider_config = getattr(module, "PROVIDER", None)
        if provider_config and isinstance(provider_config, dict):
            if _validate_provider_config(provider_config, module_info.name):
                REGISTRY[provider_config["name"]] = provider_config


def _load_user_config() -> None:
    """Load provider overrides/additions from ~/.hydra/providers.yaml if it exists."""
    if not USER_CONFIG_PATH.is_file():
        return
    try:
        import yaml
        raw_yaml = USER_CONFIG_PATH.read_text(encoding="utf-8")
        data = yaml.safe_load(raw_yaml)
        if not isinstance(data, dict) or "providers" not in data:
            logger.warning(f"Invalid providers.yaml format (expected top-level 'providers' key)")
            return
        for provider_entry in data["providers"]:
            if not isinstance(provider_entry, dict):
                continue
            provider_name = provider_entry.get("name")
            if not provider_name:
                logger.warning(f"Provider entry in YAML missing 'name', skipping")
                continue
            if provider_name in REGISTRY:
                merged_config = dict(REGISTRY[provider_name])
                merged_config.update(provider_entry)
                if _validate_provider_config(merged_config, f"yaml:{provider_name}"):
                    REGISTRY[provider_name] = merged_config
                    logger.debug(f"YAML override applied to provider '{provider_name}'")
            else:
                if _validate_provider_config(provider_entry, f"yaml:{provider_name}"):
                    REGISTRY[provider_name] = provider_entry
                    logger.debug(f"YAML added new provider '{provider_name}'")
    except ImportError:
        logger.warning("PyYAML not installed, cannot load providers.yaml")
    except Exception as yaml_error:
        logger.warning(f"Failed to load {USER_CONFIG_PATH}: {yaml_error}")


_discover_providers()
_load_user_config()


def get_provider(name: str) -> dict:
    """Return a deep copy of a provider config by name, or raise KeyError."""
    import copy
    if name not in REGISTRY:
        available = ", ".join(sorted(REGISTRY.keys()))
        raise KeyError(f"Unknown provider '{name}'. Available: {available}")
    return copy.deepcopy(REGISTRY[name])


def list_providers() -> list:
    """Return sorted list of registered provider names."""
    return sorted(REGISTRY.keys())

from urllib.parse import urlparse

import yaml

from src.pulse.models import EndpointConfig
from pathlib import Path

class ConfigError(ValueError):


 def load_config(path: Path) -> list[EndpointConfig]:

    try:
        raw_config = yaml.safe_load(path.read_text())
    except FileNotFoundError as error:
        raise ConfigError(f"Configuration file not found: {path}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {path}: {error}") from error

    if not isinstance(raw_config, dict):
        raise ConfigError("Configuration must be a YAML mapping.")

    raw_checks = raw_config.get("checks")
    if not isinstance(raw_checks, list):
        raise ConfigError("Configuration must contain a 'checks' list.")

    endpoints = [
        _parse_endpoint(raw_check, position)
        for position, raw_check in enumerate(raw_checks, start=1)
    ]

    _ensure_unique_names(endpoints)

    return endpoints

def _parse_endpoint(raw_check: object, position: int) -> EndpointConfig:
     """Convert one YAML check entry into an EndpointConfig."""
     if not isinstance(raw_check, dict):
         raise ConfigError(f"Check {position} must be a mapping.")

     name = raw_check.get("name")
     url = raw_check.get("url")

     if not isinstance(name, str) or not name.strip():
         raise ConfigError(f"Check {position} must have a non-empty 'name'.")

     if not isinstance(url, str) or not _is_valid_http_url(url):
         raise ConfigError(
             f"Check '{name}' must have a valid HTTP or HTTPS 'url'."
         )

     expected_status = _read_expected_status(
         raw_check.get("expected_status", 200),
         name,
     )
     timeout_seconds = _read_timeout_seconds(
         raw_check.get("timeout_seconds", 5.0),
         name,
     )

     return EndpointConfig(
         name=name,
         url=url,
         expected_status=expected_status,
         timeout_seconds=timeout_seconds,
     )

def _read_expected_status(value: object, check_name: str) -> int:
     """Validate an expected HTTP status code."""
     if isinstance(value, bool) or not isinstance(value, int):
         raise ConfigError(
             f"Check '{check_name}' has an invalid 'expected_status'. "
             "It must be an integer."
         )

     if not 100 <= value <= 599:
         raise ConfigError(
             f"Check '{check_name}' has an invalid 'expected_status'. "
             "It must be between 100 and 599."
         )

     return value

def _read_timeout_seconds(value: object, check_name: str) -> float:
     """Validate an HTTP timeout value."""
     if isinstance(value, bool) or not isinstance(value, int | float):
         raise ConfigError(
             f"Check '{check_name}' has an invalid 'timeout_seconds'. "
             "It must be a number."
         )

     timeout_seconds = float(value)

     if timeout_seconds <= 0:
         raise ConfigError(
             f"Check '{check_name}' has an invalid 'timeout_seconds'. "
             "It must be greater than zero."
         )

     return timeout_seconds

def _is_valid_http_url(value: str) -> bool:
     """Return whether a URL has an HTTP scheme and hostname."""
     parsed_url = urlparse(value)

     return parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)

def _ensure_unique_names(endpoints: list[EndpointConfig]) -> None:
     """Reject duplicate endpoint names."""
     names = [endpoint.name for endpoint in endpoints]
     duplicate_names = {name for name in names if names.count(name) > 1}

     if duplicate_names:
         duplicates = ", ".join(sorted(duplicate_names))
         raise ConfigError(
             f"Check names must be unique. Duplicate names: {duplicates}"
         )
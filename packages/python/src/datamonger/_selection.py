"""Resolve strong registry selectors across Python configuration scopes."""

from __future__ import annotations

import json
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from datamonger._errors import RegistryError
from datamonger._models import Pathish, Registry
from datamonger._registry import BUNDLED_REGISTRY, validate_registry_selector

_PROJECT_SELECTOR = Path(".datamonger") / "selector.json"
_SELECTOR_FIELDS = {"release", "index_sha256", "index_url"}
_session_registry: Registry | None = None


def _project_selector_path(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / _PROJECT_SELECTOR
        try:
            mode = candidate.stat().st_mode
        except FileNotFoundError:
            continue
        except OSError as error:
            raise RegistryError(
                f"cannot inspect project selector {candidate}: {error}"
            ) from error
        if not stat.S_ISREG(mode):
            raise RegistryError(f"project selector {candidate} must be a file")
        return candidate
    return None


def _read_project_registry(path: Path) -> Registry:
    try:
        raw = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RegistryError(f"project selector {path} contains invalid JSON") from error
    except OSError as error:
        raise RegistryError(f"cannot read project selector {path}: {error}") from error
    if not isinstance(raw, Mapping):
        raise RegistryError(f"project selector {path} must be a JSON object")
    if set(raw) != _SELECTOR_FIELDS:
        raise RegistryError(
            f"project selector {path} must contain exactly "
            "release, index_sha256, and index_url"
        )
    if not all(isinstance(raw[field], str) for field in _SELECTOR_FIELDS):
        raise RegistryError(f"project selector {path} fields must be strings")
    registry = Registry(
        release=cast(str, raw["release"]),
        index_sha256=cast(str, raw["index_sha256"]),
        index_url=cast(str, raw["index_url"]),
    )
    validate_registry_selector(registry)
    return registry


def set_registry(registry: Registry | None) -> None:
    """Set a session selector, or clear it with ``None``."""

    if registry is not None:
        validate_registry_selector(registry)
    global _session_registry
    _session_registry = registry


def active_registry(*, project_dir: Pathish | None = None) -> Registry:
    """Return the session, nearest project, or bundled selector in precedence order."""

    if _session_registry is not None:
        return _session_registry
    start = Path.cwd() if project_dir is None else Path(project_dir)
    selector_path = _project_selector_path(start.resolve())
    if selector_path is not None:
        return _read_project_registry(selector_path)
    return BUNDLED_REGISTRY

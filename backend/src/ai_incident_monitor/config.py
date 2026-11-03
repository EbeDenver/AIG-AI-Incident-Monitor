"""Configuration loader and local environment management.

Governing Charter: Project Constitution (Rules 9, 15: Zero secrets in Git).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_repo_root() -> Path:
    """Resolve repository root path."""
    repo_root_env = os.getenv("REPO_ROOT")
    if repo_root_env:
        return Path(repo_root_env).resolve()
    # config.py -> ai_incident_monitor -> src -> backend -> repo root
    return Path(__file__).resolve().parents[3]


def load_env_file(repo_root: Optional[Path] = None) -> Optional[Path]:
    """Load key-value pairs from .env into os.environ if not already present.

    Searches:
    1. Specified repo_root / .env
    2. Default get_repo_root() / .env
    3. Workspace parent directory / .env
    """
    root = repo_root or get_repo_root()
    candidate_paths = [
        root / ".env",
        root.parent / ".env",
    ]

    for env_path in candidate_paths:
        if env_path.is_file():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            if key and key not in os.environ:
                                os.environ[key] = val
                return env_path
            except Exception as exc:
                logger.warning(f"Failed to read environment file at {env_path}: {exc}")
    return None


# Auto-load on import
load_env_file()

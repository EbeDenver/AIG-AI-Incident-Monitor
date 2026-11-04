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


def load_env_file(repo_root: Optional[Path] = None, *, override: bool = False) -> Optional[Path]:
    """Load key-value pairs from .env into os.environ.

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
                            if key and (override or key not in os.environ):
                                os.environ[key] = val
                return env_path
            except Exception as exc:
                logger.warning(f"Failed to read environment file at {env_path}: {exc}")
    return None


def get_llm_provider() -> str:
    """Resolve configured LLM provider (claude | gemini | mock)."""
    load_env_file()
    provider = os.getenv("AI_MONITOR_LLM_PROVIDER", "").lower().strip()
    if provider:
        return provider
    if os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "mock"


def get_claude_model() -> str:
    """Resolve Anthropic Claude model ID (default: claude-sonnet-4-5-20250929)."""
    load_env_file()
    return os.getenv("ANTHROPIC_MODEL") or os.getenv("AI_MONITOR_CLAUDE_MODEL") or "claude-sonnet-4-5-20250929"


def get_gemini_model() -> str:
    """Resolve Google Gemini model ID (default: gemini-3.1-pro-preview, active Pro model)."""
    load_env_file()
    return os.getenv("GEMINI_MODEL") or os.getenv("AI_MONITOR_GEMINI_MODEL") or "gemini-3.1-pro-preview"


def get_pilot_budget_cap_usd() -> float:
    """Resolve pilot budget ceiling (default: $1.00 USD)."""
    load_env_file()
    raw = os.getenv("AI_MONITOR_MAX_PILOT_BUDGET_USD", "1.00")
    try:
        val = float(raw)
        return max(0.0, val)
    except ValueError:
        return 1.00


def is_production_environment() -> bool:
    """Return True if executing in a production deployment environment."""
    load_env_file()
    env = os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or os.getenv("AI_MONITOR_ENV") or ""
    return env.lower().strip() in ("production", "prod")


def allow_mock_opt_in() -> bool:
    """Check whether synthetic mock data opt-in is permitted.

    Strictly disabled in production to guarantee zero mock data leakage to public consumers.
    """
    if is_production_environment():
        return False
    load_env_file()
    val = os.getenv("AI_MONITOR_ALLOW_MOCK_OPT_IN", "true").lower().strip()
    return val in ("true", "1", "yes")


# Auto-load on import
load_env_file()

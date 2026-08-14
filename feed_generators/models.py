"""Pydantic models for feed configuration and settings."""

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings


class FeedType(StrEnum):
    REQUESTS = "requests"
    SELENIUM = "selenium"


class FeedConfig(BaseModel):
    """Configuration for a single feed generator."""

    script: str
    type: FeedType
    blog_url: str
    enabled: bool = True

    @field_validator("script")
    @classmethod
    def script_must_exist(cls, v: str) -> str:
        script_path = Path(__file__).parent / v
        if not script_path.exists():
            msg = f"Script not found: {v}"
            raise ValueError(msg)
        return v


class GlobalSettings(BaseSettings):
    """Project-wide settings, overridable via RSS_ env vars.

    Example: RSS_REPO_SLUG=oborchers/rss-feeds overrides the default.
    """

    model_config = {"env_prefix": "RSS_"}

    repo_slug: str = "Olshansk/rss-feeds"


def load_feed_registry() -> dict[str, FeedConfig]:
    """Load and validate feeds.yaml.

    Returns:
        Dict mapping feed name to validated FeedConfig.

    Raises:
        FileNotFoundError: If feeds.yaml is missing.
        ValidationError: If any feed config is invalid.
    """
    registry_path = Path(__file__).parent.parent / "feeds.yaml"
    if not registry_path.exists():
        msg = f"Feed registry not found: {registry_path}"
        raise FileNotFoundError(msg)

    with open(registry_path) as f:
        data = yaml.safe_load(f)

    feeds = {}
    for name, config in data.get("feeds", {}).items():
        feeds[name] = FeedConfig(**config)
    return feeds

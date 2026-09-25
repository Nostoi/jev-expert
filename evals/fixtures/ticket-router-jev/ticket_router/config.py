import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    pagerduty_service: str
    auto_reply_enabled: bool
    jev_mode: str  # off | shadow | active


def load_settings() -> Settings:
    return Settings(
        pagerduty_service=os.environ.get("PAGERDUTY_SERVICE", "support-oncall"),
        auto_reply_enabled=os.environ.get("AUTO_REPLY_ENABLED", "true") == "true",
        jev_mode=os.environ.get("JEV_MODE", "shadow"),
    )

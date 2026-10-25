"""Configuration without executing shell startup files."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from pydantic_lab.models import Policy


@dataclass
class Settings:
    database_url: str = "sqlite:///.local-data/control.db"
    state_dir: Path = Path(".local-data")
    redis_url: str | None = None
    image: str = "pydantic-lab-sandbox:local"
    concurrency: int = 4
    idle_seconds: int = 300
    model: str = "deepseek-flash"
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    demo: bool = False
    demo_tool: str = "list_directory"
    compaction_tokens: int = 24000
    request_limit: int = 40
    policy: Policy = field(default_factory=Policy)

    @classmethod
    def load(cls) -> Settings:
        literals: dict[str, str] = {}
        startup = Path.home() / ".zshrc"
        if startup.exists():
            for line in startup.read_text().splitlines():
                match = re.fullmatch(
                    r'\s*(?:export\s+)?(DEEPSEEK_[A-Z_]+)\s*=\s*([\'"])([^\n]*?)\2\s*(?:#.*)?', line
                )
                if match and not any(x in match[3] for x in ("$", "`", "\\")):
                    literals[match[1]] = match[3]

        file_values = dotenv_values(".env", interpolate=False)

        def setting(name: str, default: str) -> str:
            return os.environ.get(name, file_values.get(name) or literals.get(name, default))

        state = Path(os.environ.get("LAB_STATE_DIR", ".local-data")).resolve()
        state.mkdir(parents=True, exist_ok=True)
        return cls(
            database_url=os.environ.get("LAB_DATABASE_URL", f"sqlite:///{state / 'control.db'}"),
            state_dir=state,
            redis_url=os.environ.get("LAB_REDIS_URL"),
            image=os.environ.get("LAB_SANDBOX_IMAGE", "pydantic-lab-sandbox:local"),
            concurrency=int(os.environ.get("LAB_CONCURRENCY", "4")),
            idle_seconds=int(os.environ.get("LAB_IDLE_SECONDS", "300")),
            model=setting("DEEPSEEK_MODEL", "deepseek-flash"),
            base_url=setting(
                "DEEPSEEK_BASE_URL", setting("DEEPSEEK_API_BASE", "https://api.deepseek.com")
            ),
            api_key=setting("DEEPSEEK_API_KEY", ""),
            demo=os.environ.get("LAB_DEMO") == "1",
            demo_tool=os.environ.get("LAB_DEMO_TOOL", "list_directory"),
            compaction_tokens=int(os.environ.get("LAB_COMPACTION_TOKENS", "24000")),
            request_limit=int(os.environ.get("LAB_REQUEST_LIMIT", "40")),
            policy=Policy.model_validate_json(os.environ.get("LAB_POLICY_JSON") or "{}"),
        )

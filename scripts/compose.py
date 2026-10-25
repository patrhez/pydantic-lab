"""Run Compose with literal provider configuration, without sourcing a shell file."""

import os
import subprocess
import sys

from pydantic_lab.config import Settings

settings = Settings.load()
env = os.environ.copy()
for name, value in {
    "DEEPSEEK_API_KEY": settings.api_key,
    "DEEPSEEK_BASE_URL": settings.base_url,
    "DEEPSEEK_MODEL": settings.model,
}.items():
    env.setdefault(name, value)
raise SystemExit(subprocess.call(["docker", "compose", *sys.argv[1:]], env=env))

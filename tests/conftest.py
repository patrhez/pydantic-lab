import os

import pytest

from pydantic_lab.config import Settings
from pydantic_lab.models import Session
from pydantic_lab.storage.control import ControlStore

os.environ["PYDANTIC_AI_NO_BANNER"] = "1"


@pytest.fixture
def store(tmp_path):
    return ControlStore(f"sqlite:///{tmp_path / 'control.db'}")


@pytest.fixture
def local(store, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    session = Session(title="Test", mode="local", repository=str(workspace), initialized=True)
    session.sandbox.image = os.environ.get("LAB_TEST_IMAGE", "pydantic-lab-sandbox:local")
    return store.create(session)


@pytest.fixture
def settings(tmp_path):
    return Settings(state_dir=tmp_path, demo=True, idle_seconds=30)

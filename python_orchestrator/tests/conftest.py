"""Shared test fixtures for WebCMD."""
import asyncio
import tempfile
from pathlib import Path

import pytest

from webcmd.config import WebCMDConfig


@pytest.fixture
def tmp_home(tmp_path: Path) -> Path:
    """Create a temporary WebCMD home directory."""
    home = tmp_path / ".webcmd"
    home.mkdir()
    return home


@pytest.fixture
def config(tmp_home: Path) -> WebCMDConfig:
    """Create a test configuration with temp directories."""
    cfg = WebCMDConfig(home_dir=tmp_home)
    cfg.ensure_dirs()
    return cfg

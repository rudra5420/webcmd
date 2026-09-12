"""WebCMD global configuration."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class WebCMDConfig(BaseModel):
    """Global WebCMD configuration."""
    
    # Paths
    data_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("WEBCMD_DATA_DIR", Path.cwd() / "data"))
    )
    home_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("WEBCMD_HOME", Path.home() / ".webcmd"))
    )
    
    # Database
    db_path: Path | None = None  # Defaults to data_dir / "webcmd.db"
    
    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None  # For Ollama: http://localhost:11434/v1
    
    # Workers
    browser_headless: bool = Field(
        default_factory=lambda: os.environ.get("WEBCMD_HEADLESS", "false").lower() in ("true", "1", "yes")
    )
    browser_timeout_ms: int = 30000
    shell_command_timeout_s: int = 60
    
    # Recovery
    max_recovery_attempts: int = 3
    max_recovery_depth: int = 2
    max_execution_time_s: int = 600
    
    # Memory
    memory_confidence_threshold: float = 0.6
    memory_freshness_half_life_days: int = 14
    
    # Checkpoints
    checkpoint_periodic_interval_s: int = 30
    
    def model_post_init(self, __context: Any) -> None:
        if "data_dir" not in self.model_fields_set and "home_dir" in self.model_fields_set:
            self.data_dir = self.home_dir

    def get_db_path(self) -> Path:
        return self.db_path or self.data_dir / "webcmd.db"
    
    def get_browser_profile_dir(self) -> Path:
        return self.data_dir / "browser-profile"
    
    def get_downloads_dir(self) -> Path:
        return self.data_dir / "downloads"
    
    def get_screenshots_dir(self) -> Path:
        return self.data_dir / "screenshots"
    
    def get_artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"
    
    def get_checkpoints_dir(self) -> Path:
        return self.data_dir / "checkpoints"
    
    def get_logs_dir(self) -> Path:
        return self.data_dir / "logs"
    
    def get_skills_dir(self) -> Path:
        return self.data_dir / "skills"
    
    def get_runs_dir(self) -> Path:
        return self.data_dir / "runs"
    
    def get_audit_log_path(self) -> Path:
        return self.get_logs_dir() / "audit.log"
    
    def ensure_dirs(self) -> None:
        """Create all required directories."""
        dirs = [
            self.data_dir,
            self.get_browser_profile_dir(),
            self.get_downloads_dir(),
            self.get_screenshots_dir(),
            self.get_artifacts_dir(),
            self.get_checkpoints_dir(),
            self.get_logs_dir(),
            self.get_skills_dir(),
            self.get_runs_dir(),
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


def get_config() -> WebCMDConfig:
    """Get the global WebCMD configuration."""
    cfg = WebCMDConfig()
    cfg.ensure_dirs()
    return cfg

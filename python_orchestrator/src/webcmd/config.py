"""WebCMD global configuration."""
from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field


class WebCMDConfig(BaseModel):
    """Global WebCMD configuration."""
    
    # Paths
    home_dir: Path = Field(
        default_factory=lambda: Path(os.environ.get("WEBCMD_HOME", Path.home() / ".webcmd"))
    )
    
    # Database
    db_path: Path | None = None  # Defaults to home_dir / "state.db"
    
    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None  # For Ollama: http://localhost:11434/v1
    
    # Workers
    browser_headless: bool = True
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
    
    def get_db_path(self) -> Path:
        return self.db_path or self.home_dir / "state.db"
    
    def get_artifacts_dir(self) -> Path:
        return self.home_dir / "artifacts"
    
    def get_skills_dir(self) -> Path:
        return self.home_dir / "skills"
    
    def get_runs_dir(self) -> Path:
        return self.home_dir / "runs"
    
    def get_audit_log_path(self) -> Path:
        return self.home_dir / "audit.log"
    
    def ensure_dirs(self) -> None:
        """Create all required directories."""
        for d in [self.home_dir, self.get_artifacts_dir(), self.get_skills_dir(), self.get_runs_dir()]:
            d.mkdir(parents=True, exist_ok=True)


def get_config() -> WebCMDConfig:
    """Get the global WebCMD configuration."""
    return WebCMDConfig()

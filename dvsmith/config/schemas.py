"""Pydantic schemas for configuration validation."""

from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class SimulatorConfig(BaseModel):
    """Configuration for a specific simulator."""
    
    work_dir: str = Field(description="Working directory for simulator")
    compile_cmd: str = Field(description="Command to compile the design")
    run_cmd: str = Field(description="Command to run simulation")
    
    
class CoverageConfig(BaseModel):
    """Coverage configuration."""
    
    db_path: Optional[str] = Field(None, description="Path to coverage database")
    merge_cmd: Optional[str] = Field(None, description="Command to merge coverage")
    report_cmd: Optional[str] = Field(None, description="Command to generate reports")


class ThresholdsConfig(BaseModel):
    """Grading thresholds configuration."""
    
    functional: Dict[str, object] = Field(default_factory=dict)
    code: Dict[str, object] = Field(default_factory=dict)
    health: Dict[str, object] = Field(default_factory=dict)


class GradingConfig(BaseModel):
    """Grading configuration."""
    
    smoke_tests: List[str] = Field(default_factory=list, description="List of smoke test names")
    weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "functional_coverage": 0.6,
            "code_coverage": 0.3,
            "health": 0.1
        },
        description="Grading weights"
    )
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    
    @field_validator('weights')
    @classmethod
    def validate_weights(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Validate that weights sum to ~1.0."""
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v


class PathsConfig(BaseModel):
    """Repository paths configuration."""
    
    root: str = Field(default=".", description="Repository root path")
    tests: str = Field(description="Path to tests directory")
    sequences: Optional[str] = Field(None, description="Path to sequences directory")
    env: Optional[str] = Field(None, description="Path to environment directory")


class ProfileMetadata(BaseModel):
    """Profile metadata section."""
    
    test_count: int = Field(default=0)
    sequence_count: int = Field(default=0)
    covergroup_count: int = Field(default=0)
    build_system: str = Field(default="makefile")
    covergroups: List[str] = Field(default_factory=list)


class Profile(BaseModel):
    """Complete profile configuration with validation."""
    
    name: str = Field(description="Profile/gym name")
    repo_url: str = Field(description="Repository URL or local path")
    description: str = Field(default="", description="Profile description")
    simulators: List[str] = Field(description="List of supported simulators")
    paths: PathsConfig = Field(description="Repository paths")
    build: Dict[str, SimulatorConfig] = Field(
        default_factory=dict,
        description="Build configuration per simulator"
    )
    coverage: CoverageConfig = Field(
        default_factory=CoverageConfig,
        description="Coverage configuration"
    )
    grading: GradingConfig = Field(
        default_factory=GradingConfig,
        description="Grading configuration"
    )
    metadata: ProfileMetadata = Field(
        default_factory=ProfileMetadata,
        description="Profile metadata"
    )
    
    # Analysis cache (saved to YAML for build command)
    analysis_cache: Optional[dict] = Field(None, description="Cached analysis results")
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Profile":
        """Load and validate profile from YAML file.
        
        Args:
            path: Path to YAML profile file
            
        Returns:
            Validated Profile instance
            
        Raises:
            ValidationError: If profile is invalid
            FileNotFoundError: If file doesn't exist
        """
        if not path.exists():
            raise FileNotFoundError(f"Profile not found: {path}")
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return cls.model_validate(data)
    
    def to_yaml(self, path: Path) -> None:
        """Save profile to YAML file.
        
        Args:
            path: Path to save YAML file
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict - include analysis cache for build command
        data = self.model_dump(exclude_none=True, by_alias=False)
        
        with open(path, "w") as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary (for backwards compatibility)."""
        return self.model_dump(exclude={"_analysis_cache"}, exclude_none=True)

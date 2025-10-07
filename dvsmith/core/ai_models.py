"""Pydantic models for structured AI responses."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, RootModel, ConfigDict


class FilesEnvelope(BaseModel):
    """Stable wrapper for a list of file paths."""
    model_config = ConfigDict(extra="ignore")  # Tolerate stray keys if model adds them
    kind: Literal["dvsmith.files.v1"] = "dvsmith.files.v1"
    files: list[str] = Field(default_factory=list, description="List of .sv file paths")


class DirectoryInfo(BaseModel):
    """Directory identification response."""
    tests_dir: Optional[str] = Field(
        None,
        description="Path to directory containing UVM test classes"
    )
    sequences_dir: Optional[str] = Field(
        None,
        description="Path to directory containing UVM sequences"
    )
    env_dir: Optional[str] = Field(
        None,
        description="Path to directory containing UVM environment"
    )
    agents_dir: Optional[str] = Field(
        None,
        description="Path to directory containing UVM agents"
    )


class TestFileList(RootModel[list[str]]):
    """List of test files as a root model (returns bare list)."""
    root: list[str]


class TestInfo(BaseModel):
    """UVM test class information."""
    is_test: bool = Field(
        description="True if this file contains a UVM test class, False otherwise"
    )
    class_name: Optional[str] = Field(
        None,
        description="Name of the UVM test class (null if not a test)"
    )
    base_class: Optional[str] = Field(
        None,
        description="Name of the base class this test extends (null if not a test)"
    )
    description: Optional[str] = Field(
        None,
        description="Brief one-sentence description of what this test does"
    )


class BuildInfo(BaseModel):
    """Build system and simulator detection."""
    build_system: str = Field(
        description="Type of build system: makefile, cmake, fusesoc, dvsim, or custom"
    )
    simulators: list[str] = Field(
        default_factory=list,
        description="List of detected simulators: questa, modelsim, xcelium, irun, vcs, verilator, dsim"
    )


# Task generator response models

class TaskName(BaseModel):
    """Task name generation."""
    name: str = Field(
        description="Human-readable task name (2-5 words)"
    )


class TaskDifficulty(BaseModel):
    """Task difficulty assessment."""
    difficulty: str = Field(
        description="Difficulty level: EASY, MEDIUM, or HARD"
    )


class TaskDescription(BaseModel):
    """Task description."""
    description: str = Field(
        description="Clear, detailed task description (2-4 sentences) explaining what needs to be verified"
    )


class TaskGoal(BaseModel):
    """Task goal statement."""
    goal: str = Field(
        description="Concise goal statement (1-2 sentences) telling what needs to be accomplished"
    )


class TaskHints(BaseModel):
    """Task hints."""
    hints: list[str] = Field(
        default_factory=list,
        description="List of 3-5 helpful hints that guide without giving away the solution"
    )


class CovergroupSelection(BaseModel):
    """Covergroup selection for a test."""
    covergroups: list[str] = Field(
        default_factory=list,
        description="List of 2-4 relevant covergroup names from the available list"
    )


class CompleteTaskMetadata(BaseModel):
    """Complete task metadata generated in a single AI call."""
    task_name: str = Field(
        description="Human-readable task name (2-5 words, clear and professional)"
    )
    difficulty: str = Field(
        description="Difficulty level: EASY, MEDIUM, or HARD"
    )
    description: str = Field(
        description="Clear, detailed task description (2-4 sentences) explaining what needs to be verified"
    )
    goal: str = Field(
        description="Concise goal statement (1-2 sentences) telling what needs to be accomplished"
    )
    hints: list[str] = Field(
        default_factory=list,
        description="List of 3-5 helpful hints that guide without giving away the solution"
    )
    covergroups: list[str] = Field(
        default_factory=list,
        description="List of 2-4 relevant covergroup names from the available list for this test"
    )

"""Simulator adapters."""

# Import all adapters to trigger registration
from .questa import QuestaAdapter
from .xcelium import XceliumAdapter

__all__ = ["QuestaAdapter", "XceliumAdapter"]

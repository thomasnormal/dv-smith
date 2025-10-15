"""CVDP data models."""

from dataclasses import dataclass, asdict
from typing import Dict, List
import json


@dataclass
class CvdpItem:
    """A single CVDP task item."""
    
    id: str
    categories: List[str]            # e.g. ["cid005","medium"]
    system_message: str
    prompt: str
    context: Dict[str, str]          # rel paths under /code -> file text
    patch: Dict[str, str]            # usually {}
    harness: Dict[str, str]          # docker-compose.yml, scripts, .env, etc.

    def to_json(self) -> str:
        """Convert to JSON string for JSONL output."""
        return json.dumps(asdict(self), ensure_ascii=False)

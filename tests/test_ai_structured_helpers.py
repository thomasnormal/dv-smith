"""Tests for helper utilities in dvsmith.core.ai_structured."""

from pathlib import Path

import json
import pytest

from dvsmith.core.ai_structured import _extract_payload


def test_extract_payload_inline_normalizes_enums(tmp_path: Path) -> None:
    payload = {
        "build_system": "MAKEFILE",
        "detected_simulators": ["QUESTA", "VCS"],
        "coverage_components": [
            {
                "name": "comp",
                "file_path": "foo",
                "base_class": "base",
                "covergroups": [],
            }
        ],
    }

    result = _extract_payload({"payload_object": payload}, tmp_path)

    assert result["build_system"] == "makefile"
    assert result["detected_simulators"] == ["questa", "vcs"]


def test_extract_payload_from_path(tmp_path: Path) -> None:
    data = {
        "build_system": "FUSESOC",
        "detected_simulators": ["XCELIUM"],
    }
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(json.dumps(data))

    result = _extract_payload({"payload_path": str(payload_path)}, tmp_path)

    assert result["build_system"] == "fusesoc"
    assert result["detected_simulators"] == ["xcelium"]


@pytest.mark.parametrize(
    "tool_input",
    [
        {"payload_path": "foo", "payload_object": {}},
        {},
        {"payload_object": None},
    ],
)
def test_extract_payload_invalid_inputs(tool_input: dict, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _extract_payload(tool_input, tmp_path)

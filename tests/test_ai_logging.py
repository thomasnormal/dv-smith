"""Test AI logging functionality."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from dvsmith.core.ai_structured import log_ai_call


class TestLogAICall:
    """Test the log_ai_call function."""

    def test_log_ai_call_basic(self, tmp_path: Path) -> None:
        """Test basic log entry creation."""
        log_file = tmp_path / "ai_calls.jsonl"

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="Test prompt",
                response_model_name="TestModel",
                schema={"type": "object", "properties": {}},
                response={"result": "success"},
                duration_ms=123.45,
            )

        # Verify log file was created
        assert log_file.exists()

        # Parse and verify log entry
        with log_file.open() as f:
            line = f.readline()
            entry = json.loads(line)

        assert entry["prompt"] == "Test prompt"
        assert entry["response_model"] == "TestModel"
        assert entry["schema"]["type"] == "object"
        assert entry["response"] == {"result": "success"}
        assert entry["duration_ms"] == 123.45
        assert entry["error"] is None
        assert "timestamp" in entry
        assert "messages" in entry
        assert entry["messages"] == []

    def test_log_ai_call_with_messages(self, tmp_path: Path) -> None:
        """Test log entry with agent messages."""
        log_file = tmp_path / "ai_calls.jsonl"

        messages = [
            {"type": "text", "text": "Analyzing the problem..."},
            {"type": "tool_use", "tool_name": "Read", "input": {"file": "test.py"}},
            {"type": "tool_result", "content": "File contents here"},
        ]

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="Test prompt",
                response_model_name="TestModel",
                schema={},
                response={"result": "success"},
                duration_ms=100.0,
                messages=messages,
            )

        with log_file.open() as f:
            entry = json.loads(f.readline())

        assert len(entry["messages"]) == 3
        assert entry["messages"][0]["type"] == "text"
        assert entry["messages"][0]["text"] == "Analyzing the problem..."
        assert entry["messages"][1]["type"] == "tool_use"
        assert entry["messages"][1]["tool_name"] == "Read"
        assert entry["messages"][2]["type"] == "tool_result"

    def test_log_ai_call_with_error(self, tmp_path: Path) -> None:
        """Test log entry with error."""
        log_file = tmp_path / "ai_calls.jsonl"

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="Test prompt",
                response_model_name="TestModel",
                schema={},
                error="Something went wrong",
                duration_ms=50.0,
            )

        with log_file.open() as f:
            entry = json.loads(f.readline())

        assert entry["error"] == "Something went wrong"
        assert entry["response"] is None

    def test_log_ai_call_creates_directory(self, tmp_path: Path) -> None:
        """Test that log_ai_call creates parent directory if needed."""
        log_file = tmp_path / "nested" / "dir" / "ai_calls.jsonl"

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="Test",
                response_model_name="Model",
                schema={},
            )

        assert log_file.exists()
        assert log_file.parent.exists()

    def test_log_ai_call_appends_entries(self, tmp_path: Path) -> None:
        """Test that multiple calls append to the log file."""
        log_file = tmp_path / "ai_calls.jsonl"

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="First prompt",
                response_model_name="Model1",
                schema={},
                response={"result": "first"},
            )
            log_ai_call(
                prompt="Second prompt",
                response_model_name="Model2",
                schema={},
                response={"result": "second"},
            )

        # Verify both entries are in the file
        with log_file.open() as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 2
        assert entries[0]["prompt"] == "First prompt"
        assert entries[0]["response"] == {"result": "first"}
        assert entries[1]["prompt"] == "Second prompt"
        assert entries[1]["response"] == {"result": "second"}

    def test_log_ai_call_valid_jsonl(self, tmp_path: Path) -> None:
        """Test that log file is valid JSONL format."""
        log_file = tmp_path / "ai_calls.jsonl"

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            # Write multiple entries
            for i in range(5):
                log_ai_call(
                    prompt=f"Prompt {i}",
                    response_model_name=f"Model{i}",
                    schema={"id": i},
                    response={"count": i},
                )

        # Verify each line is valid JSON
        with log_file.open() as f:
            for i, line in enumerate(f):
                entry = json.loads(line)  # Should not raise
                assert entry["prompt"] == f"Prompt {i}"
                assert entry["schema"]["id"] == i

    def test_log_ai_call_timestamp_format(self, tmp_path: Path) -> None:
        """Test that timestamp is in ISO format."""
        log_file = tmp_path / "ai_calls.jsonl"

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="Test",
                response_model_name="Model",
                schema={},
            )

        with log_file.open() as f:
            entry = json.loads(f.readline())

        # Verify timestamp can be parsed
        timestamp = entry["timestamp"]
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)

    def test_log_ai_call_handles_none_messages(self, tmp_path: Path) -> None:
        """Test that None messages parameter defaults to empty list."""
        log_file = tmp_path / "ai_calls.jsonl"

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="Test",
                response_model_name="Model",
                schema={},
                messages=None,
            )

        with log_file.open() as f:
            entry = json.loads(f.readline())

        assert entry["messages"] == []

    def test_log_ai_call_doesnt_crash_on_write_error(
        self, tmp_path: Path, caplog
    ) -> None:
        """Test that log_ai_call doesn't crash if writing fails."""
        import logging
        
        # Set caplog to capture WARNING level from the dvsmith logger
        caplog.set_level(logging.WARNING, logger="dvsmith")
        
        # Use an invalid path (file instead of directory)
        log_file = tmp_path / "file.txt"
        log_file.write_text("existing file")
        invalid_log = log_file / "ai_calls.jsonl"  # Can't create file under a file

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", invalid_log):
            # Should not raise an exception
            log_ai_call(
                prompt="Test",
                response_model_name="Model",
                schema={},
            )

        # Check that a warning was logged
        assert "Failed to log AI call" in caplog.text

    def test_log_ai_call_large_messages(self, tmp_path: Path) -> None:
        """Test log entry with large message content."""
        log_file = tmp_path / "ai_calls.jsonl"

        # Create a large message
        large_text = "x" * 10000
        messages = [
            {"type": "text", "text": large_text},
        ]

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="Test",
                response_model_name="Model",
                schema={},
                messages=messages,
            )

        with log_file.open() as f:
            entry = json.loads(f.readline())

        assert len(entry["messages"][0]["text"]) == 10000

    def test_log_ai_call_complex_schema(self, tmp_path: Path) -> None:
        """Test log entry with complex nested schema."""
        log_file = tmp_path / "ai_calls.jsonl"

        complex_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "nested": {
                    "type": "object",
                    "properties": {
                        "field1": {"type": "boolean"},
                        "field2": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "required": ["name", "age"],
        }

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt="Test",
                response_model_name="ComplexModel",
                schema=complex_schema,
            )

        with log_file.open() as f:
            entry = json.loads(f.readline())

        # Verify schema was preserved correctly
        assert entry["schema"]["properties"]["nested"]["properties"]["field2"]["type"] == "array"
        assert entry["schema"]["required"] == ["name", "age"]

    def test_log_ai_call_special_characters(self, tmp_path: Path) -> None:
        """Test log entry with special characters in strings."""
        log_file = tmp_path / "ai_calls.jsonl"

        special_prompt = 'Test with "quotes" and\nnewlines\tand\ttabs'

        with patch("dvsmith.core.ai_structured.AI_LOG_FILE", log_file):
            log_ai_call(
                prompt=special_prompt,
                response_model_name="Model",
                schema={},
                messages=[{"type": "text", "text": "Line 1\nLine 2\nLine 3"}],
            )

        with log_file.open() as f:
            entry = json.loads(f.readline())

        # Verify special characters were preserved
        assert entry["prompt"] == special_prompt
        assert "\n" in entry["messages"][0]["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

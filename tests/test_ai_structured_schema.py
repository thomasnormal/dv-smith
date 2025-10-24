"""Tests for AI structured schema generation."""

import jsonschema

from typing import List

from dvsmith.core.ai_structured import _make_adapter
from dvsmith.core.models import RepoAnalysis


def test_repo_analysis_schema_is_trimmed_and_valid_jsonschema():
    """Schema sent to the agent should be flat and valid JSON schema."""
    schema, _validate, _name = _make_adapter(RepoAnalysis)

    # 1) No $defs or $ref should remain (flattened schema).
    assert "$defs" not in schema

    def contains_ref(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return True
            return any(contains_ref(v) for v in node.values())
        if isinstance(node, list):
            return any(contains_ref(item) for item in node)
        return False

    assert not contains_ref(schema)

    # 2) Validate schema structure using Draft2020-12 meta-schema.
    jsonschema.Draft202012Validator.check_schema(schema)


def test_make_adapter_supports_list_response_model():
    schema, validate, name = _make_adapter(List[int])

    assert schema["type"] == "array"
    assert schema["items"]["type"] == "integer"
    assert name  # non-empty descriptive name

    assert validate([1, 2, 3]) == [1, 2, 3]


def test_make_adapter_supports_primitive_response_model():
    schema, validate, name = _make_adapter(str)

    assert schema["type"] == "string"
    assert name  # non-empty descriptive name
    assert validate("hello") == "hello"

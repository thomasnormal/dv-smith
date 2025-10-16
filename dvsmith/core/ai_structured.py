"""Structured AI responses using Claude Agent SDK with Pydantic models."""

import json
import logging
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, Tuple

from pydantic import BaseModel, TypeAdapter

from filelock import FileLock
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookContext,
    HookMatcher,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk.types import (
    AssistantMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)

# Configure logging and enable Anthropic SDK debug logging if needed
from ..config import get_logger

logger = get_logger(__name__)

if os.getenv("DVSMITH_DEBUG", "").lower() in ("1", "true", "yes"):
    # Enable Anthropic SDK debug logging
    logging.getLogger("anthropic").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)

# AI call log file path
AI_LOG_FILE = Path.home() / ".dvsmith" / "ai_calls.jsonl"


@contextmanager
def temporarily_override_claude_config(config: dict[str, Any]) -> Iterator[None]:
    """Temporarily replace ~/.claude.json with the provided config."""
    claude_path = Path.home() / ".claude.json"
    backup_path = Path.home() / ".claude.json.dvsmith_backup"
    try:
        if claude_path.exists():
            shutil.move(str(claude_path), str(backup_path))
        claude_path.write_text(json.dumps(config))
        yield
    finally:
        try:
            if claude_path.exists():
                claude_path.unlink()
            if backup_path.exists():
                shutil.move(str(backup_path), str(claude_path))
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logger.warning("Failed to restore Claude config: %s", exc)


def log_ai_call(
    prompt: str,
    response_model_name: str,
    schema: dict,
    response: Optional[dict] = None,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
    messages: Optional[list] = None,
) -> None:
    """Log an AI call to the log file.

    Args:
        prompt: The user prompt
        response_model_name: Name of the response model
        schema: JSON schema of the response model
        response: The response data (if successful)
        error: Error message (if failed)
        duration_ms: Call duration in milliseconds
        messages: List of agent messages (conversation transcript)
    """
    try:
        AI_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "response_model": response_model_name,
            "schema": schema,
            "response": response,
            "error": error,
            "duration_ms": duration_ms,
            "messages": messages or [],
        }

        # Use file lock to prevent concurrent writes
        lock_file = AI_LOG_FILE.with_suffix(".lock")
        with FileLock(lock_file, timeout=10):
            with AI_LOG_FILE.open("a") as f:
                f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        # Don't fail if logging fails
        logger.warning(f"Failed to log AI call: {e}")


def _make_adapter(model: Any) -> Tuple[dict[str, Any], Callable[[Any], Any], str]:
    """Create schema, validator, and name for BaseModel or dataclass/typing types.
    
    Args:
        model: Pydantic BaseModel class, dataclass, or typing type
        
    Returns:
        Tuple of (schema dict, validation function, model name)
    """
    if isinstance(model, type) and issubclass(model, BaseModel):
        schema: dict[str, Any] = model.model_json_schema()

        def validate(data: Any) -> Any:
            return model.model_validate(data)

        model_name = model.__name__
    else:
        # Use TypeAdapter for dataclasses and other types
        ta = TypeAdapter(model)
        schema = ta.json_schema()

        def validate(data: Any) -> Any:
            return ta.validate_python(data)

        model_name = getattr(model, "__name__", str(model))
    return schema, validate, model_name


def _tool_status_line(tool_name: str, tool_input: dict[str, Any] | None) -> Optional[str]:
    """Generate a short status message for tool usage."""
    if not tool_input:
        return tool_name

    if tool_name == "Read":
        if path_str := tool_input.get("path"):
            return f"{tool_name}: {Path(path_str).name}"
        else:
            return f"{tool_name}: {str(tool_input)}"
    elif tool_name == "Bash":
        cmd = (
            tool_input.get("cmd")
            or tool_input.get("command")
            or tool_input.get("bash_command")
        )
        if not cmd and tool_input:
            first_val = next(iter(tool_input.values()), "")
            if isinstance(first_val, str) and len(first_val) < 200:
                cmd = first_val
        if cmd:
            trimmed = cmd.replace("\n", "\\n")
            suffix = "..." if len(trimmed) > 40 else ""
            return f"{tool_name}: {trimmed[:40]}{suffix}"
    elif tool_name in {"Glob", "Grep"}:
        pattern = (
            tool_input.get("filePattern")
            or tool_input.get("pattern")
            or tool_input.get("patternText")
        )
        if pattern:
            suffix = "..." if len(pattern) > 30 else ""
            return f"{tool_name}: {pattern[:30]}{suffix}"

    return tool_name


def _load_payload_from_path(path_value: str, base_dir: Path) -> Any:
    """Read JSON payload from a file path, resolving relative to base_dir."""
    target_path = Path(path_value).expanduser()
    if not target_path.is_absolute():
        target_path = (base_dir / target_path).resolve()
    else:
        target_path = target_path.resolve()

    if not target_path.exists():
        raise FileNotFoundError(f"Payload path not found: {target_path}")

    try:
        with target_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Payload file {target_path} does not contain valid JSON") from exc


def _handle_assistant_message(
    message: AssistantMessage,
    agent_messages: list[dict[str, Any]],
    status_cb: Optional[Callable[[str], None]],
) -> None:
    """Store assistant message blocks and fire status callbacks."""
    for block in message.content:
        if isinstance(block, TextBlock):
            agent_messages.append({"type": "text", "text": block.text})
            if status_cb:
                status_cb(block.text[:80].strip())
        elif isinstance(block, ThinkingBlock):
            agent_messages.append(
                {
                    "type": "thinking",
                    "thinking": block.thinking,
                    "signature": block.signature,
                }
            )
            if status_cb:
                status_cb("thinking...")
        elif isinstance(block, ToolUseBlock):
            agent_messages.append(
                {
                    "type": "tool_use",
                    "tool_id": block.id,
                    "tool_name": block.name,
                    "input": block.input,
                }
            )
            if status_cb:
                status_text = _tool_status_line(block.name, block.input)
                if status_text:
                    status_cb(status_text)
        elif isinstance(block, ToolResultBlock):
            content_str = str(block.content) if block.content is not None else ""
            agent_messages.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.tool_use_id,
                    "content": content_str,
                    "is_error": block.is_error,
                }
            )
            if status_cb:
                status_cb("tool result")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True,
)
async def query_with_pydantic_response(
    prompt: str,
    response_model: type,
    system_prompt: str = "",
    cwd: str = ".",
    status_cb: Optional[Callable[[str], None]] = None,
    postprocess: Optional[Callable[[Any], Any]] = None,
) -> Any:
    """
    Query Claude and get a structured response (Pydantic model or dataclass).

    Claude can use all reasoning but must return a final answer using
    the FinalAnswer tool with data matching the response_model schema.

    Args:
        prompt: The user prompt
        response_model: Pydantic BaseModel class, dataclass, or typing type
        system_prompt: Additional system prompt context
        cwd: Working directory
        status_cb: Optional callback for live status updates
        postprocess: Optional function to post-process validated result

    Returns:
        Validated instance of response_model (after optional postprocess)
    """
    schema, validate_payload, response_model_name = _make_adapter(response_model)
    model_properties = dict(schema.get("properties", {}))
    required_fields = list(schema.get("required", []))
    tool_schema = {
        "oneOf": [
            {
                "type": "object",
                "properties": model_properties,
                "required": required_fields,
            },
            {
                "type": "object",
                "properties": {
                    "payload_path": {
                        "type": "string",
                        "description": (
                            "Absolute or relative path to a JSON file that contains the "
                            "final response payload."
                        ),
                    }
                },
                "required": ["payload_path"],
                "additionalProperties": False,
            },
        ]
    }

    base_dir = Path(cwd or ".").expanduser().resolve()
    final_obj: Optional[Any] = None
    start_time = time.time()
    agent_messages: list[dict[str, Any]] = []

    if not hasattr(log_ai_call, "_printed_location"):
        logger.info("Logging AI calls to: %s", AI_LOG_FILE)
        log_ai_call._printed_location = True  # type: ignore[attr-defined]

    @tool(
        "FinalAnswer",
        "Return the final answer as JSON that matches the required schema. "
        "Pass the fields directly as tool parameters, not wrapped in any container.",
        tool_schema,
    )
    async def final_answer(_: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": "received"}]}

    async def capture_final(
        input_data: dict[str, Any],
        _tool_use_id: str | None,
        _ctx: HookContext,
    ) -> dict[str, Any]:
        nonlocal final_obj
        if input_data.get("tool_name") == "mcp__answer__FinalAnswer":
            tool_input = input_data.get("tool_input", {})
            if "payload_path" in tool_input:
                extra_keys = [key for key in tool_input.keys() if key != "payload_path"]
                if extra_keys:
                    raise ValueError(
                        "FinalAnswer must provide either payload_path or direct fields, not both."
                    )
                payload_data = _load_payload_from_path(tool_input["payload_path"], base_dir)
            else:
                payload_data = tool_input
            final_obj = validate_payload(payload_data)
        return {}

    async def enforce_final_before_stop(
        input_data: dict[str, Any],
        _tool_use_id: str | None,
        _ctx: HookContext,
    ) -> dict[str, Any]:
        if final_obj is None:
            return {
                "decision": "block",
                "reason": (
                    "Before stopping, call the tool `FinalAnswer` exactly once with the "
                    "final JSON object that matches the provided schema."
                ),
            }
        return {}

    answer_server = create_sdk_mcp_server(name="answer", tools=[final_answer])
    full_system_prompt = system_prompt + (
        "\n\nWhen you are done with your analysis, call the `FinalAnswer` tool exactly once with "
        "the final JSON payload that matches the provided schema. You may either pass the fields "
        "directly, or provide `payload_path` pointing to a JSON file that contains the full payload."
    )
    options = ClaudeAgentOptions(
        system_prompt=full_system_prompt,
        mcp_servers={"answer": answer_server},
        permission_mode="bypassPermissions",
        cwd=cwd,
        hooks={
            "PostToolUse": [
                HookMatcher(matcher="mcp__answer__FinalAnswer", hooks=[capture_final])
            ],
            "Stop": [HookMatcher(hooks=[enforce_final_before_stop])],
        },
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            logger.debug("Received message type: %s", type(message).__name__)
            if hasattr(message, "__dict__"):
                logger.debug("Message attributes: %s", message.__dict__)

            if isinstance(message, AssistantMessage):
                _handle_assistant_message(message, agent_messages, status_cb)
            else:
                agent_messages.append(
                    {"type": type(message).__name__, "raw": str(message)}
                )

            if final_obj is not None:
                break

    duration_ms = (time.time() - start_time) * 1000
    if final_obj is None:
        error_msg = "Claude finished without calling FinalAnswer"
        log_ai_call(
            prompt=prompt,
            response_model_name=response_model_name,
            schema=schema,
            error=error_msg,
            duration_ms=duration_ms,
            messages=agent_messages,
        )
        raise RuntimeError(
            "Claude finished without calling FinalAnswer. "
            "Check that the prompt is clear about calling FinalAnswer."
        )

    result_obj = postprocess(final_obj) if postprocess else final_obj
    response_payload = (
        result_obj.model_dump() if hasattr(result_obj, "model_dump") else result_obj
    )
    log_ai_call(
        prompt=prompt,
        response_model_name=response_model_name,
        schema=schema,
        response=response_payload,
        duration_ms=duration_ms,
        messages=agent_messages,
    )

    return result_obj

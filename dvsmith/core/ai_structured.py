"""Structured AI responses using Claude Agent SDK with Pydantic models."""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Type, TypeVar, Optional, Any, Callable
from pydantic import BaseModel, TypeAdapter

from filelock import FileLock
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
    HookMatcher,
    HookContext,
)
from claude_agent_sdk.types import (
    AssistantMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
)

# Configure logging and enable Anthropic SDK debug logging if needed
from ..config import get_logger

logger = get_logger(__name__)

if os.getenv("DVSMITH_DEBUG", "").lower() in ("1", "true", "yes"):
    # Enable Anthropic SDK debug logging
    logging.getLogger("anthropic").setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)

ModelT = TypeVar("ModelT", bound=BaseModel)

# AI call log file path
AI_LOG_FILE = Path.home() / ".dvsmith" / "ai_calls.jsonl"


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


def _make_adapter(model: type):
    """Create schema, validator, and name for BaseModel or dataclass/typing types.
    
    Args:
        model: Pydantic BaseModel class, dataclass, or typing type
        
    Returns:
        Tuple of (schema dict, validation function, model name)
    """
    if isinstance(model, type) and issubclass(model, BaseModel):
        schema = model.model_json_schema()
        validate = lambda data: model.model_validate(data)
        model_name = model.__name__
    else:
        # Use TypeAdapter for dataclasses and other types
        ta = TypeAdapter(model)
        schema = ta.json_schema()
        validate = lambda data: ta.validate_python(data)
        model_name = getattr(model, "__name__", str(model))
    return schema, validate, model_name


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
    # Build JSON Schema and validator for BaseModel or dataclass
    schema, validate_payload, response_model_name = _make_adapter(response_model)

    # Extract only the properties and required fields for the tool schema
    # The tool parameters should match the model's fields directly
    tool_schema = {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }

    final_obj: Optional[Any] = None
    start_time = time.time()
    agent_messages = []  # Accumulate all agent messages

    # Log location on first call
    if not hasattr(log_ai_call, "_printed_location"):
        logger.info(f"Logging AI calls to: {AI_LOG_FILE}")
        log_ai_call._printed_location = True

    # Define the FinalAnswer tool
    @tool(
        "FinalAnswer",
        "Return the final answer as JSON that matches the required schema. "
        "Pass the fields directly as tool parameters, not wrapped in any container.",
        tool_schema,
    )
    async def final_answer(args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": "received"}]}

    # Capture the FinalAnswer tool payload
    async def capture_final(
        input_data: dict[str, Any],
        tool_use_id: str | None,
        ctx: HookContext,
    ) -> dict[str, Any]:
        nonlocal final_obj
        if input_data.get("tool_name") == "mcp__answer__FinalAnswer":
            tool_input = input_data["tool_input"]
            # Validate using TypeAdapter (works for BaseModel or dataclass)
            final_obj = validate_payload(tool_input)
        return {}

    # Block stop until FinalAnswer is called
    async def enforce_final_before_stop(
        input_data: dict[str, Any],
        tool_use_id: str | None,
        ctx: HookContext,
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

    # Create MCP server with FinalAnswer tool
    answer_server = create_sdk_mcp_server(name="answer", tools=[final_answer])

    # Configure options
    full_system_prompt = system_prompt + (
        "\n\nWhen you are done with your analysis, call the `FinalAnswer` tool exactly once with "
        "the final JSON payload that matches the provided schema. "
        # "Do not print the answer in plain text - use the tool."
    )

    # Note: We capture tool usage from ToolUseBlock in AssistantMessage below
    # No need for PreToolUse hook since it doesn't have parameters yet

    # Build options
    # Don't use settings parameter - let SDK use defaults but we'll backup .claude.json
    options = ClaudeAgentOptions(
        system_prompt=full_system_prompt,
        mcp_servers={"answer": answer_server},
        # Don't restrict tools - let Claude use any default tools for analysis
        permission_mode="bypassPermissions",
        cwd=cwd,
        hooks={
            "PostToolUse": [HookMatcher(matcher="mcp__answer__FinalAnswer", hooks=[capture_final])],
            "Stop": [HookMatcher(hooks=[enforce_final_before_stop])],
        },
    )

    # Replace .claude.json with minimal config to avoid hook recursion
    import shutil
    import json as json_module

    claude_json = Path.home() / ".claude.json"
    claude_backup = Path.home() / ".claude.json.dvsmith_backup"
    backed_up = False

    if claude_json.exists():
        shutil.move(str(claude_json), str(claude_backup))
        backed_up = True

    # Create minimal config with no hooks
    minimal_config = {"version": "1.0", "hooks": []}
    claude_json.write_text(json_module.dumps(minimal_config))

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        # Receive and accumulate all agent messages
        async for message in client.receive_response():
            # Debug logging: show raw message structure
            logger.debug(f"Received message type: {type(message).__name__}")
            if hasattr(message, "__dict__"):
                logger.debug(f"Message attributes: {message.__dict__}")

            # Handle AssistantMessage which contains content blocks
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        agent_messages.append({"type": "text", "text": block.text})
                        if status_cb:
                            status_cb(f"text: {block.text[:80].strip()}")
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
                            # Show tool with details from actual input
                            from pathlib import Path as PathLib
                            tool_name = block.name
                            detail = ""
                            
                            # Debug: Check what's in block.input
                            if block.input and isinstance(block.input, dict) and block.input:
                                # Show first key/value as detail
                                first_key = list(block.input.keys())[0] if block.input.keys() else None
                                if first_key and tool_name in ["Read", "Bash", "Glob"]:
                                    val = str(block.input[first_key])
                                    if tool_name == "Read":
                                        detail = f": {PathLib(val).name if '/' in val else val[:30]}"
                                    elif tool_name == "Bash":
                                        detail = f": {val[:40]}" + ("..." if len(val) > 40 else "")
                                    elif tool_name == "Glob":
                                        detail = f": {val}"
                            
                            if not detail and tool_name == "Read" and block.input:
                                path_str = block.input.get("path", "")
                                if path_str:
                                    detail = f": {PathLib(path_str).name}"
                            elif tool_name == "Bash" and block.input:
                                cmd = block.input.get("cmd", "")
                                if cmd:
                                    detail = f": {cmd[:40]}" + ("..." if len(cmd) > 40 else "")
                            elif tool_name == "Glob" and block.input:
                                pattern = block.input.get("filePattern") or block.input.get("pattern", "")
                                if pattern:
                                    detail = f": {pattern}"
                            elif tool_name == "Grep" and block.input:
                                pattern = block.input.get("pattern", "")
                                if pattern:
                                    detail = f": {pattern[:30]}" + ("..." if len(pattern) > 30 else "")
                            
                            status_cb(f"tool: {tool_name}{detail}")
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
            # Log other message types for debugging
            else:
                agent_messages.append({"type": type(message).__name__, "raw": str(message)})

    # Log successful call
    duration_ms = (time.time() - start_time) * 1000
    response_data = final_obj.model_dump() if hasattr(final_obj, "model_dump") else final_obj
    response_model_name = getattr(response_model, "__name__", str(response_model))
    log_ai_call(
        prompt=prompt,
        response_model_name=response_model_name,
        schema=schema,
        response=response_data,
        duration_ms=duration_ms,
        messages=agent_messages,
    )

    if final_obj is None:
        duration_ms = (time.time() - start_time) * 1000
        error_msg = "Claude finished without calling FinalAnswer"
        log_ai_call(
            prompt=prompt,
            response_model_name=response_model.__name__,
            schema=schema,
            error=error_msg,
            duration_ms=duration_ms,
            messages=agent_messages,
        )
        raise RuntimeError(
            "Claude finished without calling FinalAnswer. "
            "Check that the prompt is clear about calling FinalAnswer."
        )

    return final_obj

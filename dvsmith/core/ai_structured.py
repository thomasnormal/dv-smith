"""Structured AI responses using Claude Agent SDK with Pydantic models."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
    HookMatcher,
    HookContext,
)

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
) -> None:
    """Log an AI call to the log file.

    Args:
        prompt: The user prompt
        response_model_name: Name of the response model
        schema: JSON schema of the response model
        response: The response data (if successful)
        error: Error message (if failed)
        duration_ms: Call duration in milliseconds
    """
    try:
        AI_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "prompt": prompt[:500],  # Truncate long prompts
            "response_model": response_model_name,
            "schema": schema,
            "response": response,
            "error": error,
            "duration_ms": duration_ms,
        }

        with AI_LOG_FILE.open("a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        # Don't fail if logging fails
        print(f"[AI Logger] Warning: Failed to log AI call: {e}")


async def query_with_pydantic_response(
    prompt: str,
    response_model: Type[ModelT],
    system_prompt: str = "",
    cwd: str = ".",
) -> ModelT:
    """
    Query Claude and get a structured Pydantic response.

    Claude can use all reasoning but must return a final answer using
    the FinalAnswer tool with data matching the response_model schema.

    Args:
        prompt: The user prompt
        response_model: Pydantic model class for the response
        system_prompt: Additional system prompt context
        cwd: Working directory

    Returns:
        Validated instance of response_model
    """
    # Build JSON Schema from Pydantic model
    schema = response_model.model_json_schema()
    
    # Extract only the properties and required fields for the tool schema
    # The tool parameters should match the model's fields directly
    tool_schema = {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
    }

    final_obj: Optional[ModelT] = None
    start_time = time.time()

    # Print log location on first call
    if not hasattr(log_ai_call, '_printed_location'):
        print(f"[AI Logger] Logging AI calls to: {AI_LOG_FILE}")
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
            # Validate directly - tool must return data matching schema exactly
            final_obj = response_model.model_validate(tool_input)
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
        "Do not print the answer in plain text - use the tool."
    )

    options = ClaudeAgentOptions(
        system_prompt=full_system_prompt,
        mcp_servers={"answer": answer_server},
        # Don't restrict tools - let Claude use any default tools for analysis
        permission_mode="bypassPermissions",
        cwd=cwd,
        hooks={
            "PostToolUse": [HookMatcher(
                matcher="mcp__answer__FinalAnswer",
                hooks=[capture_final]
            )],
            "Stop": [HookMatcher(hooks=[enforce_final_before_stop])],
        },
    )

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            # Drain response stream
            async for _ in client.receive_response():
                pass

        if final_obj is None:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = "Claude finished without calling FinalAnswer"
            log_ai_call(
                prompt=prompt,
                response_model_name=response_model.__name__,
                schema=schema,
                error=error_msg,
                duration_ms=duration_ms,
            )
            raise RuntimeError(
                "Claude finished without calling FinalAnswer. "
                "Check that the prompt is clear about calling FinalAnswer."
            )

        # Log successful call
        duration_ms = (time.time() - start_time) * 1000
        response_data = final_obj.model_dump() if hasattr(final_obj, 'model_dump') else final_obj
        response_model_name = getattr(response_model, '__name__', str(response_model))
        log_ai_call(
            prompt=prompt,
            response_model_name=response_model_name,
            schema=schema,
            response=response_data,
            duration_ms=duration_ms,
        )

        return final_obj

    except Exception as e:
        # Log error
        duration_ms = (time.time() - start_time) * 1000
        response_model_name = getattr(response_model, '__name__', str(response_model))
        log_ai_call(
            prompt=prompt,
            response_model_name=response_model_name,
            schema=schema,
            error=str(e),
            duration_ms=duration_ms,
        )
        raise

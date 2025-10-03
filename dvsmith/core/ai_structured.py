"""Structured AI responses using Claude Agent SDK with Pydantic models."""

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
    if "type" not in schema:
        schema = {"type": "object", **schema}
    schema.setdefault("additionalProperties", False)

    final_obj: Optional[ModelT] = None

    # Define the FinalAnswer tool
    @tool(
        "FinalAnswer",
        "Return the final answer as JSON that matches the required schema.",
        schema,
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
        # Only auto-allow our FinalAnswer tool
        allowed_tools=["mcp__answer__FinalAnswer"],
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

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        # Drain response stream
        async for _ in client.receive_response():
            pass

    if final_obj is None:
        raise RuntimeError(
            "Claude finished without calling FinalAnswer. "
            "Check that the prompt is clear about calling FinalAnswer."
        )

    return final_obj

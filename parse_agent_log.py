#!/usr/bin/env python3
"""Parse terminal-bench agent.log JSON into readable format."""

import json
import sys
from pathlib import Path


def parse_log(log_path: Path):
    """Parse agent log and display in Claude Code style."""

    with open(log_path) as f:
        for line in f:
            if not line.strip():
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            # System initialization
            if msg_type == "system" and data.get("subtype") == "init":
                print(f"\n[System] Session started")
                print(f"  Model: {data.get('model')}")
                print(f"  CWD: {data.get('cwd')}")
                print()
                continue

            # Assistant messages
            if msg_type == "assistant":
                message = data.get("message", {})
                content = message.get("content", [])

                for item in content:
                    # Text output
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        print(f"\n💬 Claude:\n{text}\n")

                    # Tool use
                    elif item.get("type") == "tool_use":
                        tool_name = item.get("name")
                        tool_input = item.get("input", {})

                        print(f"\n🔧 Tool: {tool_name}")

                        # Show relevant tool parameters
                        if tool_name == "Read":
                            print(f"   Reading: {tool_input.get('file_path')}")
                        elif tool_name == "Write":
                            print(f"   Writing: {tool_input.get('file_path')}")
                        elif tool_name == "Edit":
                            print(f"   Editing: {tool_input.get('file_path')}")
                        elif tool_name == "Bash":
                            cmd = tool_input.get('command', '')
                            if len(cmd) > 80:
                                cmd = cmd[:77] + "..."
                            print(f"   Command: {cmd}")
                        elif tool_name == "Glob":
                            print(f"   Pattern: {tool_input.get('pattern')}")
                        elif tool_name == "Grep":
                            print(f"   Pattern: {tool_input.get('pattern')}")
                        else:
                            # Show first few keys for other tools
                            keys = list(tool_input.keys())[:3]
                            if keys:
                                print(f"   {', '.join(f'{k}={tool_input[k]}' for k in keys)}")
                        print()

            # User messages (tool results)
            elif msg_type == "user":
                message = data.get("message", {})
                content = message.get("content", [])

                for item in content:
                    if item.get("type") == "tool_result":
                        result_content = item.get("content", "")

                        # Truncate long results
                        if isinstance(result_content, str):
                            if len(result_content) > 500:
                                result_content = result_content[:497] + "..."
                            if result_content.strip():
                                print(f"📥 Result:\n{result_content}\n")

            # Final result
            elif msg_type == "result":
                print("\n" + "="*80)
                print("✅ Session Complete")
                print(f"   Status: {data.get('subtype')}")
                print(f"   Duration: {data.get('duration_ms', 0) / 1000:.1f}s")
                print(f"   Cost: ${data.get('total_cost_usd', 0):.4f}")

                result_text = data.get("result", "")
                if result_text:
                    print(f"\n💬 Final Response:\n{result_text}")
                print("="*80 + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: parse_agent_log.py <path-to-agent.log>")
        sys.exit(1)

    log_path = Path(sys.argv[1])
    if not log_path.exists():
        print(f"Error: {log_path} not found")
        sys.exit(1)

    parse_log(log_path)

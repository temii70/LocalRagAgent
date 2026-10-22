"""Interactive end-to-end demonstration through the real MCP stdio transport."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .review import DEFAULT_STATE


async def main():
    root = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(command=sys.executable,
        args=["-m", "mock_mcp.server", "--state", str(DEFAULT_STATE)], cwd=str(root))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            print("Tools:", ", ".join(tool.name for tool in (await client.list_tools()).tools))
            args = {"to": "partner@company.example", "subject": "Student club partnership",
                    "body": "Synthetic demo invitation to discuss a student-club partnership."}
            proposal = json.loads((await client.call_tool("propose_mock_email", args)).content[0].text)
            execution = args | {"proposal_id": proposal["proposal_id"]}
            blocked = await client.call_tool("execute_mock_email", execution)
            print("Before approval:", blocked.content[0].text, flush=True)
            await asyncio.to_thread(subprocess.run,
                [sys.executable, "-m", "mock_mcp.review", "review", proposal["proposal_id"]],
                cwd=root, check=True)
            result = await client.call_tool("execute_mock_email", execution)
            print("After review:", result.content[0].text)
            replay = await client.call_tool("execute_mock_email", execution)
            print("Replay attempt:", replay.content[0].text)
            print("Audit: python -m mock_mcp.review audit")


if __name__ == "__main__":
    asyncio.run(main())

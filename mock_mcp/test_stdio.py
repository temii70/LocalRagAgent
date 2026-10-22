"""Exercise discovery and approval enforcement through an actual MCP subprocess."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .core import Mailbox


class StdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_protocol_lifecycle(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.sqlite3"
            params = StdioServerParameters(command=sys.executable,
                args=["-m", "mock_mcp.server", "--state", str(state)],
                cwd=str(Path(__file__).resolve().parent.parent))
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()
                    tools = {tool.name for tool in (await client.list_tools()).tools}
                    self.assertEqual(tools, {"list_mock_inbox", "propose_mock_email", "execute_mock_email", "list_mock_sent"})
                    inbox = await client.call_tool("list_mock_inbox", {})
                    self.assertFalse(inbox.isError)
                    args = {"to": "partner@company.example", "subject": "Demo", "body": "Synthetic invitation"}
                    proposed = await client.call_tool("propose_mock_email", args)
                    proposal = json.loads(proposed.content[0].text)
                    execution = args | {"proposal_id": proposal["proposal_id"]}
                    blocked = await client.call_tool("execute_mock_email", execution)
                    self.assertEqual(json.loads(blocked.content[0].text)["status"], "rejected")
                    # Simulate the trusted terminal reviewer; no approval MCP tool exists.
                    Mailbox(state).decide(proposal["proposal_id"], proposal["arguments_sha256"], True)
                    sent = await client.call_tool("execute_mock_email", execution)
                    self.assertEqual(json.loads(sent.content[0].text)["status"], "mock_sent")
                    replay = await client.call_tool("execute_mock_email", execution)
                    self.assertEqual(json.loads(replay.content[0].text)["status"], "rejected")


if __name__ == "__main__":
    unittest.main()

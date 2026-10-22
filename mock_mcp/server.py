"""Run the synthetic mail tools over MCP stdio."""

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .core import INBOX, Mailbox
from .review import DEFAULT_STATE


def create_server(state=DEFAULT_STATE):
    box = Mailbox(state)
    server = FastMCP("LocalRagAgent mock mailbox")

    @server.tool()
    def list_mock_inbox() -> list[dict]:
        """Read two synthetic messages. No Gmail account is connected."""
        return INBOX

    @server.tool()
    def propose_mock_email(to: str, subject: str, body: str, account: str = "demo") -> dict:
        """Propose a synthetic send. A person must review it in a separate terminal."""
        return box.propose(to, subject, body, account)

    @server.tool()
    def execute_mock_email(proposal_id: str, to: str, subject: str, body: str, account: str = "demo") -> dict:
        """Record a mock send only with unexpired, unused approval for these exact arguments."""
        return box.execute(proposal_id, to, subject, body, account)

    @server.tool()
    def list_mock_sent() -> list[dict]:
        """Read the local synthetic outbox. Nothing has been delivered."""
        return box.sent()

    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    create_server(parser.parse_args().state).run(transport="stdio")

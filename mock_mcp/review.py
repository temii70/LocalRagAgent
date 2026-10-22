"""Trusted local reviewer. Approval is never exposed as a model-callable tool."""

import argparse
import json
import sys
from pathlib import Path

from .core import Mailbox

DEFAULT_STATE = Path(__file__).resolve().parent / ".state" / "mailbox.sqlite3"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    commands = parser.add_subparsers(dest="command", required=True)
    review = commands.add_parser("review")
    review.add_argument("proposal_id")
    commands.add_parser("audit")
    commands.add_parser("sent")
    args = parser.parse_args()
    box = Mailbox(args.state)
    if args.command == "review":
        if not sys.stdin.isatty():
            parser.error("Review requires an interactive terminal")
        proposal = box.inspect(args.proposal_id)
        # Escape control characters so untrusted message content cannot control the terminal.
        print(json.dumps(proposal, indent=2, ensure_ascii=True))
        answer = input("Type APPROVE to allow this exact mock send; anything else denies: ")
        result = box.decide(args.proposal_id, proposal["digest"], answer == "APPROVE")
    else:
        result = box.audit() if args.command == "audit" else box.sent()
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

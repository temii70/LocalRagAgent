# Approval-gated mock mail MCP server

A public, credential-free demonstration of the mail-agent execution boundary. It uses two synthetic inbox messages and a local SQLite outbox. It never connects to Gmail, SMTP, or any delivery service. No LLM, GPU, OAuth account, or API key is needed.

The server uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.26.0) over stdio. Four tools expose inbox reading, send proposals, approved mock execution, and outbox reading. Approval is available only through a separate terminal reviewer, never as an MCP tool.

## Run the interactive demonstration

From the repository root, with Python 3.12 or later:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r mock_mcp/requirements.txt
.venv/Scripts/python -m mock_mcp.demo
```

On Linux/macOS, replace `.venv/Scripts/python` with `.venv/bin/python`.

The demo discovers the tools, proposes a synthetic partnership invitation, and attempts execution before approval. That attempt is rejected. The terminal then shows the exact account, recipient, subject, body, argument hash, status, and expiration. Type `APPROVE` to allow that exact mock send; any other input denies it. The demo attempts execution and then a replay. An approved request produces one local outbox entry; the replay is rejected. Nothing is delivered.

Inspect the durable records:

```powershell
.venv/Scripts/python -m mock_mcp.review audit
.venv/Scripts/python -m mock_mcp.review sent
```

## Connect an MCP client

Configure the client to launch the virtual environment's Python with arguments `-m mock_mcp.server` and the repository root as its working directory. A generic configuration shape is:

```json
{
  "mcpServers": {
    "localrag-mock-mail": {
      "command": "C:/path/to/LocalRagAgent/.venv/Scripts/python.exe",
      "args": ["-m", "mock_mcp.server"],
      "cwd": "C:/path/to/LocalRagAgent"
    }
  }
}
```

Client configuration formats vary. Replace both example paths. The client needs stdio MCP support and a working-directory setting. To review a proposal returned by `propose_mock_email`, use a separate terminal:

```powershell
.venv/Scripts/python -m mock_mcp.review review PROPOSAL_ID
```

Then call `execute_mock_email` with that proposal ID and the identical account, recipient, subject, and body. The default account is `demo`, and recipients must end in `.example`.

## Enforcement and boundaries

- Proposals expire five minutes after creation, including time spent waiting for review.
- Approval binds the tool, account, recipient, subject, and body using a canonical SHA-256 digest. Changed arguments require a new proposal and review. A rejected changed-argument attempt does not consume approval for the original arguments.
- Denial is final for a proposal. Approved execution consumes approval once, across restarts and concurrent requests.
- A SQLite transaction records the outbox entry, approval consumption, and audit event together. Audit failure rolls back execution. Rejected executions and review decisions are also recorded.
- Audit entries contain timestamps, event names, proposal IDs, and hashes/reasons. Full synthetic message content lives in proposals/outbox. Local state is ignored by Git.
- Review requires an interactive terminal and escapes message control characters. No approval tool is advertised to a model.

This is a protocol-level boundary for a trusted local operator. Processes with filesystem or shell access under the same OS account can edit the database or run reviewer code; the demo is not an isolation boundary against such processes. Do not give an untrusted model host shell/database access and treat this as approval security. Audit records are durable local records, not tamper-proof evidence. The mock does not establish the behavior or usage counts of the separate private Gmail connector.

## Tests

```powershell
.venv/Scripts/python -m unittest mock_mcp.test_core mock_mcp.test_stdio -v
```

Tests cover missing approval, denial, changed arguments, expiry, replay, concurrent execution, persistence, atomic rollback on audit failure, and an actual MCP subprocess lifecycle. Test approvals are supplied directly by the trusted test harness, never by a model tool.

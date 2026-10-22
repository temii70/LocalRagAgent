# Security and privacy

[Overview](../README.md) | [Setup](setup-windows-wsl.md)

Local inference keeps generation on hardware you control. It does not make the whole workstation offline, encrypt stored documents, eliminate software vulnerabilities, or establish regulatory compliance. This project is not a clinical decision system and makes no HIPAA compliance claim.

## Network and accounts

- Keep authentication enabled. The Compose file explicitly sets `WEBUI_AUTH=true` and binds `127.0.0.1:3000:8080`.
- Create the first administrator account locally, then verify new sign-ups are disabled. Review account permissions before admitting other users.
- Do not publish port 3000 or tunnel it to the internet without authentication and appropriate network controls. Remote access needs a reviewed access layer, TLS, and firewall policy.
- Treat Ollama's port 11434 as an internal service. Do not assume its native API supplies an authentication barrier. Restrict any non-loopback binding at the Windows/WSL firewall and avoid router forwarding.
- Use a separate demo account for tools and synthetic or appropriately licensed public documents for screenshots and demonstrations.

The [OpenWebUI quick start](https://docs.openwebui.com/getting-started/quick-start/) covers initial account creation. [WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking) changes reachability depending on NAT, mirrored mode, and firewall settings.

## Secrets and stored data

Generate a private `WEBUI_SECRET_KEY` and keep it stable across container recreation. It supports session signing and, in applicable upstream versions, protection of stored credentials. It does not encrypt the full OpenWebUI volume. Consult the [upstream secret-key reference](https://docs.openwebui.com/reference/env-configuration/#webui_secret_key) before rotating it.

The named Docker volume can contain uploaded files, extracted text, vectors, chats, account records, and tool data. Protect backups like the original documents. Host disk encryption and account restrictions are separate controls. Deleting an upload does not prove that every cache, chat excerpt, index, or backup has been purged; verify deletion behavior in the deployed version.

The [.gitignore](../.gitignore) excludes environment files, OAuth state, private keys, private document folders, common paper formats, model weights, databases, and editor configuration. Ignore rules do not sanitize previously tracked content. Review the actual files and Git changes before publication. Do not export a running instance's full configuration into the public repository.

## Approval-gated tools

MCP describes how a client talks to tools; it does not by itself guarantee permission prompts. The private Gmail workflow is owner-reported as user-approved and has assisted with more than 200 emails. Its credentials and executable connector are excluded from this repository. Neither Compose nor the Continue example installs an approval gate.

A tool-enabled version must enforce the following outside the model:

1. Default to denial until an allowed tool and account are explicitly selected.
2. Show the exact operation and arguments before execution. For email, include recipients, CC/BCC, subject, body, attachments, and sending account.
3. Bind approval to that exact request; argument changes and later retries require renewed review. Reject expired, missing, or reused approval.
4. Enforce least-privilege OAuth scopes and an allowlist in the tool server or client executor. Read-only scopes cannot send mail; add write capability only when the reviewed workflow requires it.
5. Record an outcome and request identifier without dumping credentials or complete private messages into logs. Prevent duplicate sends on retries.

Draft creation, sending, deleting, archiving, and changing labels are distinct operations. Treat each proposed external mutation as requiring review. A model's `tool_use` capability declares a feature, not authorization. No external messages are sent by the public example.

## Untrusted documents and dependencies

Retrieved passages and email bodies are data. Text inside them must not authorize tools, request credentials, or override execution policy. Citation text can also be wrong; check the source before relying on an answer.

Use trusted parser and model sources. Test document ingestion with synthetic files first, keep dependencies updated, and review container tags/digests before upgrades. Imported OpenWebUI tools, functions, and MCP servers may execute code; install only reviewed components and avoid broad host-directory mounts.

## What can leave the machine

Initial image/model downloads require network access. Default update checks, extension telemetry, web search, remote OCR, cloud providers, and external tools can also make outbound requests. Gmail content necessarily crosses the local boundary when an approved request uses Gmail.

For an offline demonstration, prefetch dependencies, select local extraction/embedding/reranking/generation backends, disable unneeded integrations, and verify outbound behavior. Do not describe the minimal Compose file as an air-gapped deployment.

## Public mock approval boundary

The [credential-free mock](../mock_mcp/README.md) implements exact-argument approvals, five-minute expiry, single-use execution, and transactional audit records. The model cannot approve through MCP. This is a local demonstration: the operator and OS account are trusted, and shell or database access can bypass the boundary. Audit records are not tamper-proof. Synthetic messages and state stay in an ignored SQLite database; there is no Gmail or SMTP client. It does not validate the private connector or the reported email count.

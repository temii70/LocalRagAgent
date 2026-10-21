# Windows 11 and WSL2 setup

[Overview](../README.md) | [Architecture](architecture.md) | [Security](security-and-privacy.md)

PowerShell blocks run on Windows; Bash blocks run in Ubuntu under WSL2. Use your own clone location, with no personal paths saved in public configuration. These instructions describe setup; repository preparation did not replace existing services or launch another copy of the stack.

## Prepare Windows, WSL, and Docker

Install the Windows NVIDIA driver with WSL CUDA support. Do not install a separate Linux display driver inside WSL; follow [NVIDIA's WSL guidance](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

From an elevated PowerShell terminal on a new machine:

```powershell
wsl --install -d Ubuntu
wsl --update
wsl --list --verbose
```

Restart Windows if requested, finish Ubuntu account creation, and confirm the distribution runs as WSL version 2. If Ubuntu is already installed, keep the existing distribution and check its version rather than reinstalling it. See [Microsoft's WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).

Install Docker Desktop, select Linux containers, enable the WSL2 engine, and enable integration for Ubuntu. Start Docker Desktop before using Compose. The [Docker WSL2 guide](https://docs.docker.com/desktop/features/wsl/) covers those settings.

```powershell
docker version
docker compose version
wsl -d Ubuntu -- nvidia-smi
```

The last command should see the RTX 4080 Super. The reference card has 16 GB VRAM. About 32 GB system RAM and 50 GB free SSD space are planning recommendations, not validated minimums.

## Install Ollama in WSL

Use [Ollama's Linux instructions](https://docs.ollama.com/linux) inside Ubuntu. The upstream installation command is:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
ollama list
```

Inspect downloaded installer scripts before executing them if that is your normal installation policy. For systemd-based Ubuntu, check `systemctl status ollama`; start the service if needed. On a distribution without that service, `ollama serve` starts a foreground server. Do not start a second process against an occupied port.

Windows Ollama and WSL Ollama can have different model stores. During preparation, WSL Ollama reported version 0.34.2 with both aliases, while Windows reported 0.40.3 and listed only the GPT-OSS base model. These are observed versions, not required pins. Run all model commands below against the intended WSL instance.

At the repository root in a WSL terminal (Windows drives are mounted under `/mnt/c/`):

```bash
ollama pull qwen3.5:9b
ollama pull gpt-oss:20b
ollama pull nomic-embed-text
ollama create qwen3.5-32k -f ollama/Modelfile.qwen3.5-32k
ollama create gpt-oss-16k -f ollama/Modelfile.gpt-oss-16k
ollama show qwen3.5-32k --parameters
ollama show gpt-oss-16k --parameters
```

Expected context parameters are `num_ctx 32768` and `num_ctx 16384`. The base tags, advertised tool capability, and existing alias parameters were checked locally. The files inherit upstream templates and other defaults; model pulls and inference were not rerun during repository preparation. If another Ollama version rejects a model or parameter, check its release support and `ollama show` output before changing the example.

## Connect Docker to the WSL server

The configured URL is `http://host.docker.internal:11434`. Docker Desktop resolves that hostname to the Windows host; reaching a service inside WSL also depends on WSL forwarding, NAT/mirrored mode, and firewall policy. A successful Windows localhost request alone does not prove container connectivity.

Check WSL first, then Windows:

```bash
curl -fsS http://localhost:11434/api/tags
```

```powershell
Invoke-RestMethod -Uri http://localhost:11434/api/tags
```

If these list different models, a separate Windows Ollama may be answering the Windows request. Resolve which server clients should use before continuing.

For container access, Ollama may need a non-loopback bind. On WSL with systemd, use `sudo systemctl edit ollama` and add the following override, merging with existing settings:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_NUM_PARALLEL=1"
```

Then run `sudo systemctl daemon-reload` and `sudo systemctl restart ollama`. For a manually launched server, set those variables in its launch environment instead. The two memory settings are suggested starting points for a 16 GB GPU.

**Before using a non-loopback bind, restrict port 11434 to the required local/Docker path with Windows/WSL firewall rules.** Ollama should not become an unauthenticated LAN or internet endpoint. A bind address is not an access policy.

If host forwarding still fails, obtain the distribution's current address with `wsl -d Ubuntu -- hostname -I`, verify container reachability to it, and update `OLLAMA_BASE_URL` privately in `.env`. WSL addresses can change after restarts. Do not publish a private IP as a universal solution or add router forwarding. See [Microsoft's networking guide](https://learn.microsoft.com/en-us/windows/wsl/networking) and [Ollama networking configuration](https://docs.ollama.com/faq).

## Start OpenWebUI

From PowerShell at the repository root, create a fresh `.env` and fill its empty secret with 32 cryptographically random bytes. This block refuses to overwrite an existing `.env` or rotate a working key:

```powershell
if (Test-Path -LiteralPath .env) {
    throw 'An .env already exists. Keep its secret and edit it deliberately.'
}
Copy-Item -LiteralPath .env.example -Destination .env
$secretBytes = New-Object byte[] 32
$secretGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$secretGenerator.GetBytes($secretBytes)
$secretGenerator.Dispose()
$secretValue = -join ($secretBytes | ForEach-Object { $_.ToString('x2') })
(Get-Content -LiteralPath .env) -replace '^WEBUI_SECRET_KEY=.*$', "WEBUI_SECRET_KEY=$secretValue" |
    Set-Content -LiteralPath .env -Encoding ascii
Remove-Variable secretBytes, secretGenerator, secretValue
```

Review `OPENWEBUI_IMAGE` in `.env`. No existing project file pinned a stable release. The example uses `ghcr.io/open-webui/open-webui:main`, a mutable fallback also present locally. For repeatable deployments, replace it with a tested upstream release tag or digest and record the selected version. A floating tag is not a version lock.

```powershell
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose logs --tail 50 open-webui
```

Open [localhost:3000](http://localhost:3000). Create the initial administrator account locally. Verify new sign-ups are disabled afterward; the UI location varies by release. Verify the Ollama connection and model list in the administrator settings. The [OpenWebUI quick start](https://docs.openwebui.com/getting-started/quick-start/) describes initial account creation.

To check Docker-to-Ollama connectivity from the running service:

```powershell
@'
import json
import os
import urllib.request
url = os.environ["OLLAMA_BASE_URL"].rstrip("/") + "/api/tags"
with urllib.request.urlopen(url, timeout=10) as response:
    print([model["name"] for model in json.load(response)["models"]])
'@ | docker compose exec -T open-webui python -
```

If port 3000 is already in use, inspect the existing service before choosing a different loopback port for a demo. Do not stop an existing stack just to test the example. `docker compose down` stops this Compose project and keeps its named volume; adding `--volumes` deletes its stored accounts, documents, and chats.

## Configure document retrieval

The Compose file only sets up chat and storage. Configure RAG through the administrator's document/retrieval settings, then save and verify the effective values. Labels and supported fields vary by OpenWebUI release. These are starting examples, **not recovered historical benchmark settings**:

| Setting | Public example |
| --- | --- |
| Embedding engine / model | Ollama / `nomic-embed-text` |
| Embedding API URL | Same reachable WSL Ollama endpoint as chat |
| Chunking | Start with 800 tokens and 100-token overlap if token splitting is supported; otherwise record the actual splitter units and selected values |
| Hybrid search | Enabled; record fusion/weight settings |
| Reranker engine / model | Local CrossEncoder / `BAAI/bge-reranker-v2-m3` |
| Candidate / final context counts | Example: 20 candidates, 5 after reranking, where supported |
| Extraction | Default text loader for synthetic `.txt`; optional Docling for PDFs/OCR |

Nomic is a separate embedding model, not a chat model. Keep chunks within its actual input limit, independently of the generation model's context. Ollama documents the [Nomic model and embedding API](https://ollama.com/library/nomic-embed-text). The selected BGE model is a [BAAI reranker](https://huggingface.co/BAAI/bge-reranker-v2-m3); using it here is an example choice, not a verified record of the private model variant.

Current environment names include `RAG_EMBEDDING_ENGINE`, `RAG_EMBEDDING_MODEL`, `RAG_OLLAMA_BASE_URL`, `ENABLE_RAG_HYBRID_SEARCH`, and `RAG_RERANKING_MODEL`. Current releases distinguish `RAG_TOP_K` candidates from `RAG_TOP_K_RERANKER` final chunks when hybrid search is on. Consult the [environment reference](https://docs.openwebui.com/reference/env-configuration/) for your selected version. Adding variables only to `.env` will not pass them into the container unless Compose also references them. Existing database-persisted settings may override environment defaults; verify settings in the UI instead of deleting the volume.

The standard UI image supports local reranking; do not substitute a slim image expecting the same local dependencies. Initial reranker downloads need network access. Keep reranking on CPU initially to preserve Ollama's VRAM budget.

Upload the six files in [evaluation/corpus](../evaluation/corpus/), preserving filenames as document-ID mappings. Attach the knowledge collection in chat and ask the [synthetic questions](../evaluation/example_queries.json). Inspect extraction, source passages, and the configured retrieval limits. Changing embedding models requires reindexing existing documents.

### Optional Docling parsing and OCR

Docling is a separate service. Start with synthetic text to verify retrieval first. A local CPU example follows upstream [Docling Serve deployment](https://github.com/docling-project/docling-serve); the `latest` tag below is mutable and must be replaced with a tested tag/digest for repeatable runs:

```powershell
docker run --rm --name local-rag-docling --publish 127.0.0.1:5001:5001 --env DOCLING_DEVICE=cpu quay.io/docling-project/docling-serve-cpu:latest
```

This runs in the foreground and downloads a separate image. It does not grant host-directory access or GPU access. In OpenWebUI, select Docling as the extraction engine and use `http://host.docker.internal:5001` as the server URL if reachable from the UI container. Check its API documentation at [localhost:5001/docs](http://localhost:5001/docs). Select local OCR settings supported by that service and test one synthetic PDF before a larger ingestion.

Record the actual `docling`, `docling-serve`, OCR engine, PDF backend, and OpenWebUI versions. The existing "Docling v4" label does not establish those pins. API compatibility and parsing parameters are version-specific; use the selected release's docs if ingestion fails. This optional service was not launched or validated end to end during repository preparation.

## Configure Continue

Install Continue in VS Code and use its configuration UI to open the active YAML file. Merge the model entries from [continue.example.yaml](../config/continue.example.yaml); preserve any existing configuration. If VS Code runs its extension in WSL, `localhost` means WSL. A Windows extension uses Windows networking, so confirm it reaches the intended model store.

Select Qwen for routine work and GPT-OSS for reasoning/debugging. The explicit context lengths prevent a client default from silently requesting a larger window. Tool support is advertised locally for both base models, but each actual tool integration still needs testing and permission controls. See [Continue's Ollama guide](https://docs.continue.dev/guides/ollama-guide).

## Record and troubleshoot

Record `ollama --version`, `ollama list`, `ollama show <alias> --parameters`, the OpenWebUI image digest, and effective retrieval settings with each evaluation. Keep local run notes under ignored `evaluation/runs/`. Do not publish full config exports or logs containing prompts and credentials.

| Symptom | Check |
| --- | --- |
| Compose rejects an empty secret | Fill `WEBUI_SECRET_KEY` in private `.env`; no default secret is shipped |
| Missing aliases in UI | Check for separate Windows/WSL servers and container reachability |
| CPU offload or memory pressure | Inspect `ollama ps` / `nvidia-smi`; lower context and concurrency |
| Settings seem unchanged | Review persisted administrator settings before environment defaults |
| Poor citations | Inspect extraction, chunk units, collection attachment, and retrieval configuration |
| PDF ingestion fails | Check Docling compatibility, URL, OCR dependencies, and server limits |

Use [evaluation instructions](../evaluation/README.md) for scoring exported rankings. Nothing in this setup enables Gmail or sends external messages.

# Recording your demo

[Project overview](../README.md) | [Screenshot slots](../assets/README.md) | [Setup](setup-windows-wsl.md)

Record three separate clips, totaling about 2 minutes 15 seconds to 3 minutes. Start with document Q&A; it demonstrates the main use case. You can record your screen first and add narration afterward.

| Clip | Target length | Suggested filename |
| --- | --- | --- |
| Document Q&A and sources | 60-75 seconds | `01-document-qa.mp4` |
| Local coding with Continue | 45-60 seconds | `02-local-coding.mp4` |
| Models and GPU execution | 30-45 seconds | `03-models-and-gpu.mp4` |

These are target lengths, not measured response times. Trim waiting where helpful, but label cuts or speed changes rather than implying real-time performance. No video has been recorded by this repository.

## Prepare once

1. Open your existing OpenWebUI at [localhost:3000](http://localhost:3000). Use a demo account, hide the private conversation sidebar, and close unrelated tabs. Keep private document names, account details, and terminal username/path prompts outside the capture.
2. Create a knowledge collection named **Demo Workspace** and upload only the six `.txt` files from [evaluation/corpus](../evaluation/corpus/). Wait for ingestion to finish. These are fictional documents, not policies for your actual system.
3. Confirm your intended local embedding, hybrid search, and reranking settings using the [RAG setup guide](setup-windows-wsl.md#configure-document-retrieval). Attach the collection to a new chat. If your version offers full-document context versus retrieval, choose retrieval for this demonstration.
4. Select `qwen3.5-32k`. Rehearse the first prompt below and check the actual source passages before recording. The public demo corpus is text, so this clip does not demonstrate OCR.
5. Prepare the Continue exercise below in VS Code. Keep a terminal ready for the GPU clip. Increase interface text until source passages and terminal output are readable in the recording.

Keep raw recordings under `assets/recordings/`, which is ignored by Git. For example, from PowerShell at the repository root:

```powershell
New-Item -ItemType Directory -Force -Path assets/recordings | Out-Null
```

Use your normal screen recorder and microphone. Recording one application window at a time makes it easier to keep unrelated desktop content out of the video.

## Clip 1: document Q&A and sources

**Copy this prompt into a new chat with Demo Workspace attached:**

```text
Use only the attached Demo Workspace documents.

When are temporary snippets removed from the live cache, and how long do
demo backups retain them?

Give the two retention periods separately, explain why deleting the live
copy does not immediately delete a backup copy, and cite the source for
each claim. If the documents do not contain an answer, say so.
```

**What to show:**

| Time | On screen | Suggested narration |
| --- | --- | --- |
| 0-10s | Model selector and attached collection | "This is my local AI workspace. I integrated OpenWebUI with Ollama and document retrieval on a Windows workstation with WSL2." |
| 10-30s | Submit the question; let the response appear | "I'm asking a question that needs information from two synthetic documents. The application retrieves passages and supplies them to the local model." |
| 30-60s | Expand both source references and highlight the supporting sentences | "The live cache keeps snippets for seven days. Backups retain their snapshots for thirty days. I can open the sources and check the answer instead of accepting the model's response on its own." |
| 60-75s | Briefly return to the answer | "The model and retrieval tools are existing projects. My work here is their integration, configuration, evaluation, and workflow design." |

**Expected evidence:**

- [storage-policy.txt](../evaluation/corpus/storage-policy.txt): temporary snippets leave the live cache after **seven days**; removing the live copy does not immediately remove a backup.
- [backup-policy.txt](../evaluation/corpus/backup-policy.txt): demo backup snapshots are retained for **thirty days**.

Speak the answer only after checking the model's actual response. If it gives an incorrect period, omits a source, or cites an unrelated passage, investigate before recording a successful take. Citation appearance alone does not prove the answer is supported.

**Optional backup question:**

```text
Using only Demo Workspace, who approves a proposed outgoing demo message,
and what happens if the tool arguments change after approval? Cite the
documents. Do not invoke tools or send any message.
```

Expected sources are `access-policy` and `incident-response`: a human operator approves the proposal; changed arguments invalidate approval and require review again. This demonstrates document retrieval about a fictional workflow, not execution of a Gmail tool.

Capture `rag-citations.png` while both the answer and a supporting source are readable. Capture `workspace-overview.png` from the same synthetic session with the selected model visible.

## Clip 2: local coding with Continue

The [starter exercise](../assets/demo/recall_exercise.py.txt) intentionally confuses hit rate with recall. It is a recording prop, separate from the working [evaluation scorer](../evaluation/score.py).

Create a disposable copy from PowerShell at the repository root:

```powershell
New-Item -ItemType Directory -Force -Path evaluation/runs/continue-demo | Out-Null
Copy-Item -LiteralPath assets/demo/recall_exercise.py.txt -Destination evaluation/runs/continue-demo/recall_exercise.py
python evaluation/runs/continue-demo/recall_exercise.py
```

The unedited exercise should report **one failed case**: retrieving one of two relevant documents returns 1.0, but recall should be 0.5. That failure is intentional. Keep the public starter unchanged; Continue should edit only the disposable copy. Copying the starter again resets that copy for another take.

Open the disposable `.py` file in VS Code. Select **Qwen Fast 32K** in Continue, or your equivalent alias label. Provide the current file as context and use edit mode if needed.

**Copy this prompt into Continue:**

```text
This file is a small retrieval-evaluation exercise. One test fails because
recall_at_k returns 1.0 when only one of two relevant documents is retrieved.

Explain the bug briefly, then fix only recall_at_k in the current file.
Recall is the fraction of labeled relevant documents found among the first
k unique retrieved document IDs. Preserve the input validation and
de-duplication before the cutoff. Do not change the cases or expected values.
Use only the Python standard library. Do not modify any other files.
```

**What to show:**

| Time | On screen | Suggested narration |
| --- | --- | --- |
| 0-10s | Local model selection, exercise, and failing case | "Continue connects VS Code to the same local model server. This example has a small metric bug: it treats finding any relevant document as complete recall." |
| 10-35s | Submit the prompt; inspect the proposed edit | "I'm asking for a focused fix and reviewing the change before applying it. The correct calculation counts relevant matches and divides by all relevant documents." |
| 35-60s | Apply the edit and rerun the file | "The tests now distinguish partial recall, no matches, duplicate results, and the retrieval cutoff." |

Only use the final narration if the rerun actually reports `5/5 cases passed`. Keep the terminal output visible long enough to read. A successful take demonstrates local coding assistance and a reviewed change, not a broad coding benchmark.

Capture `continue-local-models.png` with the local model label and the small diff or passing output visible.

## Clip 3: models and GPU execution

Use the WSL server, since a separate Windows Ollama may have a different model store. Run these from PowerShell before recording:

```powershell
wsl -d Ubuntu -- ollama show qwen3.5-32k --parameters
wsl -d Ubuntu -- ollama show gpt-oss-16k --parameters
```

Show `num_ctx 32768` for Qwen and `num_ctx 16384` for GPT-OSS. These are configured alias settings; the live request can have a different context if a client overrides them.

Prepare a GPU monitor in another terminal:

```powershell
wsl -d Ubuntu -- nvidia-smi -l 1
```

Press **Ctrl+C** when finished. In OpenWebUI, select Qwen and submit this harmless prompt to create an actual generation request:

```text
Explain how keyword search and semantic search complement each other in
document retrieval. Use about 400 words and one simple example.
```

While the response is generating, check the active model in a second terminal:

```powershell
wsl -d Ubuntu -- ollama ps
```

**Suggested narration:**

> "I use Qwen for routine work and GPT-OSS for harder reasoning and debugging. The aliases configure different context budgets. Ollama runs the selected model through WSL on my RTX 4080 Super. Here, `ollama ps` shows the active model and CPU/GPU placement, and `nvidia-smi` shows GPU activity during this request. This is a live execution check, not a performance benchmark."

Keep the model selector, active-model output, and GPU monitor readable. If the actual placement includes CPU offload, describe that accurately; do not claim full GPU residency. You do not need both models loaded together. If `ollama ps` is empty, start another request and capture it while active rather than presenting idle output as evidence of inference.

Capture `gpu-memory.png` during the request. A screenshot does not establish peak memory, speed, or end-to-end privacy guarantees.

## Optional extra: evaluation format

If you want a separate 30-second technical clip, show the scorer on the supplied handwritten rankings. Use a fresh output filename if this one already exists:

```powershell
python evaluation/score.py --queries evaluation/example_queries.json --predictions evaluation/predictions.example.json --output evaluation/runs/recording-example.csv
```

Expected output is `evidence_type=illustrative`, macro recall@5 `0.833333`, and hit rate@5 `1.000000`.

Suggested narration: "This utility scores supplied document rankings. These examples are handwritten to explain the metric; they are not measurements from the retrieval system. The original 64% to 86% improvement is reported separately, and the private experiment data isn't included here."

Do not describe this command as running a new retrieval experiment or reproducing the reported improvement.

## Optional extra: actual tool approval

Record this only if your existing private workflow is ready and a separate demo account is available. Show the actual request preview, including exact recipients and arguments, and reject or cancel it. No email needs to be sent for a useful approval demonstration. If demonstrating approval invalidation, show the executor actually blocking changed arguments; do not infer it from model text.

The public repository does not ship the Gmail connector or enforcement gate. Describe the clip as your separately configured workflow and keep credentials and real recipients out of view. If it is not ready, leave this clip out.

## Add the finished clips

Review the entire recordings for private material. Upload the edited clips to your chosen video host, then add links in the root README near the screenshot section. Do not claim a recording exists until it has been uploaded and its link works.

Suggested titles:

- **Document Q&A with source verification**
- **Local coding assistance with a reviewed fix**
- **Local model configuration and GPU execution**

Add the four screenshots listed above under `assets/` once reviewed. Keep raw video in ignored `assets/recordings/`; use hosted links for the public clips. You can add `tool-approval.png` later if a real, safe approval demonstration is available.

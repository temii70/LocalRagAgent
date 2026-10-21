# Demo assets and screenshots

[Project overview](../README.md)

The root README links the [document Q&A video](../01-document-qa.mp4) and [local coding video](../02-local-coding.mp4..mp4). Their clickable preview images are actual stills from those recordings, stored in `demo/`.

The [Continue starter exercise](demo/recall_exercise.py.txt) intentionally contains a recall calculation bug. Copy it into an ignored `evaluation/runs/continue-demo/` folder before editing; the starter should pass four of five cases, and a correct fix should pass all five. The working project scorer is [evaluation/score.py](../evaluation/score.py). Keep raw takes in ignored `assets/recordings/`.

The additional screenshot slots below point to recommended filenames without embedding missing images. Capture the real system using synthetic documents and a separate demo account, then add image links to the root README.

| Recommended filename | Capture |
| --- | --- |
| `workspace-overview.png` | OpenWebUI with the two aliases visible and a short synthetic conversation |
| `rag-citations.png` | A synthetic corpus question, answer, and expanded source passage; show readable citations |
| `continue-local-models.png` | Continue's local model choices or a small reviewed edit in a demo project |
| `tool-approval.png` | Actual tool-approval preview with exact demo arguments, captured before execution; label any mock clearly |
| `gpu-memory.png` | `ollama ps` and a cropped `nvidia-smi` view during one model request |

Use readable captures around 1440 pixels wide, crop unrelated windows, and prefer PNG for interface text. Redact names, email addresses, avatars, OAuth prompts, tokens, private URLs, local usernames/paths, document titles, and browser history. Do not show real outreach recipients or private lecture/research content.

Do not stage an approval screenshot as proof that the public repository implements a Gmail gate. If no safe tool demo is available, leave that slot pending. A GPU screenshot records one instant; it does not establish peak memory or benchmark throughput. Do not create a 64%/86% chart that implies the synthetic fixtures reproduce the reported experiment.

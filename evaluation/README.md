# Retrieval evaluation

[Method and evidence limits](../docs/evaluation.md) | [Project overview](../README.md)

This folder contains two separate evaluation tracks:

- **[Measured public benchmark](public/scifact/README.md):** 75 published, labeled BEIR SciFact test claims against all 5,183 abstracts. [Results and raw rankings](results/scifact-75/README.md) compare dense, BM25, hybrid, and hybrid+BGE retrieval.
- **Synthetic format example:** six original fictional documents and handwritten rankings that demonstrate the scoring schema. These remain explicitly labeled `illustrative`.

Neither track reproduces the earlier private 64%/86% observation. The public benchmark has its own measured results and source judgments.

## Verify measured results

```powershell
python evaluation/verify_public.py
```

This independent check needs only Python's standard library and no model server. Full inference instructions, model pins, and dataset attribution are in the [public benchmark guide](public/scifact/README.md).

## Synthetic format example files

| File | Purpose |
| --- | --- |
| [corpus/](corpus/) | Six short fictional policy/engineering documents; filename stems are stable IDs |
| [example_queries.json](example_queries.json) | Three synthetic questions, relevant document IDs, and optional notes |
| [predictions.example.json](predictions.example.json) | Handwritten rankings, with a run ID and explicit evidence label |
| [results.example.csv](results.example.csv) | Expected per-query scoring output for that illustrative input at k=5 |
| [score.py](score.py) | Offline scorer using only Python's standard library |

The corpus policies are fictional test material. They are not retention or security guarantees for the actual platform.

## Run the format demonstration

Use Python 3.10 or newer from the repository root. No packages, GPU, model download, credentials, or network access are required:

```powershell
python evaluation/score.py --queries evaluation/example_queries.json --predictions evaluation/predictions.example.json --output evaluation/runs/example.csv
```

Expected console output begins with:

```text
evidence_type=illustrative run=handwritten-format-demo queries=3
macro_recall@5=0.833333 hit_rate@5=1.000000
```

These values follow from the handwritten rankings, not a retrieval experiment. The saved CSV should match [results.example.csv](results.example.csv). Output files are created exclusively: if the destination already exists, choose a different filename. Local `runs/` output is ignored by Git.

## Input and result schemas

Each query needs `query_id`, `query`, and a non-empty `relevant_document_ids` list. `notes` is optional. IDs use letters, digits, dots, underscores, colons, and hyphens, starting with a letter or digit. Keep private titles and personal paths out of IDs used in public examples.

A predictions file has `evidence_type` (`illustrative` or `measured`), a `run_id`, and a `rankings` list. Each ranking has `query_id` and `retrieved_document_ids` in retrieval order. An empty list means no documents were returned. Every query must appear exactly once; missing, duplicate, and unknown query IDs are rejected. A `measured` label is the operator's declaration of provenance, not an authenticity check by the scorer.

The scorer de-duplicates document IDs in rank order before selecting k. Relevant labels cannot contain duplicates. If your retriever returns chunks, first map them to source document IDs and preserve their order. This is document-level recall; evaluating the first five chunks instead is a different metric.

| CSV field | Meaning |
| --- | --- |
| `evidence_type`, `run_id`, `query_id` | Provenance category, run, and question |
| `k` | Number of distinct retrieved documents considered |
| `relevant_document_ids` | All relevance labels, separated by `|` |
| `retrieved_document_ids` | Top k unique document IDs, separated by `|` |
| `relevant_count`, `relevant_retrieved` | Denominator and matching document count |
| `recall_at_k` | Matching relevant documents divided by all relevance labels |
| `hit_at_k` | 1 if any relevant document was retrieved, otherwise 0 |

Macro recall averages the per-query ratios, weighting every question equally. Hit rate averages the hit flags. The script reports both and keeps full-precision ratios for the aggregate before rounding to six decimal places. Questions with no relevance labels need a separate no-answer evaluation.

## Collect real retrieval output

Upload the corpus using the [setup guide](../docs/setup-windows-wsl.md#configure-document-retrieval). Freeze your configuration, ask every query, and export actual retrieval rankings from your OpenWebUI version. Map internal file IDs to these stable document IDs. Do not reconstruct a ranking from the generated answer's citations: they may be only a subset of retrieved passages.

Create a new predictions file under ignored `evaluation/runs/`, preserve all query IDs, mark real exports `measured`, and use a descriptive run ID. Run the scorer with that file. It performs **no retrieval**, connects to no OpenWebUI endpoint, and does not infer the retrieval configuration; save version and configuration notes alongside your export. A version-specific retrieval exporter is not included.

For a comparison, use separate dense-only and hybrid-plus-reranker exports on the same labeled questions, then compare macro recall@5. Those are newly measured experiments, not validation of historical private results. Follow the [full protocol](../docs/evaluation.md) before making broader performance claims.

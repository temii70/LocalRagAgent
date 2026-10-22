# Measured retrieval results: SciFact-75

[Frozen data and reproduction](../../public/scifact/README.md) | [Summary CSV](summary.csv) | [Per-query CSV](per_query.csv) | [Runtime and model metadata](metadata.json)

Completed on **October 21, 2026**. The same 75 labeled BEIR SciFact test claims were searched against all 5,183 abstracts. These are actual local model/retrieval outputs, not illustrative rankings or a reconstruction of the private 64%/86% observation.

| Configuration | Macro recall@5 | Hit rate@5 |
| --- | ---: | ---: |
| Nomic dense retrieval | **81.89%** | 84.00% |
| BM25 | 74.78% | 78.67% |
| Hybrid RRF | 81.78% | **85.33%** |
| Hybrid RRF + BGE reranking | 79.78% | 82.67% |

**Hybrid+BGE did not improve recall in this run.** Its difference from dense retrieval is **-2.11 percentage points**, with a paired bootstrap 95% interval of **[-9.89, +5.67] percentage points**. The interval includes zero, and this small sample does not establish a reliable advantage for either configuration.

Compared with dense search, hybrid+BGE improved per-query recall on **4** claims, worsened it on **8**, and left it unchanged on **63**. Hybrid's 20-candidate pool had **91.89%** macro recall before the final top-five cutoff. That is a diagnostic of candidate availability, not a result at k=5.

Hybrid has a slightly higher hit rate but slightly lower macro recall than dense search. Those metrics differ when a claim has more than one relevant abstract: one relevant hit can still miss other labeled evidence.

## Raw artifacts

| Artifact | Contents |
| --- | --- |
| [dense.predictions.json](dense.predictions.json) | Top 20 IDs and cosine scores for every claim |
| [bm25.predictions.json](bm25.predictions.json) | Top 20 IDs and lexical scores |
| [hybrid.predictions.json](hybrid.predictions.json) | Top 20 fused candidates and RRF scores |
| [hybrid_bge.predictions.json](hybrid_bge.predictions.json) | Those candidates reordered by raw BGE logits |
| [candidate_coverage.json](candidate_coverage.json) | Candidate IDs and relevant-document coverage |
| [per_query.csv](per_query.csv) | All 300 per-query scoring rows, including failures |
| [summary.csv](summary.csv) | Four aggregates plus diagnostic ranking timings |
| [metadata.json](metadata.json) | Source/data/config hashes, exact model identities, packages, runtime, cache reuse, and bootstrap interval |

The scorer uses distinct abstract IDs and positive source judgments. No claim was dropped after retrieval, and no answer-generation model supplied relevance labels. Full abstract text stays in the ignored download cache; the published claim subset and labels have [separate data attribution and licensing](../../public/scifact/ATTRIBUTION.md).

## Verify without inference

```powershell
python evaluation/verify_public.py
```

The independent verifier recomputes the metrics from the published rankings, checks all per-query rows and aggregates, and verifies the recorded source/config hashes. A full rerun is documented with the [frozen inputs](../../public/scifact/README.md#recompute-embeddings-and-rankings).

## Interpretation

The evidence supports reporting this configuration's measured behavior on this subset, including the lack of a reranking gain. It does not support claiming a general RAG improvement, answer correctness, OCR quality, or production latency. The harness uses one abstract per document and exact dense search; it does not call OpenWebUI or exercise its chunking, vector database, access controls, or tool execution.

BGE processes up to 512 combined tokens per claim/abstract pair, while the embedding and lexical stages have different input handling. Candidate depth and truncation are possible subjects for future ablations, not established explanations for this result. No parameters were changed to chase a positive gain after seeing these scores. Pretrained models' training overlap with SciFact has not been established.

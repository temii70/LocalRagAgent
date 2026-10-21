# Retrieval evaluation

[Overview](../README.md) | [Runnable example](../evaluation/README.md)

## What is reported

The owner reports testing the RAG system on more than 100 lecture/research documents and improving top-5 retrieval recall from **64%** at baseline to **86%** with hybrid retrieval and BGE reranking. That is a 22 percentage-point increase. The document count is not a query count.

The original corpus, query set, relevance judgments, exact baseline settings, aggregation method, and raw retrieval logs are not supplied. The comparison is described as baseline versus hybrid plus reranking; those missing details prevent a reconstruction of precisely how the historical percentage was calculated. No confidence interval, latency measurement, isolated reranker gain, or answer-accuracy improvement can be inferred.

The protocol below defines a reproducible method for **new** experiments. It is not asserted to be the historical method behind the reported figures. The public synthetic data demonstrates scoring only and is not evidence for 64% or 86%.

## What recall measures

Suppose a question has four documents labeled relevant. If three appear among the first five retrieved documents, its recall@5 is `3 / 4 = 0.75`. Relevant documents count once, even when several chunks came from the same source.

```text
recall@k(query) = relevant documents in first k unique retrieved documents
                 ------------------------------------------------------
                         all documents labeled relevant

macro recall@k = mean of per-query recall@k over the full query set
```

The public scorer collapses repeated document IDs **before** taking the first k. This evaluates a ranking of distinct documents, not the first k chunks given to an LLM. Export enough candidates to obtain five unique documents where possible. If a run returns fewer than k distinct documents, score those returned without filling the remaining slots from another run.

Hit@k asks whether there was at least one relevant document. It can be 1 while recall@k is only 0.25. The two coincide for a question with exactly one relevant document; do not use the names interchangeably for other cases. Retrieval metrics do not establish that the answer was correct or that its citations support every claim.

## Reproduce a comparison

1. Freeze a synthetic or appropriately licensed public corpus. Give each document a stable ID and record file hashes, version, and licensing. Keep private data out of public artifacts.
2. Write questions covering paraphrases, exact terms, multi-document questions, and difficult extraction. Label all relevant document IDs independently of the retriever's ranking. Use at least one relevant document per scored query; evaluate no-answer questions separately.
3. Keep a held-out set for final evaluation. Tune chunking, fusion weights, candidate counts, and thresholds on a separate development set. Record who labeled relevance and how disagreements were resolved.
4. Run a new, explicitly defined baseline, such as dense retrieval only, on the frozen queries. This is a proposed baseline, not a recovered historical configuration.
5. Run hybrid retrieval with BGE reranking on the same queries and corpus. Keep parsing, embeddings, relevance labels, and the evaluation unit fixed; record intentional differences. Extra dense-plus-reranker and hybrid-only runs can separate contributions.
6. Export actual ranked retrieval results before answer generation. Preserve query IDs, document mappings, full ranking order, and configuration. UI answer citations can omit retrieved candidates and are not a reliable substitute for a retrieval trace. No version-specific OpenWebUI exporter is supplied here; adapt its documented API or instrument your deployed version.
7. Convert each export to the [prediction schema](../evaluation/predictions.example.json), mark actual retrieval output `measured`, and run the [scorer](../evaluation/score.py). The label records provenance supplied by the operator; the script cannot authenticate that provenance.
8. Compare macro recall@5 across exactly the same query IDs. Report query count, relevant-document counts, configuration, and failures alongside the average. If reporting uncertainty, use an appropriate paired analysis rather than treating chunks as independent samples.

An empty retrieved list is a zero, not a reason to drop a difficult question. The scorer requires every query ID to appear exactly once in a run. Queries without relevance labels are rejected because recall's denominator would be zero.

## Record with each real run

| Area | Required context |
| --- | --- |
| Corpus and labels | Dataset version, document hashes, query count, judgments, split |
| Extraction | Docling package/server version, PDF backend, OCR engine/languages |
| Chunking | Splitter, token/character units, size, overlap, metadata mapping |
| Embedding | Nomic tag/hash, embedding input handling, index rebuild state |
| Retrieval | Dense/keyword settings, fusion method/weights, thresholds, candidate count |
| Reranking | Exact BGE variant/revision, input truncation, final count |
| Runtime | OpenWebUI image digest, Ollama version, hardware, concurrency |
| Scoring | Document/chunk unit, de-duplication policy, k, macro/micro aggregation |

Record generation settings separately if evaluating answers. They do not determine the recall of an already exported retrieval ranking. Preserve failures and keep raw private logs outside version control.

## Public example and limits

The [synthetic corpus](../evaluation/corpus/), [three questions](../evaluation/example_queries.json), [handwritten rankings](../evaluation/predictions.example.json), and [example CSV](../evaluation/results.example.csv) are deliberately small. Every result row says `illustrative`; these rankings were not produced by OpenWebUI. They demonstrate multi-document recall, not statistical performance or OCR quality. See [evaluation/README.md](../evaluation/README.md) for commands and expected output.

Future work is to publish actual retrieval exports on a larger public corpus, document the labeling process, and separately measure latency, extraction quality, answer support, and memory use.

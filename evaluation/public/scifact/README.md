# Public SciFact retrieval benchmark

[Measured results](../../results/scifact-75/README.md) | [Method overview](../../../docs/evaluation.md) | [Data attribution](ATTRIBUTION.md)

This benchmark retrieves scientific abstracts for **75 existing, labeled claims** sampled from the **BEIR SciFact test split**, searching all **5,183 abstracts**. It uses the published relevance judgments rather than newly generated questions or model-generated labels. SciFact claims are statements to retrieve evidence for, not conversational questions.

The query selection was frozen before retrieval: Python `random.Random(42).sample` selects 75 IDs from the numerically sorted list of 300 positive-qrel test IDs. The selected IDs are then sorted numerically for execution. There are 84 positive query/document judgments and 78 distinct relevant abstracts in this subset. No retrieval parameters were tuned on this sample.

## Published inputs

| File | Contents |
| --- | --- |
| [queries.json](queries.json) | Claim text, query IDs, and relevant document IDs |
| [qrels.tsv](qrels.tsv) | Positive published judgments for the selected IDs |
| [manifest.json](manifest.json) | Selection seed/IDs, archive checksum, and source/member hashes |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Original authors, source, modifications, and CC BY-SA 4.0 terms |

The complete corpus is fetched into ignored `evaluation/.cache/scifact/`, not committed. [BEIR](https://github.com/beir-cellar/beir) publishes the source archive and its MD5; the manifest also records SHA-256 hashes. The [SciFact dataset card](https://huggingface.co/datasets/BeIR/scifact) describes the corpus and query schema.

## Fixed retrieval configurations

Each abstract is one document: stripped title, a newline, and abstract text. There is no PDF parsing, OCR, passage chunking, answer generation, or OpenWebUI request in this harness.

| Run | Definition |
| --- | --- |
| `dense` | Nomic embeddings, L2 normalization, exact cosine search across all abstracts |
| `bm25` | BM25Okapi with `k1=1.5`, `b=0.75`; lowercase `[a-z0-9]+` tokens |
| `hybrid` | Top 20 dense + top 20 BM25 lists combined by unweighted reciprocal-rank fusion with constant 60; retain 20 |
| `hybrid_bge` | The same 20 hybrid candidates reordered by BGE; no candidate added or removed |

Dense and BM25 ties follow frozen corpus order; RRF ties follow first appearance in dense-then-BM25 rankings. BGE ties preserve hybrid order. Only the first five unique document IDs enter recall@5. All 20 ranked IDs and raw scores are retained in each predictions file.

The [configuration](../../public-config.json) pins the Nomic Ollama manifest digest and BGE model revision. Document and query prefixes are `search_document: ` and `search_query: `, following [Nomic's model instructions](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5). Ollama input truncation is enabled; vectors have 768 dimensions. The model's context information is recorded in the measured metadata.

The [BGE cross-encoder](https://huggingface.co/BAAI/bge-reranker-v2-m3) receives a claim/abstract pair. This run uses Hugging Face Transformers, raw logits, a maximum combined length of 512 tokens, batch size 8, CUDA float32, and disabled TF32. Longer pairs are truncated by the tokenizer. Model weights are not redistributed.

## Verify the published scores

From the repository root, with Python 3.10 or newer:

```powershell
python evaluation/verify_public.py
```

No model, GPU, package installation, download, or account is needed for this check. It independently computes recall with exact fractions, compares all 300 per-query result rows and four summary rows, checks source/configuration hashes, and checks that reranking preserves candidate membership. It verifies artifact consistency, not the authenticity of an arbitrary author's run.

## Recompute embeddings and rankings

The measured environment used Python 3.12.12, Ollama 0.40.3, an RTX 4080 Super, PyTorch 2.10.0+cu128, and the package versions in [requirements-public.txt](../../requirements-public.txt). The complete environment and immutable container image digest are in [metadata.json](../../results/scifact-75/metadata.json).

In an isolated Python 3.12 environment, install the CUDA build and benchmark requirements:

```text
python -m pip install torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r evaluation/requirements-public.txt
```

The CUDA wheel command follows [PyTorch's versioned installation instructions](https://pytorch.org/get-started/previous-versions/). A compatible NVIDIA driver and reachable Ollama server are required. This configuration uses CUDA for reranking; a CPU run needs a separate config/result directory and will be slower.

On the Ollama instance used for the benchmark:

```text
ollama pull nomic-embed-text:latest
python evaluation/prepare_public.py
python evaluation/benchmark.py --ollama-url http://localhost:11434 --output evaluation/runs/scifact-rerun
```

Preparation downloads and validates the archive, reconstructs the corpus cache, and verifies the existing frozen selection without overwriting it. If a Windows Python installation cannot verify the archive server's certificate chain, Windows' native TLS client can populate the cache first, with certificate verification still enabled:

```powershell
New-Item -ItemType Directory -Force -Path evaluation/.cache/scifact | Out-Null
curl.exe --fail --location --output evaluation/.cache/scifact/scifact.zip https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip
python evaluation/prepare_public.py
```

The runner checks the configured embedding digest before inference and downloads the pinned BGE revision if no local snapshot is supplied. Embedding caches are keyed by text, prefix, model digest, and truncation setting. A new result directory is required; existing results are never overwritten. Initial downloads need internet access; no hosted inference API or private documents are involved.

For a Docker execution, the Ollama endpoint is normally `http://host.docker.internal:11434`. The measured run reused the locally installed CUDA image identified in its metadata, mounted only the existing Hugging Face model cache read-only, and installed the pinned 8.6 kB BM25 wheel into that temporary container. This reused existing dependencies; the Python script is independent of Docling's API.

An initial CPU reranking attempt was stopped before a complete report because CUDA was available. Its document/query embeddings were reused for the final run; the metadata explicitly records cache reuse. Corpus, labels, candidate counts, fusion settings, and model identities were unchanged. No accuracy-driven configuration search or successful-result selection was performed.

## Metrics and boundaries

For each claim, recall@5 is the number of labeled relevant abstracts in the top five divided by all its positive relevance labels. Macro recall weights each claim equally. Hit@5 is one when at least one relevant abstract is found. A claim with multiple relevant abstracts can have a hit but only partial recall. Unjudged documents are treated as nonrelevant; supporting and refuting evidence both count as relevant under the source qrels.

The report includes a paired query bootstrap for the hybrid+BGE minus dense recall difference: 10,000 resamples, seed 42, percentile 95% interval. Claims can share source papers, so this is sample-level uncertainty rather than an assurance of independent paper-level generalization.

This is a 75-claim subset, not the complete 300-query BEIR evaluation or a leaderboard submission. Pretrained model exposure to benchmark data has not been audited. Truncation, candidate depth, and fusion settings can affect results; this run does not isolate their individual effects. Recorded ranking times exclude embedding, indexing, model loading, OCR, generation, and UI overhead.

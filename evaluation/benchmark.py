#!/usr/bin/env python3
"""Measure retrieval on frozen public SciFact claims using local model inference."""

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean

import numpy as np
from rank_bm25 import BM25Okapi

from score import FIELDS, score


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def request_json(url, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def top_indices(values, count):
    values = np.asarray(values)
    if not np.isfinite(values).all():
        raise ValueError("Non-finite ranking scores")
    # Stable sorting resolves ties in the frozen corpus order.
    return np.argsort(-values, kind="stable")[:count].tolist()


def fuse(rankings, constant=60, count=20):
    """Unweighted reciprocal-rank fusion; no relevance labels enter this step."""
    scores = defaultdict(float)
    first_seen = {}
    for ranking in rankings:
        for rank, document_index in enumerate(dict.fromkeys(ranking), 1):
            first_seen.setdefault(document_index, len(first_seen))
            scores[document_index] += 1.0 / (constant + rank)
    selected = sorted(scores, key=lambda index: (-scores[index], first_seen[index]))[:count]
    return selected, [scores[index] for index in selected]


def embed(texts, prefix, label, cache, config, endpoint):
    identity = {
        "texts_sha256": hashlib.sha256(json.dumps(texts, ensure_ascii=False).encode()).hexdigest(),
        "prefix": prefix,
        "model_digest": config["embedding_digest"],
        "truncate": config["embedding_truncate"],
    }
    name = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    array_path, info_path = cache / (name + ".npy"), cache / (name + ".json")
    if array_path.exists() and info_path.exists() and json.loads(info_path.read_text()) == identity:
        array = np.load(array_path, allow_pickle=False)
        if array.shape[0] == len(texts) and array.ndim == 2 and np.isfinite(array).all():
            print(f"Using verified {label} embedding cache: {len(texts)} rows", flush=True)
            return array, True
    values = []
    batch_size = config["embedding_batch_size"]
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        result = request_json(endpoint + "/api/embed", {
            "model": config["embedding_model"],
            "input": [prefix + text for text in batch],
            "truncate": config["embedding_truncate"],
            "keep_alive": "5m",
        })
        vectors = result.get("embeddings", [])
        if len(vectors) != len(batch):
            raise ValueError("Embedding response row count mismatch")
        values.extend(vectors)
        if start == 0 or (start // batch_size) % 10 == 0 or start + batch_size >= len(texts):
            print(f"Embedded {label}: {min(start + batch_size, len(texts))}/{len(texts)}", flush=True)
    array = np.asarray(values, dtype=np.float32)
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if not np.isfinite(array).all() or np.any(norms == 0):
        raise ValueError("Invalid embedding values")
    array /= norms
    np.save(array_path, array, allow_pickle=False)
    write_json(info_path, identity)
    return array, False


def paired_bootstrap(baseline, improved, seed, resamples):
    deltas = np.asarray(improved, dtype=np.float64) - np.asarray(baseline, dtype=np.float64)
    generator = np.random.default_rng(seed)
    means = deltas[generator.integers(0, len(deltas), size=(resamples, len(deltas)))].mean(axis=1)
    lower, upper = np.quantile(means, [0.025, 0.975])
    return {"mean_delta": float(deltas.mean()), "percentile_95_ci": [float(lower), float(upper)], "seed": seed, "resamples": resamples}


def predict_pairs(model, tokenizer, pairs, config):
    import torch
    values = []
    for start in range(0, len(pairs), config["reranker_batch_size"]):
        batch = pairs[start:start + config["reranker_batch_size"]]
        encoded = tokenizer(
            [pair[0] for pair in batch], [pair[1] for pair in batch],
            padding=True, truncation=True, max_length=config["reranker_max_length"], return_tensors="pt",
        ).to(config["reranker_device"])
        with torch.inference_mode():
            values.extend(model(**encoded, return_dict=True).logits.view(-1).float().cpu().tolist())
    return np.asarray(values, dtype=np.float32)


def run(args):
    started = time.perf_counter()
    config = json.loads(args.config.read_text())
    manifest = json.loads((args.dataset / "manifest.json").read_text())
    query_path = args.dataset / "queries.json"
    if sha256(query_path) != manifest["queries_sha256"]:
        raise ValueError("Frozen queries have changed")
    if sha256(args.dataset / "qrels.tsv") != manifest["qrels_sha256"]:
        raise ValueError("Frozen relevance judgments have changed")
    corpus_path = args.cache / "corpus.jsonl"
    if sha256(corpus_path) != manifest["member_sha256"]["corpus.jsonl"]:
        raise ValueError("Corpus checksum mismatch; run prepare_public.py first")
    queries = json.loads(query_path.read_text())
    corpus = [json.loads(line) for line in corpus_path.read_text().splitlines() if line]
    assert len(corpus) == manifest["corpus_documents"]
    assert [query["query_id"] for query in queries] == manifest["query_ids"]
    if args.output.exists():
        raise FileExistsError("Result folder exists; use a new output path to preserve recorded runs")

    endpoint = args.ollama_url.rstrip("/")
    tags = request_json(endpoint + "/api/tags")["models"]
    current = next((model for model in tags if model["name"] == config["embedding_model"]), None)
    if current is None or current["digest"] != config["embedding_digest"]:
        raise ValueError("Ollama embedding model missing or digest differs from the frozen configuration")
    ollama_version = request_json(endpoint + "/api/version")["version"]
    model_info = request_json(endpoint + "/api/show", {"model": config["embedding_model"]})
    if manifest["selected_queries"] != len(queries):
        raise ValueError("Query count mismatch")
    document_ids = [document["_id"] for document in corpus]
    texts = [(document["title"] + "\n" + document["text"]).strip() for document in corpus]
    query_texts = [query["query"] for query in queries]
    args.output.mkdir(parents=True)
    embeddings_cache = args.cache / "embeddings"
    embeddings_cache.mkdir(exist_ok=True)
    print(f"Frozen evaluation: {len(queries)} claims, {len(corpus)} abstracts; no generation or OCR", flush=True)
    embed_started = time.perf_counter()
    document_vectors, document_cached = embed(texts, config["document_prefix"], "documents", embeddings_cache, config, endpoint)
    query_vectors, query_cached = embed(query_texts, config["query_prefix"], "queries", embeddings_cache, config, endpoint)
    embedding_seconds = time.perf_counter() - embed_started
    embedding_processes = request_json(endpoint + "/api/ps").get("models", [])
    placement = next(({key: model.get(key) for key in ["size", "size_vram"]}
                      for model in embedding_processes if model.get("digest") == config["embedding_digest"]), {})
    if query_vectors.shape[1] != document_vectors.shape[1]:
        raise ValueError("Embedding dimension mismatch")

    lexical = BM25Okapi([tokenize(text) for text in texts], k1=config["bm25_k1"], b=config["bm25_b"])
    count = config["candidate_count"]
    names = ["dense", "bm25", "hybrid", "hybrid_bge"]
    predictions = {name: {"evidence_type": "measured", "run_id": "scifact-75-" + name, "rankings": []} for name in names}
    timings = {name: [] for name in names}
    candidates = []
    for index, query in enumerate(queries):
        tick = time.perf_counter()
        dense_scores = document_vectors @ query_vectors[index]
        dense = top_indices(dense_scores, count)
        dense_seconds = time.perf_counter() - tick
        tick = time.perf_counter()
        lexical_scores = lexical.get_scores(tokenize(query["query"]))
        bm25 = top_indices(lexical_scores, count)
        bm25_seconds = time.perf_counter() - tick
        tick = time.perf_counter()
        hybrid, hybrid_scores = fuse([dense, bm25], config["rrf_constant"], count)
        fusion_seconds = time.perf_counter() - tick
        candidates.append(hybrid)
        for name, ranking, scores in [
            ("dense", dense, [float(dense_scores[i]) for i in dense]),
            ("bm25", bm25, [float(lexical_scores[i]) for i in bm25]),
            ("hybrid", hybrid, hybrid_scores),
        ]:
            predictions[name]["rankings"].append({"query_id": query["query_id"], "retrieved_document_ids": [document_ids[i] for i in ranking], "scores": scores})
        timings["dense"].append(dense_seconds)
        timings["bm25"].append(bm25_seconds)
        timings["hybrid"].append(dense_seconds + bm25_seconds + fusion_seconds)
    for name in names[:-1]:
        write_json(args.output / f"{name}.predictions.json", predictions[name])
    print("Dense, BM25, and hybrid rankings complete; loading pinned BGE reranker", flush=True)

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    torch.set_num_threads(config["cpu_threads"])
    torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if config["reranker_device"] == "cuda" and not torch.cuda.is_available():
        raise ValueError("This configuration requires CUDA; use a separate CPU config and result path if needed")
    if config["reranker_dtype"] != "float32" or config["reranker_backend"] != "transformers":
        raise ValueError("Unsupported reranker precision or backend")
    local_path = args.reranker_path
    if local_path and Path(local_path).name != config["reranker_revision"]:
        raise ValueError("Local snapshot directory must match the pinned reranker revision")
    model_arguments = dict(
        revision=None if local_path else config["reranker_revision"],
        local_files_only=bool(local_path), trust_remote_code=False,
    )
    tokenizer = AutoTokenizer.from_pretrained(local_path or config["reranker_model"], **model_arguments)
    reranker = AutoModelForSequenceClassification.from_pretrained(
        local_path or config["reranker_model"],
        torch_dtype=torch.float32, **model_arguments,
    ).to(config["reranker_device"])
    reranker.eval()
    for index, query in enumerate(queries):
        ranking = candidates[index]
        tick = time.perf_counter()
        scores = predict_pairs(reranker, tokenizer, [(query["query"], texts[document]) for document in ranking], config)
        order = top_indices(scores, count)
        predictions["hybrid_bge"]["rankings"].append({
            "query_id": query["query_id"],
            "retrieved_document_ids": [document_ids[ranking[i]] for i in order],
            "scores": [float(scores[i]) for i in order],
        })
        timings["hybrid_bge"].append(timings["hybrid"][index] + time.perf_counter() - tick)
        if index == 0 or (index + 1) % 5 == 0:
            print(f"BGE reranked {index + 1}/{len(queries)} claims", flush=True)
    write_json(args.output / "hybrid_bge.predictions.json", predictions["hybrid_bge"])

    # Judgments are used only here, after every ranking has been computed.
    all_rows, summary, recalls = [], [], {}
    for name in names:
        rows = score(queries, predictions[name], config["k"])
        all_rows.extend(rows)
        recalls[name] = [row["relevant_retrieved"] / row["relevant_count"] for row in rows]
        summary.append({
            "run": name, "queries": len(rows), "corpus_documents": len(corpus), "k": config["k"],
            "macro_recall_at_k": fmean(recalls[name]), "hit_rate_at_k": fmean(row["hit_at_k"] for row in rows),
            "mean_ranking_seconds": fmean(timings[name]),
        })
    for filename, rows, fields in [("per_query.csv", all_rows, FIELDS), ("summary.csv", summary, list(summary[0]))]:
        with (args.output / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    funnel = []
    for index, query in enumerate(queries):
        relevant = set(query["relevant_document_ids"])
        candidate_documents = {document_ids[i] for i in candidates[index]}
        funnel.append({"query_id": query["query_id"], "relevant_count": len(relevant), "relevant_in_hybrid_candidates": len(relevant & candidate_documents), "candidate_document_ids": [document_ids[i] for i in candidates[index]]})
    write_json(args.output / "candidate_coverage.json", funnel)
    delta = paired_bootstrap(recalls["dense"], recalls["hybrid_bge"], config["bootstrap_seed"], config["bootstrap_resamples"])
    metadata = {
        "evidence_type": "measured", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_manifest_sha256": sha256(args.dataset / "manifest.json"),
        "runner_sha256": sha256(Path(__file__)), "scorer_sha256": sha256(ROOT / "score.py"),
        "config_sha256": sha256(args.config), "config": config,
        "runtime": {"python": platform.python_version(), "platform": platform.platform(), "ollama_version": ollama_version,
                    "container_image": os.environ.get("EVAL_CONTAINER_IMAGE"), "embedding_placement_bytes": placement,
                    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                    "packages": {name: importlib.metadata.version(name) for name in ["numpy", "torch", "transformers", "rank-bm25", "huggingface-hub", "tokenizers", "safetensors"]}},
        "embedding_model": {"name": current["name"], "digest": current["digest"], "details": current.get("details"), "model_info": model_info.get("model_info"), "dimensions": int(document_vectors.shape[1])},
        "embedding_cache": {"documents_reused": document_cached, "queries_reused": query_cached},
        "embedding_phase_seconds": embedding_seconds, "total_seconds": time.perf_counter() - started,
        "paired_bootstrap_hybrid_bge_minus_dense": delta,
        "metric_unit": "distinct abstract/document; macro recall@5; positive published qrels; unjudged documents treated as nonrelevant",
        "timing_scope": "Ranking only; excludes embedding, indexing, model loading, answer generation, OCR, UI, and network setup; not an end-to-end latency benchmark",
        "scope": "75-claim fixed sample of official SciFact test; full corpus; standalone retrieval harness, not an OpenWebUI end-to-end evaluation",
    }
    write_json(args.output / "metadata.json", metadata)
    for result in summary:
        print(f"{result['run']}: recall@5={result['macro_recall_at_k']:.6f}, hit@5={result['hit_rate_at_k']:.6f}", flush=True)
    print("COMPLETE: measured rankings, per-query scores, configuration, and provenance saved", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "public" / "scifact")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "scifact")
    parser.add_argument("--config", type=Path, default=ROOT / "public-config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "scifact-75")
    parser.add_argument("--ollama-url", default=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    parser.add_argument("--reranker-path", help="Optional local snapshot directory named with the pinned model revision")
    run(parser.parse_args())

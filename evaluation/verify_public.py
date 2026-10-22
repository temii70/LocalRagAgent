#!/usr/bin/env python3
"""Independently recompute public retrieval scores without models or network access."""

import argparse
import csv
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNS = ["dense", "bm25", "hybrid", "hybrid_bge"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(dataset, results):
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    metadata = json.loads((results / "metadata.json").read_text(encoding="utf-8"))
    queries = json.loads((dataset / "queries.json").read_text(encoding="utf-8"))
    require(digest(dataset / "queries.json") == manifest["queries_sha256"], "Query checksum mismatch")
    require(digest(dataset / "qrels.tsv") == manifest["qrels_sha256"], "Qrels checksum mismatch")
    require(digest(dataset / "manifest.json") == metadata["dataset_manifest_sha256"], "Dataset manifest mismatch")
    for filename, field in [("benchmark.py", "runner_sha256"), ("score.py", "scorer_sha256"), ("public-config.json", "config_sha256")]:
        require(digest(ROOT / filename) == metadata[field], "Run source/config changed: " + filename)
    config = json.loads((ROOT / "public-config.json").read_text(encoding="utf-8"))
    require(config == metadata["config"], "Recorded configuration differs")
    labels = {query["query_id"]: set(query["relevant_document_ids"]) for query in queries}
    require(len(labels) == len(queries) == manifest["selected_queries"], "Invalid query IDs/count")
    require(list(labels) == manifest["query_ids"], "Query order differs from frozen selection")
    require(all(labels.values()), "Empty relevance labels")
    with (dataset / "qrels.tsv").open(newline="") as handle:
        qrels = list(csv.DictReader(handle, delimiter="\t"))
    require({(row["query-id"], row["corpus-id"]) for row in qrels if int(row["score"]) > 0}
            == {(query_id, document) for query_id, documents in labels.items() for document in documents}, "JSON and TSV relevance labels disagree")

    with (results / "per_query.csv").open(newline="") as handle:
        per_query = list(csv.DictReader(handle))
    indexed_rows = {(row["run_id"], row["query_id"]): row for row in per_query}
    require(len(indexed_rows) == len(per_query) == len(queries) * len(RUNS), "Missing or duplicated result rows")
    with (results / "summary.csv").open(newline="") as handle:
        summary_rows = list(csv.DictReader(handle))
    summaries = {row["run"]: row for row in summary_rows}
    require(len(summary_rows) == len(RUNS) and set(summaries) == set(RUNS), "Invalid summary runs")
    rankings, exact_recalls = {}, {}
    k = config["k"]
    for name in RUNS:
        prediction = json.loads((results / f"{name}.predictions.json").read_text(encoding="utf-8"))
        require(prediction["evidence_type"] == "measured", "Unexpected evidence label")
        require([row["query_id"] for row in prediction["rankings"]] == list(labels), "Ranking query IDs changed")
        rankings[name], values, hits = {}, [], []
        for ranking in prediction["rankings"]:
            query_id = ranking["query_id"]
            documents = ranking["retrieved_document_ids"]
            require(len(documents) == len(set(documents)) == config["candidate_count"], "Invalid document ranking")
            scores = ranking["scores"]
            require(len(scores) == len(documents) and all(math.isfinite(s) for s in scores), "Invalid ranking scores")
            require(all(a >= b for a, b in zip(scores, scores[1:])), "Scores not descending")
            top = list(dict.fromkeys(documents))[:k]
            found = len(set(top) & labels[query_id])
            recall = Fraction(found, len(labels[query_id]))
            values.append(recall)
            hits.append(int(found > 0))
            row = indexed_rows[(prediction["run_id"], query_id)]
            require(row["evidence_type"] == "measured" and int(row["k"]) == k, "Per-query provenance mismatch")
            require(row["retrieved_document_ids"].split("|") == top, "Per-query ranking mismatch")
            require(set(row["relevant_document_ids"].split("|")) == labels[query_id], "Per-query labels mismatch")
            require(int(row["relevant_count"]) == len(labels[query_id]) and int(row["relevant_retrieved"]) == found, "Relevant counts mismatch")
            require(row["recall_at_k"] == f"{float(recall):.6f}" and int(row["hit_at_k"]) == hits[-1], "Per-query score mismatch")
            rankings[name][query_id] = documents
        exact_recalls[name] = values
        summary = summaries[name]
        require(int(summary["queries"]) == len(queries) and int(summary["k"]) == k, "Summary sample size mismatch")
        require(int(summary["corpus_documents"]) == manifest["corpus_documents"], "Corpus count mismatch")
        require(math.isclose(float(summary["macro_recall_at_k"]), float(sum(values) / len(values)), abs_tol=1e-12), "Macro recall mismatch")
        require(math.isclose(float(summary["hit_rate_at_k"]), sum(hits) / len(hits), abs_tol=1e-12), "Hit rate mismatch")
        print(f"VERIFIED {name}: recall@{k}={float(sum(values) / len(values)):.6f}, hit@{k}={sum(hits) / len(hits):.6f}")
    funnel = json.loads((results / "candidate_coverage.json").read_text(encoding="utf-8"))
    require([row["query_id"] for row in funnel] == list(labels), "Candidate coverage query mismatch")
    for row in funnel:
        query_id = row["query_id"]
        require(row["candidate_document_ids"] == rankings["hybrid"][query_id], "Candidate coverage ranking mismatch")
        require(set(rankings["hybrid"][query_id]) == set(rankings["hybrid_bge"][query_id]), "Reranking changed candidate membership")
        require(row["relevant_in_hybrid_candidates"] == len(labels[query_id] & set(row["candidate_document_ids"])), "Candidate relevance mismatch")
    expected_delta = float(sum(b - a for a, b in zip(exact_recalls["dense"], exact_recalls["hybrid_bge"])) / len(queries))
    require(math.isclose(metadata["paired_bootstrap_hybrid_bge_minus_dense"]["mean_delta"], expected_delta, abs_tol=1e-12), "Paired delta mismatch")
    print(f"PASS: independently checked {len(per_query)} per-query scores, all summaries, candidate membership, and source/config checksums")
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "public" / "scifact")
    parser.add_argument("--results", type=Path, default=ROOT / "results" / "scifact-75")
    args = parser.parse_args()
    verify(args.dataset, args.results)

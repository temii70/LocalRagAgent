#!/usr/bin/env python3
"""Score supplied document rankings; never performs retrieval or network calls."""

import argparse
import csv
import json
import re
from pathlib import Path
from statistics import fmean


FIELDS = [
    "evidence_type", "run_id", "query_id", "k", "relevant_document_ids",
    "retrieved_document_ids", "relevant_count", "relevant_retrieved",
    "recall_at_k", "hit_at_k",
]


def identifier(value, field):
    """Use portable IDs that cannot introduce CSV formulas or list separators."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", value):
        raise ValueError(f"{field} must be an ID using letters, digits, '.', '_', ':', or '-'")
    return value


def document_ids(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list of document IDs")
    return [identifier(item, field) for item in value]


def score(queries, predictions, k=5):
    """Return one row per query, de-duplicating document rankings before cutoff."""
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty list")
    if not isinstance(predictions, dict):
        raise ValueError("predictions must be an object")
    evidence = predictions.get("evidence_type")
    if evidence not in ("illustrative", "measured"):
        raise ValueError("evidence_type must be 'illustrative' or 'measured'")
    run_id = identifier(predictions.get("run_id"), "run_id")

    judgments = {}
    for query in queries:
        if not isinstance(query, dict):
            raise ValueError("each query must be an object")
        query_id = identifier(query.get("query_id"), "query_id")
        if query_id in judgments:
            raise ValueError("duplicate query_id in queries")
        if not isinstance(query.get("query"), str) or not query["query"].strip():
            raise ValueError("each query needs non-empty query text")
        relevant = document_ids(query.get("relevant_document_ids"), "relevant_document_ids")
        if not relevant or len(relevant) != len(set(relevant)):
            raise ValueError("relevance labels must be non-empty and contain no duplicates")
        judgments[query_id] = relevant

    rankings = predictions.get("rankings")
    if not isinstance(rankings, list):
        raise ValueError("rankings must be a list")
    retrieved = {}
    for ranking in rankings:
        if not isinstance(ranking, dict):
            raise ValueError("each ranking must be an object")
        query_id = identifier(ranking.get("query_id"), "query_id")
        if query_id in retrieved:
            raise ValueError("duplicate query_id in rankings")
        docs = document_ids(ranking.get("retrieved_document_ids"), "retrieved_document_ids")
        retrieved[query_id] = list(dict.fromkeys(docs))[:k]
    if set(retrieved) != set(judgments):
        raise ValueError("rankings must contain exactly the labeled query IDs, including empty results")

    rows = []
    for query_id, relevant in judgments.items():
        top = retrieved[query_id]
        found = len(set(top).intersection(relevant))
        rows.append({
            "evidence_type": evidence,
            "run_id": run_id,
            "query_id": query_id,
            "k": k,
            "relevant_document_ids": "|".join(relevant),
            "retrieved_document_ids": "|".join(top),
            "relevant_count": len(relevant),
            "relevant_retrieved": found,
            "recall_at_k": f"{found / len(relevant):.6f}",
            "hit_at_k": int(found > 0),
        })
    return rows


def positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("k must be a positive integer")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--k", type=positive_integer, default=5)
    args = parser.parse_args()

    try:
        queries = json.loads(args.queries.read_text(encoding="utf-8-sig"))
        predictions = json.loads(args.predictions.read_text(encoding="utf-8-sig"))
        rows = score(queries, predictions, args.k)
        if args.output.suffix.lower() != ".csv":
            raise ValueError("output must have a .csv extension")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects input fixtures and previous evaluation runs.
        with args.output.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    macro_recall = fmean(row["relevant_retrieved"] / row["relevant_count"] for row in rows)
    hit_rate = fmean(row["hit_at_k"] for row in rows)
    print(f"evidence_type={predictions['evidence_type']} run={predictions['run_id']} queries={len(rows)}")
    print(f"macro_recall@{args.k}={macro_recall:.6f} hit_rate@{args.k}={hit_rate:.6f}")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()

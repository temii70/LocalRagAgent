#!/usr/bin/env python3
"""Freeze a deterministic, labeled SciFact test subset from the BEIR archive."""

import argparse
import csv
import hashlib
import io
import json
import random
import urllib.request
import zipfile
from pathlib import Path


DATASET_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
DATASET_MD5 = "5f7d1de60b170fc8027bb7898e2efca1"
ROOT = Path(__file__).resolve().parent


def dump_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def prepare(cache, output, count=75, seed=42):
    if count < 1:
        raise ValueError("count must be positive")
    manifest_path = output / "manifest.json"
    existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    if existing and (existing["selected_queries"] != count or existing["selection"]["seed"] != seed):
        raise ValueError("Selection already frozen with different settings; use a new output folder")
    cache.mkdir(parents=True, exist_ok=True)
    archive_path = cache / "scifact.zip"
    if not archive_path.exists():
        print("Downloading public BEIR SciFact archive", flush=True)
        request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "LocalRagAgent-public-evaluation"})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
        if hashlib.md5(data).hexdigest() != DATASET_MD5:
            raise ValueError("Downloaded archive does not match the published BEIR checksum")
        archive_path.write_bytes(data)
    data = archive_path.read_bytes()
    if hashlib.md5(data).hexdigest() != DATASET_MD5:
        raise ValueError("Cached archive checksum mismatch")

    # Read only the named members; never extract arbitrary archive paths.
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = {}
        for filename in ["corpus.jsonl", "queries.jsonl", "qrels/test.tsv"]:
            member = "scifact/" + filename
            members[filename] = archive.read(member)
        corpus = [json.loads(line) for line in members["corpus.jsonl"].decode("utf-8").splitlines() if line]
        queries = {row["_id"]: row for row in (json.loads(line) for line in members["queries.jsonl"].decode("utf-8").splitlines() if line)}
        qrels = {}
        for row in csv.DictReader(io.StringIO(members["qrels/test.tsv"].decode("utf-8")), delimiter="\t"):
            if int(row["score"]) > 0:
                qrels.setdefault(row["query-id"], []).append(row["corpus-id"])

    document_ids = {document["_id"] for document in corpus}
    assert len(document_ids) == len(corpus) == 5183
    if count > len(qrels):
        raise ValueError("count exceeds the number of labeled test claims")
    selected = sorted(random.Random(seed).sample(sorted(qrels, key=int), count), key=int)
    public_queries = []
    for query_id in selected:
        relevant = sorted(set(qrels[query_id]), key=int)
        assert set(relevant) <= document_ids
        public_queries.append({
            "query_id": query_id,
            "query": queries[query_id]["text"],
            "relevant_document_ids": relevant,
            "source_split": "BEIR SciFact test",
        })
    output.mkdir(parents=True, exist_ok=True)
    (cache / "corpus.jsonl").write_bytes(members["corpus.jsonl"])
    if existing:
        if hashlib.sha256(data).hexdigest() != existing["archive_sha256"]:
            raise ValueError("Archive differs from the frozen manifest")
        if public_queries != json.loads((output / "queries.json").read_text(encoding="utf-8")):
            raise ValueError("Frozen query selection differs from the source labels")
        for filename, field in [("queries.json", "queries_sha256"), ("qrels.tsv", "qrels_sha256")]:
            if hashlib.sha256((output / filename).read_bytes()).hexdigest() != existing[field]:
                raise ValueError("Frozen file changed: " + filename)
        print(f"Verified existing {count}-claim selection and cached corpus; public files unchanged", flush=True)
        return existing
    dump_json(output / "queries.json", public_queries)
    with (output / "qrels.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["query-id", "corpus-id", "score"])
        for query in public_queries:
            for doc_id in query["relevant_document_ids"]:
                writer.writerow([query["query_id"], doc_id, 1])
    manifest = {
        "dataset": "BEIR SciFact",
        "source_url": DATASET_URL,
        "archive_md5": DATASET_MD5,
        "archive_sha256": hashlib.sha256(data).hexdigest(),
        "member_sha256": {key: hashlib.sha256(value).hexdigest() for key, value in members.items()},
        "corpus_documents": len(corpus),
        "official_test_queries_with_positive_labels": len(qrels),
        "selected_queries": count,
        "selection": {"method": "random.Random(seed).sample over numerically sorted positive-qrel test IDs; output numerically sorted", "seed": seed},
        "query_ids": selected,
        "queries_sha256": hashlib.sha256((output / "queries.json").read_bytes()).hexdigest(),
        "qrels_sha256": hashlib.sha256((output / "qrels.tsv").read_bytes()).hexdigest(),
        "label_provenance": "Published BEIR SciFact test qrels; no model-generated relevance labels",
        "selection_note": "Frozen before retrieval; fixed configurations, no parameter search on this subset",
        "data_license": "CC-BY-SA-4.0 as identified by BEIR dataset cards; see ATTRIBUTION.md",
    }
    dump_json(output / "manifest.json", manifest)
    print(f"Frozen {count} labeled test claims against all {len(corpus)} abstracts", flush=True)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "scifact")
    parser.add_argument("--output", type=Path, default=ROOT / "public" / "scifact")
    parser.add_argument("--count", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    prepare(args.cache, args.output, args.count, args.seed)

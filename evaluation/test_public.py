"""Tests for ranking, paired uncertainty, and document-level scoring semantics."""

import unittest

import numpy as np

from benchmark import fuse, paired_bootstrap, tokenize, top_indices
from score import score


class RankingTests(unittest.TestCase):
    def test_fusion_rewards_agreement(self):
        ranking, values = fuse([[0, 1], [1, 2]])
        self.assertEqual(ranking, [1, 0, 2])
        self.assertAlmostEqual(values[0], 1 / 62 + 1 / 61)

    def test_fusion_does_not_double_count_duplicates(self):
        self.assertEqual(fuse([[0, 0, 1], [1]]), fuse([[0, 1], [1]]))

    def test_fusion_ties_follow_first_seen_order(self):
        self.assertEqual(fuse([[7], [3]])[0], [7, 3])

    def test_top_indices_cutoff_and_ties(self):
        self.assertEqual(top_indices([0.2, 0.8, 0.8, 0.1], 2), [1, 2])

    def test_nonfinite_scores_are_rejected(self):
        for values in [[1, np.nan], [np.inf, 1]]:
            with self.assertRaises(ValueError):
                top_indices(values, 2)

    def test_tokenization_is_explicit(self):
        self.assertEqual(tokenize("DNA-binding, 12.5%"), ["dna", "binding", "12", "5"])


class MetricTests(unittest.TestCase):
    def test_recall_and_hit_are_distinct(self):
        queries = [{"query_id": "q", "query": "A test question", "relevant_document_ids": ["a", "b"]}]
        predictions = {"evidence_type": "measured", "run_id": "unit-test", "rankings": [{"query_id": "q", "retrieved_document_ids": ["a", "a", "x", "b"]}]}
        row = score(queries, predictions, k=2)[0]
        self.assertEqual(row["recall_at_k"], "0.500000")
        self.assertEqual(row["hit_at_k"], 1)
        self.assertEqual(row["retrieved_document_ids"], "a|x")

    def test_empty_retrieval_is_zero_not_omitted(self):
        queries = [{"query_id": "q", "query": "A test question", "relevant_document_ids": ["a"]}]
        predictions = {"evidence_type": "measured", "run_id": "unit-test", "rankings": [{"query_id": "q", "retrieved_document_ids": []}]}
        row = score(queries, predictions)[0]
        self.assertEqual(row["recall_at_k"], "0.000000")
        self.assertEqual(row["hit_at_k"], 0)

    def test_missing_queries_are_not_silently_dropped(self):
        with self.assertRaises(ValueError):
            score([{"query_id": "q", "query": "A test", "relevant_document_ids": ["a"]}], {"evidence_type": "measured", "run_id": "unit-test", "rankings": []})

    def test_identical_runs_have_zero_paired_delta(self):
        result = paired_bootstrap([1, 0, 0.5], [1, 0, 0.5], 42, 100)
        self.assertEqual(result["mean_delta"], 0)
        self.assertEqual(result["percentile_95_ci"], [0, 0])

    def test_constant_improvement_has_exact_interval(self):
        result = paired_bootstrap([0, 0.5], [0.25, 0.75], 42, 100)
        self.assertEqual(result["mean_delta"], 0.25)
        self.assertEqual(result["percentile_95_ci"], [0.25, 0.25])

    def test_bootstrap_is_reproducible(self):
        self.assertEqual(paired_bootstrap([0, 1, 0], [1, 1, 0], 42, 100), paired_bootstrap([0, 1, 0], [1, 1, 0], 42, 100))


if __name__ == "__main__":
    unittest.main()

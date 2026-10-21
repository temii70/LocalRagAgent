# SciFact data attribution

The query text and relevance labels in [queries.json](queries.json) and [qrels.tsv](qrels.tsv) are a selected subset of the published **BEIR SciFact test split**. They are not authored or newly labeled by this repository.

SciFact was introduced in *Fact or Fiction: Verifying Scientific Claims* (EMNLP 2020) by David Wadden, Shanchuan Lin, Kyle Lo, Lucy Lu Wang, Madeleine van Zuylen, Arman Cohan, and Hannaneh Hajishirzi. Original project: [allenai/scifact](https://github.com/allenai/scifact).

BEIR provides the retrieval-format archive: [beir-cellar/beir](https://github.com/beir-cellar/beir). The [SciFact dataset card](https://huggingface.co/datasets/BeIR/scifact) and [qrels dataset card](https://huggingface.co/datasets/BeIR/scifact-qrels) identify the data license as **Creative Commons Attribution-ShareAlike 4.0 International** ([CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)). The redistributed query subset and relevance labels remain under that license, separately from the repository's Apache-2.0 code license.

Modifications: selection of 75 existing test claim IDs with seed 42, conversion of the selected query records to the repository's JSON schema, and extraction of their positive relevance judgments into a smaller TSV. Claim wording and document IDs are unchanged. The full corpus is downloaded into ignored local cache rather than committed.

The [manifest](manifest.json) records the source URL, published archive MD5, archive/member SHA-256 checksums, selected IDs, and selection settings. Supporting and refuting evidence abstracts both count as relevant under the source judgments. Retrieval relevance does not assert that a scientific claim is true.

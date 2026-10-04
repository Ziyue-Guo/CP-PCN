# Reproducibility and maintenance notes

## What this update verifies

The October 2026 maintenance checks documentation against the paper and source, audits bundled point files/split IDs, adds a standard-library checker and tests, and syntax-checks historical Python files. Original model/data-generation/training scripts, sample clouds, split JSON files and LICENSE retain their contents from `fc2b042`.

It does not train CP-PCN, load a model checkpoint, verify prediction equivalence or reproduce any scientific result. Helper tests use synthetic fixtures; data-format success does not establish geometric truth.

## Paper settings versus repository defaults

| Item | Paper description | Released defaults/behavior |
| --- | --- | --- |
| Input scales | 8192 / 4096 / 2048 | 2048 / 512 / 256 in training |
| Decoder scales | 2048 / 4096 / 8192 | 128 / 256 / 2048 in training |
| Latent representation | 5760 dimensions | 1920 input to generator's first FC layer |
| Batch / epochs | 8 / up to 200 | 2 / 151 |
| Completion / adversarial weight | 0.9 / 0.1 | 0.95 / 0.05 |
| Dataset | 4,000 simulated populations across four stages | 80 example point-cloud pairs |
| Validation | Paper describes an 80:20 split | Bundled 16 validation IDs are also in the 72 training IDs |

The paper's simulated populations are not 4,000 independently measured complete field canopies. The bundled manifest overlap is a fact about **these example files** and does not by itself establish the membership or validity of the unpublished experimental splits.

The source also monitors the first shuffled test batch and selects a best checkpoint using training loss. Recover the actual study configurations, split provenance and checkpoint selection protocol before claiming an exact reproduction. Do not silently equate source defaults with publication settings.

## Chamfer-distance conventions

Let d1 and d2 denote the two directional mean nearest-neighbor **squared Euclidean distances** for the same cloud pair. The square root is commented out in `utils.array2samples_distance`.

- Training `PointLoss`: `100 × (d1 + d2) / 2`.
- `PointLoss_test`: returns `(d1 + d2, d1, d2)`.
- For identical arrays under these definitions, the training scalar is **50 times** the test symmetric scalar.

Coordinate units, normalization, squared versus unsquared distance and reporting factors all matter. The paper labels CD values in centimeters while its equation uses squared norms. A multiplier alone is not a documented conversion to centimeters. Recover the original evaluation convention before comparing raw code losses with published CD values; this maintenance does not invent a conversion.

The README uses the model-comparison series (paper Fig. 6B): 3.35 / 3.46 / 4.32 / 4.51 cm. A different evaluation series appears elsewhere in the paper. It does not combine those series or recompute a new overall benchmark.

## Scope of claims

- Rice experiments retrain the model **from scratch on rice data** using the same data-generation workflow; no zero-shot rapeseed-to-rice checkpoint transfer is established.
- Reported SEI–yield associations are downstream regression evidence, not direct validation of every reconstructed organ or automatically an independent prediction benchmark.
- Predicted points are estimates of occluded structure, not direct measurements of hidden geometry.
- Current code consumes/predicts XYZ. It does not infer RGB, normals, organ labels or a complete yield/photosynthesis pipeline.
- Timing/hardware in the paper describes that setup, not a benchmark of this maintained checkout.

## Known technical blockers and next steps

See [USAGE.md](USAGE.md) for ignored flags, hardcoded paths/CUDA, inference shape conflicts, loader mismatches, per-device batch constraints and incomplete ablation scripts.

A useful next development phase is to recover a matching checkpoint/environment, parameterize paths, reconcile the paired-data protocol, fix device/shape handling and add genuine forward-pass/checkpoint tests. Restore trustworthy independent splits and metric reporting before new benchmarks. Model changes should retain a comparison to a known historical implementation where possible.

## Citation year

Use **2026, Plant Communications 7(3), 101675**. The DOI contains 2025, and the supplied PDF retains stale in-press text. The final volume/issue metadata is confirmed by [Crossref](https://api.crossref.org/works/10.1016/j.xplc.2025.101675) and the publisher. No exact day/month is needed for this citation.

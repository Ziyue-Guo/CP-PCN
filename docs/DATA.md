# Dataset format and availability

## Included resources

The repository contains examples, not the complete 4,000-sample simulated dataset described in the paper. Its availability statement links this repository; no external full-dataset archive or pretrained-checkpoint link was identified in the paper or repository resources reviewed on 2026-10-04.

```text
dataset/mydata/
├── synsetoffset2category.txt        # Rape    02691156
├── train_test_split/
│   ├── shuffled_train_file_list.json
│   ├── shuffled_val_file_list.json
│   └── shuffled_test_file_list.json
└── 02691156/
    ├── points/<sample>.pts          # Visible/input point cloud
    └── point_fake/<sample>.pts      # Missing-region target
```

The category directory is a legacy identifier. Use the supplied mapping, rather than inferring a crop class from the numeric directory name.

| Checked property | Bundled examples |
| --- | --- |
| Input/target files | 80 matching pairs |
| Input rows per file | 2,908–5,129 |
| Target rows per file | 2,365–7,038 |
| Coordinates | Three finite XYZ columns |
| Train / validation / test entries | 72 / 16 / 8 |
| Train–validation overlap | **16 IDs: validation is a subset of training** |
| Test overlap with either other list | 0 IDs |

These are checks of the **bundled example manifests**, not a reconstruction of the split used in the published experiments. The historical files are preserved. For a new experiment, create independent splits with provenance and grouping by source plant/population as appropriate. Do not silently rewrite these manifests and describe the new split as the original study.

## Loader contract

The paired files share a basename and coordinate frame; their row counts can differ and there is no required rowwise correspondence.

- `.pts`: headerless, whitespace-separated **X Y Z**, exactly three numbers per row. No count header, UTF-8 BOM, RGB or normals. Use ASCII decimal/scientific notation.
- Dataset mode requires at least two rows per file: a single-row `numpy.loadtxt` result is not a two-dimensional point array. A single-file format check can accept one row and is not a loader-readiness check. Set `--min-input-points 2048 --min-target-points 2048` when checking against the training defaults.
- Coordinates are loaded with `numpy.loadtxt(...).astype(float32)`; values must remain finite after conversion.
- The current loader accepts no color/normal channels and does not preserve them in model output.
- Default normalization is disabled. Enabling the existing option normalizes the two parts separately, which changes their shared coordinate relationship.
- Training samples input and target independently using farthest-point sampling: default input `npoints=2048`, target `crop_point_num=2048`. Insufficient rows can lead to repeated indices; plan point counts deliberately.
- Keep sidecar files outside the `points/` directory: the historical loader enumerates its filenames and strips four trailing characters.

A split JSON is an array of identifiers, without `.pts`:

```json
["mydata/02691156/moved_IMG_4816_down"]
```

The loader uses the third slash-separated component as the sample ID, ignoring the category/prefix when constructing its ID sets. Avoid basename collisions across categories. The checker is stricter: it validates the full layout, pair references, safe paths and split independence.

## Read-only checks

Python 3.11+ is sufficient; no packages, CUDA, PyTorch or Open3D are needed.

```bash
python tools/check_dataset.py --cloud dataset/mydata/02691156/points/moved_IMG_4580_frames_down.pts
python tools/check_dataset.py --root dataset/mydata
python tools/check_dataset.py --help
```

The full bundled-data check is expected to report the known 16-ID train/validation overlap and exit nonzero. A passing single-file check means valid coordinate format, not ground-truth accuracy, paired geometric consistency or an independent test design.

The checker does not resample, normalize, alter split membership or write over source data. Its synthetic unit tests validate the checker, not the paper.

## Other examples and weights

`test_one/` contains 51 existing comma-separated XYZ files, including files with a `.txt` extension. Extension alone does not establish the delimiter. The legacy `Test_csv.py` reads CSV data and has separate point-count/padding assumptions described in [USAGE.md](USAGE.md).

`Checkpoint/` contains historical logs. `Trained_Model/1` is a placeholder, **not a checkpoint**. No `.pt`, `.pth` or `.ckpt` model was found in the inspected repository, and its GitHub release list was empty. Do not rename the placeholder or a log file as a model. A future weight release needs matching architecture, training configuration, preprocessing and provenance.

## Generating new data

The paper reconstructs individual plants, assembles simulated populations and annotates visibility from multiple directions. `create_dataset.py` is a local-path template for mesh arrangement, point-cloud handling and ray classification. It outputs PLY files, not a complete loader-ready `.pts`/JSON dataset.

In that script, `np.any(counts < 1)` routes points with an unblocked direction to a file named `_covered.ply`; the other branch uses `_nocovered.ply`. Those names should not be treated as a reliable semantic definition. Inspect the actual visibility condition, geometry, coordinate units and examples before assigning input and missing-target roles. Preserve RGB/normals separately if needed downstream; the network consumes XYZ only.

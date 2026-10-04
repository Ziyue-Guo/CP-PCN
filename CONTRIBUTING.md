# Contributing

Use [GitHub Issues](https://github.com/Ziyue-Guo/CP-PCN/issues) for bug reports and resource questions. Include the commit, OS, Python/dependency versions, command and traceback. For model issues, include GPU and checkpoint provenance.

Preserve input data and historical evidence. Do not rewrite sample splits solely to make checks pass. Describe changes to visibility labels, coordinate normalization, FPS, point counts, loss definitions and checkpoint handling because they can change scientific results. Retain the existing MIT license and upstream attribution.

## Lightweight checks

Python 3.11+ and its standard library are sufficient:

```bash
python -m unittest discover -s tests -v
python tools/check_dataset.py --cloud dataset/mydata/02691156/points/moved_IMG_4580_frames_down.pts
```

The full example audit `python tools/check_dataset.py --root dataset/mydata` intentionally reports the historical train/validation overlap. CI verifies the checker on synthetic fixtures and syntax-checks tracked Python files without executing model workflows.

For model changes, add actual shape/device/forward-pass and checkpoint evidence in a tested environment. A green checker test suite is not a successful CP-PCN training or paper reproduction. Keep large datasets, checkpoints, experiment outputs and local credentials out of routine source commits.

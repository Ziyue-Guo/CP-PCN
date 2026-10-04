#!/usr/bin/env python3
"""Read-only CP-PCN data audit using the Python standard library.

--root audits every mapped cloud pair and all three splits, including leakage.
Dataset mode requires at least two rows per cloud for the legacy np.loadtxt shape.
--cloud checks one headerless XYZ file only; it does not validate a dataset split.
Exit codes: 0 = pass, 1 = data issues, 2 = invalid arguments or unavailable input.
No point clouds, mappings, or split files are changed by this tool.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SPLITS = ("train", "val", "test")
XYZ_LITERAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", re.ASCII)


@dataclass
class Audit:
    stats: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def check_cloud(path: Path, min_points: int = 1) -> Audit:
    """Check headerless ASCII numeric XYZ rows; never normalize or rewrite input."""
    result = Audit(stats={"points": 0})
    try:
        with path.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                fields = line.split()
                if not fields:
                    continue
                result.stats["points"] += 1
                if len(fields) != 3:
                    result.issues.append(f"{path}: line {number}: expected exactly 3 XYZ columns, got {len(fields)}")
                    continue
                if not all(XYZ_LITERAL.fullmatch(value) for value in fields):
                    result.issues.append(f"{path}: line {number}: XYZ values must be finite ASCII numeric literals (decimal/scientific notation; no header or BOM)")
                    continue
                values = [float(value) for value in fields]
                if not all(math.isfinite(value) for value in values):
                    result.issues.append(f"{path}: line {number}: XYZ values must be finite")
                elif any(abs(value) > 3.4028234663852886e38 for value in values):
                    result.issues.append(f"{path}: line {number}: coordinate exceeds the legacy loader's finite float32 range")
    except (OSError, UnicodeError) as exc:
        result.issues.append(f"Cannot read cloud {path}: {exc}")
    if result.stats["points"] < min_points:
        result.issues.append(f"{path}: {result.stats['points']} point rows; at least {min_points} required")
    return result


def _safe_component(value: str) -> bool:
    # Restrict components before resolution, including Windows drive/ADS aliases.
    return bool(value) and value not in {".", ".."} and not any(
        char in '/\\:*?"<>|' or ord(char) < 32 or char == "\ufeff" or char.isspace() for char in value
    ) and not value.endswith((".", " "))


def _inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Unsafe path outside dataset root: {path}") from exc
    return resolved


def _mapping(root: Path, result: Audit) -> dict[str, str]:
    mapping: dict[str, str] = {}
    names: set[str] = set()
    directories: set[str] = set()
    path = root / "synsetoffset2category.txt"
    try:
        path = _inside(root, path)
        content = path.read_text(encoding="utf-8")
        if content.startswith("\ufeff"):
            raise ValueError("Category mapping must not contain a UTF-8 BOM; the legacy loader does not strip it")
        lines = content.splitlines()
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        result.issues.append(f"Cannot read category mapping: {exc}")
        return mapping
    for number, line in enumerate(lines, start=1):
        fields = line.split()
        if len(fields) != 2 or not all(_safe_component(value) for value in fields):
            result.issues.append(f"Category mapping line {number}: expected a category name and a safe directory name")
            continue
        name, directory = fields
        try:
            directory_key = _inside(root, root / directory).relative_to(root).as_posix().casefold()
        except (ValueError, OSError, RuntimeError) as exc:
            result.issues.append(str(exc))
            continue
        if name.casefold() in names or directory_key in directories:
            result.issues.append(f"Category mapping line {number}: duplicate category name or directory alias")
            continue
        names.add(name.casefold())
        directories.add(directory_key)
        mapping[directory] = name
    if not mapping:
        result.issues.append("Category mapping contains no valid categories")
    return mapping


def _inventory(root: Path, category: str, folder: str, result: Audit) -> dict[str, Path]:
    files: dict[str, Path] = {}
    seen: set[str] = set()
    canonical_seen: set[str] = set()
    try:
        directory = _inside(root, root / category / folder)
        if not directory.is_dir():
            raise ValueError(f"Missing cloud directory: {category}/{folder}")
        entries = sorted(directory.iterdir())
    except (ValueError, OSError, RuntimeError) as exc:
        result.issues.append(str(exc))
        return files
    for entry in entries:
        if entry.suffix != ".pts" or not _safe_component(entry.name) or Path(entry.stem).suffix:
            result.issues.append(f"Unexpected entry in {category}/{folder}: {entry.name!r}; expected a suffix-free ID followed by .pts")
            continue
        try:
            candidate = _inside(root, entry)
            if not candidate.is_file():
                raise ValueError(f"Not a point-cloud file: {entry}")
        except (ValueError, OSError, RuntimeError) as exc:
            result.issues.append(str(exc))
            continue
        canonical_key = candidate.relative_to(root).as_posix().casefold()
        if entry.stem.casefold() in seen or canonical_key in canonical_seen:
            result.issues.append(f"Duplicate cloud ID or file alias: {category}/{folder}/{entry.name}")
        seen.add(entry.stem.casefold())
        canonical_seen.add(canonical_key)
        files[entry.stem] = candidate
    return files


def _read_split(root: Path, split: str, categories: dict[str, str], pairs: set[tuple[str, str]], result: Audit) -> set[str]:
    path = root / "train_test_split" / f"shuffled_{split}_file_list.json"
    try:
        path = _inside(root, path)
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        result.issues.append(f"Cannot read {split} split JSON: {exc}")
        result.stats["split_entries"][split] = 0
        return set()
    if not isinstance(entries, list):
        result.issues.append(f"{split} split JSON must be a list of strings")
        result.stats["split_entries"][split] = 0
        return set()
    result.stats["split_entries"][split] = len(entries)
    ids: set[str] = set()
    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, str):
            result.issues.append(f"{split} entry {number}: split ID must be a string")
            continue
        parts = entry.split("/")
        if len(parts) != 3 or not all(_safe_component(part) for part in parts) or Path(parts[-1]).suffix:
            result.issues.append(f"{split} entry {number}: unsafe or malformed split ID {entry!r}; expected prefix/category/stem without a suffix")
            continue
        _, category, stem = parts
        # The historical loader uses d.split('/')[2] globally and ignores category.
        key = stem.casefold()
        if key in ids:
            result.issues.append(f"{split} entry {number}: duplicate split ID or prefix/category alias for {stem!r}")
        ids.add(key)
        if category not in categories:
            result.issues.append(f"{split} entry {number}: unknown category {category!r}")
        elif (category, stem) not in pairs:
            result.issues.append(f"{split} entry {number}: no complete, exactly named cloud pair for {category}/{stem}")
    return ids


def check_dataset(root: Path, min_input_points: int = 1, min_target_points: int = 1) -> Audit:
    root = root.resolve()
    result = Audit(stats={"categories": 0, "input_files": 0, "target_files": 0, "pairs": 0,
                          "input_point_range": None, "target_point_range": None,
                          "split_entries": {}, "split_overlap": {}})
    categories = _mapping(root, result)
    result.stats["categories"] = len(categories)
    pairs: set[tuple[str, str]] = set()
    stem_categories: dict[str, str] = {}
    input_counts: list[int] = []
    target_counts: list[int] = []
    for category in categories:
        inputs = _inventory(root, category, "points", result)
        targets = _inventory(root, category, "point_fake", result)
        result.stats["input_files"] += len(inputs)
        result.stats["target_files"] += len(targets)
        for stem in sorted(inputs.keys() | targets.keys()):
            if stem not in inputs or stem not in targets:
                missing = "points" if stem not in inputs else "point_fake"
                result.issues.append(f"Unpaired cloud {category}/{stem}: missing {missing}/{stem}.pts")
            else:
                pairs.add((category, stem))
            key = stem.casefold()
            if key in stem_categories and stem_categories[key] != category:
                result.issues.append(f"Ambiguous ID {stem!r} in categories {stem_categories[key]} and {category}; the legacy loader matches IDs globally")
            stem_categories[key] = category
        # np.loadtxt returns a 1-D array for one XYZ row; the legacy loader
        # indexes a 2-D matrix, so dataset inputs and targets require two rows.
        for files, minimum, counts in ((inputs, max(2, min_input_points), input_counts),
                                       (targets, max(2, min_target_points), target_counts)):
            for path in files.values():
                cloud = check_cloud(path, minimum)
                result.issues.extend(cloud.issues)
                counts.append(cloud.stats["points"])
    result.stats["pairs"] = len(pairs)
    if not pairs:
        result.issues.append("Dataset has no complete cloud pairs")
    for key, counts in (("input_point_range", input_counts), ("target_point_range", target_counts)):
        if counts:
            result.stats[key] = [min(counts), max(counts)]
    split_ids = {split: _read_split(root, split, categories, pairs, result) for split in SPLITS}
    for left, right in itertools.combinations(SPLITS, 2):
        overlap = sorted(split_ids[left] & split_ids[right])
        result.stats["split_overlap"][f"{left}/{right}"] = len(overlap)
        if overlap:
            examples = ", ".join(overlap[:5])
            result.issues.append(f"Split leakage: {left}/{right} overlap on {len(overlap)} ID(s), including {examples}")
    unassigned = {stem.casefold() for _, stem in pairs} - set().union(*split_ids.values())
    result.stats["unassigned_pairs"] = len(unassigned)
    if unassigned:
        result.issues.append(f"{len(unassigned)} paired cloud ID(s) are absent from all splits: " + ", ".join(sorted(unassigned)[:5]))
    return result


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("minimum point count must be at least 1")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--root", type=Path, help="Dataset root containing the mapping, category directories, and train_test_split")
    source.add_argument("--cloud", type=Path, help="Check only one headerless whitespace-delimited XYZ file")
    parser.add_argument("--min-input-points", type=_positive, default=1, help="Minimum input rows: dataset mode always requires at least 2; --cloud allows 1 (default)")
    parser.add_argument("--min-target-points", type=_positive, default=1, help="Minimum target rows: dataset mode always requires at least 2 even if this option is 1")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable audit report")
    args = parser.parse_args(argv)
    if args.cloud and args.min_target_points != 1:
        parser.error("--min-target-points applies only to --root")
    path = args.root if args.root is not None else args.cloud
    if (args.root is not None and not path.is_dir()) or (args.cloud is not None and not path.is_file()):
        print(f"ERROR: input does not exist or has the wrong file/directory type: {path}", file=sys.stderr)
        return 2
    result = check_dataset(path, args.min_input_points, args.min_target_points) if args.root is not None else check_cloud(path, args.min_input_points)
    mode = "dataset" if args.root is not None else "cloud-format-only"
    if args.json:
        print(json.dumps({"mode": mode, "status": "PASS" if result.ok else "FAIL", "stats": result.stats, "issues": result.issues}, indent=2))
    else:
        for issue in result.issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        print(f"{'PASS' if result.ok else 'FAIL'} ({mode}): {len(result.issues)} issue(s)")
        print(json.dumps(result.stats, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())

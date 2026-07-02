#!/usr/bin/env python3
"""
SPWIN Atlas Gold Record Builder Reference Validator v1.0

Purpose
-------
Validate Gold Record Builder output against reviewed reference Gold records.

This script is used to certify that Gold Record Builder v1.0 can reproduce a
reference batch from raw SGOdds-style text fixtures.

Expected layout
---------------
raw fixtures:
    validation/gold_builder_v1/raw/*.txt

expected reviewed Gold records:
    validation/gold_builder_v1/expected/*.json

actual generated output:
    validation/gold_builder_v1/generated/*.json

Usage
-----
1. Build generated records:

    python tools/gold_record_builder.py \
      --input-dir validation/gold_builder_v1/raw \
      --out validation/gold_builder_v1/generated \
      --force

2. Compare generated vs expected:

    python tools/validate_gold_builder_reference.py \
      --expected validation/gold_builder_v1/expected \
      --generated validation/gold_builder_v1/generated

Exit codes
----------
0 = validation pass
1 = validation fail
2 = missing files / invalid input
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

IGNORED_TOP_LEVEL_FIELDS = set()

# These fields may legitimately differ if the builder improves formatting while
# preserving the audited facts. Add fields here only after explicit approval.
IGNORED_NESTED_KEYS = {
    "provenance.builder",
    "derived_features.spwin_training_notes",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def scrub(obj: Any, prefix: str = "") -> Any:
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            if prefix == "" and k in IGNORED_TOP_LEVEL_FIELDS:
                continue
            if full in IGNORED_NESTED_KEYS:
                continue
            cleaned[k] = scrub(v, full)
        return cleaned
    if isinstance(obj, list):
        return [scrub(v, prefix) for v in obj]
    return obj


def compare(expected_dir: Path, generated_dir: Path) -> tuple[bool, list[str]]:
    messages: list[str] = []
    expected_files = sorted(expected_dir.glob("*.json"))
    generated_files = sorted(generated_dir.glob("*.json"))

    if not expected_files:
        return False, [f"No expected JSON files found in {expected_dir}"]
    if not generated_files:
        return False, [f"No generated JSON files found in {generated_dir}"]

    expected_names = {p.name for p in expected_files}
    generated_names = {p.name for p in generated_files}

    missing = sorted(expected_names - generated_names)
    extra = sorted(generated_names - expected_names)
    if missing:
        messages.append(f"Missing generated files: {missing}")
    if extra:
        messages.append(f"Unexpected generated files: {extra}")

    ok = not missing and not extra
    for name in sorted(expected_names & generated_names):
        exp = scrub(load_json(expected_dir / name))
        got = scrub(load_json(generated_dir / name))
        if exp != got:
            ok = False
            messages.append(f"DIFF: {name}")
            messages.append(f"  expected match_id={exp.get('match_id')} markets={len(exp.get('markets', []))}")
            messages.append(f"  generated match_id={got.get('match_id')} markets={len(got.get('markets', []))}")
            if exp.get("score") != got.get("score"):
                messages.append(f"  score mismatch: expected={exp.get('score')} generated={got.get('score')}")
            if exp.get("derived_features", {}).get("pattern") != got.get("derived_features", {}).get("pattern"):
                messages.append(
                    "  pattern mismatch: "
                    f"expected={exp.get('derived_features', {}).get('pattern')} "
                    f"generated={got.get('derived_features', {}).get('pattern')}"
                )
        else:
            messages.append(f"PASS: {name}")

    return ok, messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Gold Record Builder output against expected references.")
    parser.add_argument("--expected", required=True, help="Expected reviewed JSON folder")
    parser.add_argument("--generated", required=True, help="Generated JSON folder")
    args = parser.parse_args()

    expected_dir = Path(args.expected)
    generated_dir = Path(args.generated)
    if not expected_dir.exists() or not generated_dir.exists():
        print("Expected and generated folders must both exist.", file=sys.stderr)
        return 2

    ok, messages = compare(expected_dir, generated_dir)
    for msg in messages:
        print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

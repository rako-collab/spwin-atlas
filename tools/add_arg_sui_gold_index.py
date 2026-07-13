#!/usr/bin/env python3
"""Safely activate the approved Argentina vs Switzerland Gold record."""

from __future__ import annotations

import json
from pathlib import Path

GOLD_DIR = Path("data/world_cup_2026/gold")
INDEX_PATH = GOLD_DIR / "MATCH_INDEX.json"
APPROVED_FILE = "WC2026-QF-ARG-SUI_v1.0.json"
EXPECTED_BEFORE = 98
EXPECTED_AFTER = 99


def index_entry(record: dict, filename: str) -> dict:
    entry = {
        "date": record["date"],
        "match_id": record["match_id"],
        "match": record["match"],
        "stage": record["stage"],
        "score": record["score"],
        "qualifier": record["qualifier"],
        "file": filename,
    }
    return entry


def main() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    records = index.get("records")
    if not isinstance(records, list):
        raise SystemExit("MATCH_INDEX records must be a list")

    if index.get("total_records") != len(records):
        raise SystemExit(
            f"Refusing activation: total_records={index.get('total_records')} "
            f"but records length={len(records)}"
        )

    path = GOLD_DIR / APPROVED_FILE
    if not path.exists():
        raise SystemExit(f"Approved Gold file is missing: {path}")

    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("quality_grade") != "Gold" or record.get("status") != "COMPLETED":
        raise SystemExit("Approved file is not a completed Gold record")
    if record.get("score", {}).get("ft_90") != "1-1":
        raise SystemExit("Argentina–Switzerland ft_90 must be 1-1")
    if record.get("score", {}).get("aet") != "3-1":
        raise SystemExit("Argentina–Switzerland aet must be 3-1")
    if record.get("qualifier") != "Argentina":
        raise SystemExit("Argentina must be stored as qualifier")

    existing_files = {row.get("file") for row in records}
    existing_ids = {row.get("match_id") for row in records}

    if APPROVED_FILE in existing_files:
        if len(records) != EXPECTED_AFTER:
            raise SystemExit(
                f"Record already indexed but expected {EXPECTED_AFTER} total; found {len(records)}"
            )
        print(f"Gold record already active; total={len(records)}")
        return

    if len(records) != EXPECTED_BEFORE:
        raise SystemExit(
            f"Expected {EXPECTED_BEFORE} active records before activation; found {len(records)}"
        )
    if record["match_id"] in existing_ids:
        raise SystemExit(f"Duplicate active match_id: {record['match_id']}")

    records.append(index_entry(record, APPROVED_FILE))
    records.sort(key=lambda row: (row["date"], row["match_id"]), reverse=True)
    index["total_records"] = len(records)
    index["generated_on"] = "2026-07-13"

    if len(records) != EXPECTED_AFTER:
        raise SystemExit(f"Expected {EXPECTED_AFTER} records after activation; found {len(records)}")

    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Activated {APPROVED_FILE}; total={len(records)}")


if __name__ == "__main__":
    main()

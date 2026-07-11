#!/usr/bin/env python3
"""One-time safe repair of the World Cup 2026 Gold match index.

Appends exactly the nine approved completed knockout records while preserving
all existing index entries and correction selections.
"""

from __future__ import annotations

import json
from pathlib import Path

GOLD_DIR = Path("data/world_cup_2026/gold")
INDEX_PATH = GOLD_DIR / "MATCH_INDEX.json"

APPROVED_FILES = [
    "WC2026-QF-ESP-BEL_v1.0.json",
    "WC2026-QF-FRA-MAR_v1.0.json",
    "WC2026-R16-SUI-COL_v1.0.json",
    "WC2026-R16-ARG-EGY_v1.0.json",
    "WC2026-R16-USA-BEL_v1.0.json",
    "WC2026-R16-POR-ESP_v1.0.json",
    "WC2026-R16-MEX-ENG_v1.0.json",
    "WC2026-R16-PAR-FRA_v1.0.json",
    "WC2026-R16-CAN-MAR_v1.0.json",
]


def index_entry(record: dict, filename: str) -> dict:
    entry = {
        "date": record["date"],
        "match_id": record["match_id"],
        "match": record["match"],
        "stage": record["stage"],
        "score": record["score"],
    }
    if record.get("qualifier"):
        entry["qualifier"] = record["qualifier"]
    if record.get("correction_of"):
        entry["correction_of"] = record["correction_of"]
    entry["file"] = filename
    return entry


def main() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    records = index["records"]

    if index.get("total_records") != len(records):
        raise SystemExit(
            f"Refusing repair: total_records={index.get('total_records')} "
            f"but records length={len(records)}"
        )

    existing_files = {row["file"] for row in records}
    existing_ids = {row["match_id"] for row in records}

    added = []
    for filename in APPROVED_FILES:
        path = GOLD_DIR / filename
        if not path.exists():
            raise SystemExit(f"Approved Gold file is missing: {path}")

        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("quality_grade") != "Gold" or record.get("status") != "COMPLETED":
            raise SystemExit(f"Invalid Gold/completion status in {filename}")

        if filename in existing_files:
            continue
        if record["match_id"] in existing_ids:
            raise SystemExit(
                f"Duplicate match_id with a different active file: {record['match_id']}"
            )

        entry = index_entry(record, filename)
        records.append(entry)
        existing_files.add(filename)
        existing_ids.add(record["match_id"])
        added.append(filename)

    # Date descending, then stable match_id ordering for deterministic output.
    records.sort(key=lambda row: (row["date"], row["match_id"]), reverse=True)
    index["total_records"] = len(records)
    index["generated_on"] = "2026-07-11"

    if len(records) != 98:
        raise SystemExit(f"Expected 98 active records after repair; found {len(records)}")

    approved_set = set(APPROVED_FILES)
    indexed_approved = {row["file"] for row in records if row["file"] in approved_set}
    if indexed_approved != approved_set:
        missing = approved_set - indexed_approved
        raise SystemExit(f"Approved files still missing from index: {sorted(missing)}")

    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Gold index repaired: added {len(added)} records; total=98")


if __name__ == "__main__":
    main()

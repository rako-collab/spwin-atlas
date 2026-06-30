#!/usr/bin/env python3
"""
SPWIN Historical Importer v2 — SGOdds Enrichment Pipeline

This importer normalizes saved SGOdds results-past-odds pages into SPWIN Atlas.

Current v0.1 capabilities:
- Parses saved text or HTML snapshots using regex-based market detection.
- Extracts Singapore Pools market codes and market names.
- Writes normalized market rows to markets.csv.
- Writes import audit rows.
- Computes first-pass derived match metrics from matches.csv and odds.csv.

Important:
This script does not bypass website access controls. For reliable historical backfill,
save SGOdds pages locally under sources/sgodds/... and run in html/text mode.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


MARKET_FIELDS = [
    "match_id",
    "source_event_id",
    "source_url",
    "market_code",
    "market_name",
    "period",
    "selection",
    "team",
    "line",
    "opening_odds",
    "closing_odds",
    "current_odds",
    "result_status",
    "settlement_rule",
    "captured_at_sgt",
    "data_quality",
    "notes",
]

DERIVED_FIELDS = [
    "match_id",
    "source_event_id",
    "favourite_team",
    "favourite_closing_odds",
    "favourite_odds_band",
    "favourite_won_1x2",
    "draw_result",
    "home_goals",
    "away_goals",
    "total_goals",
    "btts_result",
    "over_0_5",
    "over_1_5",
    "over_2_5",
    "over_3_5",
    "over_4_5",
    "odd_even",
    "capital_shield_default",
    "notes",
]

AUDIT_FIELDS = [
    "source_event_id",
    "source_url",
    "input_file",
    "import_status",
    "markets_detected",
    "rows_written",
    "warnings",
    "captured_at_sgt",
    "notes",
]

MARKET_NAME_BY_CODE = {
    "01": "1X2",
    "02": "Asian Handicap",
    "03": "HT/FT",
    "10": "Halftime 1X2",
    "11": "Halftime Correct Score",
    "12": "Total Goals Over/Under",
    "14": "Halftime Goals Over/Under",
    "46": "Winning Margin",
    "50": "Team to Score Last",
    "53": "Team to Score 4th Goal",
    "82": "Which Half More Goals",
    "91": "Who Will Qualify",
    "95": "Both Teams To Score",
    "97": "HT Team To Score First",
    "98": "HT Odd/Even",
    "99": "HT Total Goals",
}


def read_csv(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: List[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def append_csv(path: Path, fieldnames: List[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def normalize_text(raw: str, mode: str) -> str:
    text = unescape(raw)
    if mode == "html":
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", "\n", text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[\t ]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def extract_event_id(path: Path, text: str) -> str:
    m = re.search(r"(?:event[-_ ]?details|odds|event)[^0-9]*(\d{5,6})", text, flags=re.I)
    if m:
        return m.group(1)
    m = re.search(r"(\d{5,6})", path.stem)
    return m.group(1) if m else path.stem


def parse_decimal(value: str) -> str:
    try:
        return f"{float(value):.2f}"
    except ValueError:
        return ""


def detect_market_blocks(text: str) -> List[Tuple[str, str, str]]:
    """Return blocks as (code, market_name, block_text)."""
    pattern = re.compile(r"(?m)^\s*(\d{2})\s+([^\n]+)")
    matches = list(pattern.finditer(text))
    blocks: List[Tuple[str, str, str]] = []
    for idx, match in enumerate(matches):
        code = match.group(1)
        if code not in MARKET_NAME_BY_CODE:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        raw_name = match.group(2).strip()
        canonical_name = MARKET_NAME_BY_CODE.get(code, raw_name)
        blocks.append((code, canonical_name, text[start:end].strip()))
    return blocks


def parse_market_block(match_id: str, event_id: str, source_url: str, code: str, market_name: str, block: str, captured_at: str) -> List[dict]:
    """Generic parser for SGOdds-like market blocks.

    The parser is intentionally conservative: it captures selection + odds pairs when
    nearby text is parseable, and leaves complex settlement fields blank for later
    enrichment.
    """
    rows: List[dict] = []
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    pending_selection = ""
    for line in lines:
        # Common pattern: selection text followed by decimal odds, e.g. "France 1.20"
        m = re.match(r"^(.+?)\s+(-?\d+\.\d{2})$", line)
        if m:
            selection = m.group(1).strip()
            odds = parse_decimal(m.group(2))
            if selection and odds:
                rows.append(make_market_row(match_id, event_id, source_url, code, market_name, selection, odds, captured_at))
            continue

        # Some SGOdds copied text places selection and odds on separate lines.
        if re.match(r"^-?\d+\.\d{2}$", line) and pending_selection:
            odds = parse_decimal(line)
            rows.append(make_market_row(match_id, event_id, source_url, code, market_name, pending_selection, odds, captured_at))
            pending_selection = ""
            continue

        # Ignore pure ordinal/index lines such as 01, 02.
        if re.match(r"^\d{1,3}$", line):
            continue

        # Keep as possible selection if it has letters or O/U signs.
        if re.search(r"[A-Za-z]|Over|Under|Draw|Yes|No|\+|-", line):
            pending_selection = line

    return rows


def make_market_row(match_id: str, event_id: str, source_url: str, code: str, market_name: str, selection: str, odds: str, captured_at: str) -> dict:
    period = "HT" if "Half" in market_name or "Halftime" in market_name or code in {"10", "11", "14", "97", "98", "99"} else "FT"
    line = ""
    team = ""
    # Extract common handicap/total line tokens.
    lm = re.search(r"([+-]\d+(?:\.\d+)?|\d+(?:\.\d+)?)", selection)
    if code in {"02", "12", "14"} and lm:
        line = lm.group(1)
    return {
        "match_id": match_id,
        "source_event_id": event_id,
        "source_url": source_url,
        "market_code": code,
        "market_name": market_name,
        "period": period,
        "selection": selection,
        "team": team,
        "line": line,
        "opening_odds": "",
        "closing_odds": odds,
        "current_odds": "",
        "result_status": "",
        "settlement_rule": "decimal_odds_pending_market_settlement",
        "captured_at_sgt": captured_at,
        "data_quality": 3,
        "notes": "Imported by SGOdds Importer v2 generic parser",
    }


def map_event_to_match(matches: List[dict]) -> Dict[str, str]:
    mapping = {}
    for row in matches:
        source_odds = row.get("source_odds", "")
        event = re.search(r"(\d{4,6})", source_odds)
        if event:
            mapping[event.group(1)] = row["match_id"]
    return mapping


def parse_sources(input_dir: Path, output_dir: Path, mode: str) -> None:
    matches = read_csv(output_dir / "matches.csv")
    event_to_match = map_event_to_match(matches)
    captured_at = datetime.now().isoformat(timespec="seconds")

    market_rows: List[dict] = []
    audit_rows: List[dict] = []

    files = sorted(input_dir.glob("*.*"))
    for file_path in files:
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        text = normalize_text(raw, mode)
        event_id = extract_event_id(file_path, text)
        match_id = event_to_match.get(event_id, "")
        source_url = f"https://sgodds.com/football/results-past-odds/event-{event_id}"
        warnings = []
        if not match_id:
            warnings.append("event_id_not_found_in_matches_csv")
            match_id = f"UNKNOWN-{event_id}"

        blocks = detect_market_blocks(text)
        rows_before = len(market_rows)
        for code, market_name, block in blocks:
            market_rows.extend(parse_market_block(match_id, event_id, source_url, code, market_name, block, captured_at))

        rows_written = len(market_rows) - rows_before
        audit_rows.append({
            "source_event_id": event_id,
            "source_url": source_url,
            "input_file": str(file_path),
            "import_status": "imported" if rows_written else "no_rows_detected",
            "markets_detected": len(blocks),
            "rows_written": rows_written,
            "warnings": ";".join(warnings),
            "captured_at_sgt": captured_at,
            "notes": "Importer v2 parse run",
        })

    append_csv(output_dir / "markets.csv", MARKET_FIELDS, market_rows)
    append_csv(output_dir / "import_audit.csv", AUDIT_FIELDS, audit_rows)
    write_csv(output_dir / "derived_metrics.csv", DERIVED_FIELDS, compute_derived_metrics(output_dir))

    print(f"Files processed: {len(files)}")
    print(f"Market rows written: {len(market_rows)}")
    print(f"Audit rows written: {len(audit_rows)}")


def parse_score(score: str) -> Tuple[int, int]:
    if not score or "-" not in score:
        return 0, 0
    home, away = score.split("-", 1)
    return int(home.strip()), int(away.strip())


def odds_band(odds: float) -> str:
    if odds <= 1.20:
        return "heavy_1.01_1.20"
    if odds <= 1.50:
        return "strong_1.21_1.50"
    if odds <= 2.00:
        return "medium_1.51_2.00"
    return "light_2.01_plus"


def compute_derived_metrics(output_dir: Path) -> List[dict]:
    matches = read_csv(output_dir / "matches.csv")
    odds = read_csv(output_dir / "odds.csv")
    odds_by_match: Dict[str, List[dict]] = defaultdict(list)
    for row in odds:
        if row.get("market") == "1X2" and row.get("selection", "").lower() != "draw" and row.get("closing_odds"):
            odds_by_match[row["match_id"]].append(row)

    rows = []
    for match in matches:
        match_id = match["match_id"]
        hg, ag = parse_score(match.get("ft_score", ""))
        total = hg + ag
        fav_team = ""
        fav_odds = ""
        fav_band = ""
        if odds_by_match.get(match_id):
            fav = min(odds_by_match[match_id], key=lambda r: float(r["closing_odds"]))
            fav_team = fav["selection"]
            fav_odds = fav["closing_odds"]
            fav_band = odds_band(float(fav_odds))
        source_event = re.search(r"(\d{4,6})", match.get("source_odds", ""))
        rows.append({
            "match_id": match_id,
            "source_event_id": source_event.group(1) if source_event else "",
            "favourite_team": fav_team,
            "favourite_closing_odds": fav_odds,
            "favourite_odds_band": fav_band,
            "favourite_won_1x2": "Yes" if fav_team and match.get("winner") == fav_team else "No",
            "draw_result": "Yes" if match.get("winner") == "Draw" else "No",
            "home_goals": hg,
            "away_goals": ag,
            "total_goals": total,
            "btts_result": "Yes" if hg > 0 and ag > 0 else "No",
            "over_0_5": "Yes" if total > 0.5 else "No",
            "over_1_5": "Yes" if total > 1.5 else "No",
            "over_2_5": "Yes" if total > 2.5 else "No",
            "over_3_5": "Yes" if total > 3.5 else "No",
            "over_4_5": "Yes" if total > 4.5 else "No",
            "odd_even": "Odd" if total % 2 else "Even",
            "capital_shield_default": "PASS until market edge proven",
            "notes": "Derived from matches.csv and odds.csv",
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="SGOdds Historical Importer v2")
    parser.add_argument("--input", required=True, help="Directory containing saved SGOdds html/text files")
    parser.add_argument("--output", required=True, help="Atlas output directory, e.g. data/world_cup_2026")
    parser.add_argument("--mode", choices=["html", "text"], default="html")
    args = parser.parse_args()

    parse_sources(Path(args.input), Path(args.output), args.mode)


if __name__ == "__main__":
    main()

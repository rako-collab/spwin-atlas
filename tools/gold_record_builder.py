#!/usr/bin/env python3
"""
SPWIN Atlas Gold Record Builder v1.0

Purpose
-------
Convert raw SGOdds-style pasted match text into SPWIN Atlas Gold JSON draft files.

The builder is designed around the World Cup 2026 raw text format used in the
Gold archive workflow:

    Team A vs Team B (25 Jun 2026)
    All past odds movement before match closed. Result HT: 0-0 FT: 2-1

    Asian Handicap (Account Only)
    Team A +0.75
    1.80
    1.92
    +6.7%
    ...

It does not overwrite existing Gold records. It creates draft JSON files that can
be reviewed, adjusted if needed, then committed.

Usage
-----
Single match:
    python tools/gold_record_builder.py --input raw_match.txt --out data/world_cup_2026/gold

Batch folder:
    python tools/gold_record_builder.py --input-dir raw_batch --out data/world_cup_2026/gold

Optional index update:
    python tools/gold_record_builder.py --input-dir raw_batch --out data/world_cup_2026/gold --index data/world_cup_2026/gold/MATCH_INDEX.json

Notes
-----
- Generated files are draft Gold records and should be reviewed before commit.
- The final score is stored only in the result fields; replay engines must ignore
  those fields during blind pre-match replay.
- Historical records remain immutable under Rule 7. Corrections should create a
  new version file rather than replacing an existing one.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DATE_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

MARKET_HEADERS = {
    "Asian Handicap": "AH",
    "Half Time Asian Handicap": "HT_AH",
    "01 | 1X2": "1X2",
    "1X2": "1X2",
    "02 | 1/2 Goal": "HANDICAP_ALT",
    "46 | 1/2 Goal": "HANDICAP_ALT",
    "12 | Total Goals Over/Under": "OU",
    "31 | Total Goals Over/Under": "OU",
    "33 | Total Goals Over/Under": "OU",
    "Will Both Teams Score": "BTTS",
    "03 | Halftime-Fulltime": "HTFT",
    "04 | Pick The Score": "PTS",
    "05 | Total Goals": "TG",
    "08 | Team to Score 1st Goal": "FG",
    "09 | Total Goals Odd/Even": "ODD_EVEN",
    "10 | Halftime 1X2": "HT_1X2",
    "11 | Halftime PTS": "HT_PTS",
    "14 | Halftime Total Goals Over/Under": "HT_OU",
    "15 | Halftime Total Goals Over/Under": "HT_OU",
    "Halftime Total Goals Odd/Even": "HT_ODD_EVEN",
    "Halftime Total Goals": "HT_TG",
    "Half Time Team To Score 1st Goal": "HT_FG",
    "Half Time Will Both Teams Score": "HT_BTTS",
}

NOISE_LINES = {
    "Ezoic",
    "Advertisement",
    "All past odds movement before match closed.",
}

@dataclass
class MatchMeta:
    home: str
    away: str
    match: str
    date_iso: str
    ht: str
    ft: str
    stage: str = "Group Stage"
    competition: str = "FIFA World Cup 2026"


def normalize_team_code(name: str) -> str:
    mapping = {
        "USA": "USA",
        "United States": "USA",
        "Korea Republic": "KOR",
        "South Korea": "KOR",
        "Czech Republic": "CZE",
        "Czechia": "CZE",
        "Holland": "NED",
        "Netherlands": "NED",
        "Curacao": "CUW",
        "Ivory Coast": "CIV",
        "Bosnia": "BIH",
        "Bosnia and Herzegovina": "BIH",
        "DR Congo": "COD",
        "Congo DR": "COD",
        "New Zealand": "NZL",
        "Saudi Arabia": "KSA",
    }
    if name in mapping:
        return mapping[name]
    words = re.sub(r"[^A-Za-z ]", "", name).split()
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(w[0] for w in words[:3]).upper()


def parse_date(date_text: str) -> str:
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", date_text)
    if not m:
        raise ValueError(f"Unable to parse date: {date_text!r}")
    day, mon, year = m.groups()
    return f"{year}-{DATE_MAP[mon]}-{int(day):02d}"


def parse_metadata(raw: str) -> MatchMeta:
    first_line = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    m = re.match(r"(.+?)\s+vs\s+(.+?)\s*\((.+?)\)", first_line)
    if not m:
        raise ValueError("First non-empty line must look like: Team A vs Team B (25 Jun 2026)")
    home, away, date_text = [x.strip() for x in m.groups()]

    result_match = re.search(r"Result\s+HT:\s*([0-9]+-[0-9]+)\s+FT:\s*([0-9]+-[0-9]+)", raw, re.I)
    if not result_match:
        raise ValueError("Could not find result line: Result HT: x-y FT: x-y")
    ht, ft = result_match.groups()

    return MatchMeta(
        home=home,
        away=away,
        match=f"{home} vs {away}",
        date_iso=parse_date(date_text),
        ht=ht,
        ft=ft,
    )


def clean_lines(raw: str) -> list[str]:
    lines: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s in NOISE_LINES:
            continue
        if s.startswith("All past odds movement"):
            continue
        lines.append(s)
    return lines


def canonical_market(line: str) -> str | None:
    for header, code in MARKET_HEADERS.items():
        if line == header or line.startswith(header):
            return code
    return None


def split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        code = canonical_market(line)
        if code:
            current = code
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def parse_number(line: str) -> float | None:
    s = line.replace("%", "").replace("+", "").strip()
    if re.fullmatch(r"-?\d+(?:\.\d+)?", s):
        return float(s)
    return None


def looks_like_selection(line: str) -> bool:
    if parse_number(line) is not None:
        return False
    if line in {"USA", "Draw", "Yes", "No", "Odd", "Even", "Any Other Score", "No 1st Goal"}:
        return True
    return bool(re.search(r"[A-Za-z]", line))


def parse_section_rows(market_code: str, rows: list[str]) -> list[dict[str, Any]]:
    """Best-effort parser for selection/open/close/movement row groups."""
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(rows):
        line = rows[i]
        if not looks_like_selection(line):
            i += 1
            continue

        selection = line
        nums: list[float] = []
        pct: float | None = None
        j = i + 1
        while j < len(rows) and len(nums) < 2:
            n = parse_number(rows[j])
            if n is not None:
                nums.append(n)
            elif looks_like_selection(rows[j]):
                break
            j += 1

        if j < len(rows):
            pct_match = re.match(r"([+-]?\d+(?:\.\d+)?)%", rows[j])
            if pct_match:
                pct = float(pct_match.group(1))
                j += 1

        if len(nums) >= 2:
            record = {
                "market_code": market_code,
                "selection": selection,
                "opening_odds": nums[0],
                "closing_odds": nums[1],
            }
            if pct is not None:
                record["movement_pct"] = pct
            else:
                record["movement_pct"] = round(((nums[1] - nums[0]) / nums[0]) * 100, 1) if nums[0] else None
            out.append(record)
            i = j
        else:
            i += 1
    return out


def infer_market_results(meta: MatchMeta, markets: list[dict[str, Any]]) -> None:
    ht_home, ht_away = [int(x) for x in meta.ht.split("-")]
    ft_home, ft_away = [int(x) for x in meta.ft.split("-")]
    total_goals = ft_home + ft_away
    ht_total = ht_home + ht_away
    btts = ft_home > 0 and ft_away > 0
    ht_btts = ht_home > 0 and ht_away > 0

    winner = meta.home if ft_home > ft_away else meta.away if ft_away > ft_home else "Draw"
    ht_winner = meta.home if ht_home > ht_away else meta.away if ht_away > ht_home else "Draw"

    for m in markets:
        sel = m.get("selection", "")
        code = m.get("market_code")
        result = None

        if code == "1X2":
            result = "Win" if sel == winner else "Loss"
        elif code == "HT_1X2":
            result = "Win" if sel == ht_winner else "Loss"
        elif code == "BTTS":
            if sel.lower() == "yes":
                result = "Win" if btts else "Loss"
            elif sel.lower() == "no":
                result = "Win" if not btts else "Loss"
        elif code == "HT_BTTS":
            if sel.lower() == "yes":
                result = "Win" if ht_btts else "Loss"
            elif sel.lower() == "no":
                result = "Win" if not ht_btts else "Loss"
        elif code in {"PTS", "HT_PTS"}:
            expected = meta.ft if code == "PTS" else meta.ht
            result = "Win" if sel == expected else "Loss"
        elif code in {"TG", "HT_TG"}:
            g = str(total_goals if code == "TG" else ht_total)
            result = "Win" if sel.startswith(g) else "Loss"
        elif code in {"OU", "HT_OU"}:
            line = extract_line(sel)
            if line is not None:
                goals = total_goals if code == "OU" else ht_total
                if sel.lower().startswith("over"):
                    result = "Win" if goals > line else "Loss"
                elif sel.lower().startswith("under"):
                    result = "Win" if goals < line else "Loss"
        elif code == "FG":
            if total_goals == 0:
                result = "Win" if "No 1st Goal" in sel else "Loss"
            else:
                # Without scorer timeline, use winner of first-goal market only if user later confirms.
                result = "Unscored"
        elif code == "HT_FG":
            if ht_total == 0:
                result = "Win" if "No 1st Goal" in sel else "Loss"
            else:
                result = "Unscored"

        if result:
            m["result"] = result


def extract_line(selection: str) -> float | None:
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", selection)
    return float(m.group(1)) if m else None


def classify_pattern(meta: MatchMeta, markets: list[dict[str, Any]]) -> str:
    one_x_two = [m for m in markets if m.get("market_code") == "1X2"]
    if not one_x_two:
        return "UNCLASSIFIED"

    fav = min(one_x_two, key=lambda x: x.get("closing_odds", 999))
    fav_sel = fav.get("selection")
    fav_move = fav.get("movement_pct", 0) or 0
    ht_home, ht_away = [int(x) for x in meta.ht.split("-")]
    ft_home, ft_away = [int(x) for x in meta.ft.split("-")]
    winner = meta.home if ft_home > ft_away else meta.away if ft_away > ft_home else "Draw"
    total_goals = ft_home + ft_away
    btts = ft_home > 0 and ft_away > 0

    if fav_sel != winner and fav_sel != "Draw":
        return "FALSE_FAVOURITE_MARKET_TRAP" if total_goals >= 3 else "LOW_SCORING_FALSE_FAVOURITE"
    if winner == "Draw":
        return "BALANCED_DRAW" if total_goals <= 2 else "HIGH_EVENT_DRAW"
    if fav_sel == winner and total_goals >= 4 and btts:
        return "HIGH_EVENT_FAVOURITE_WITH_RESISTANCE"
    if fav_sel == winner and fav_move <= -8 and not btts:
        return "ELITE_FAVOURITE_COMPLETE_ALIGNMENT"
    if fav_sel == winner and fav_move <= -8:
        return "ELITE_FAVOURITE_STEAM"
    if fav_sel == winner:
        return "STABLE_FAVOURITE_EXECUTION"
    return "UNCLASSIFIED"


def build_record(raw: str) -> dict[str, Any]:
    meta = parse_metadata(raw)
    lines = clean_lines(raw)
    sections = split_sections(lines)
    markets: list[dict[str, Any]] = []
    for code, rows in sections.items():
        markets.extend(parse_section_rows(code, rows))
    infer_market_results(meta, markets)

    home_code = normalize_team_code(meta.home)
    away_code = normalize_team_code(meta.away)
    match_id = f"WC2026-GRP-{home_code}-{away_code}"

    return {
        "schema_version": "1.0",
        "match_id": match_id,
        "match": meta.match,
        "date": meta.date_iso,
        "competition": meta.competition,
        "stage": meta.stage,
        "status": "COMPLETED",
        "quality_grade": "Gold",
        "immutable": True,
        "score": {"ht": meta.ht, "ft": meta.ft},
        "markets": markets,
        "derived_features": {
            "pattern": classify_pattern(meta, markets),
            "actual_total_goals": sum(int(x) for x in meta.ft.split("-")),
            "actual_btts": all(int(x) > 0 for x in meta.ft.split("-")),
            "spwin_training_notes": "Generated by Gold Record Builder v1.0; review before final commit.",
        },
        "provenance": {
            "source": "User-provided SGOdds past odds text",
            "archive_policy": "Rule 7 immutable historical data",
            "builder": "gold_record_builder.py v1.0",
            "version": "v1.0",
        },
    }


def filename_for(record: dict[str, Any]) -> str:
    return f"{record['match_id']}_v1.0.json"


def update_index(index_path: Path, records: list[dict[str, Any]], out_dir: Path) -> None:
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {
            "schema_version": "1.0",
            "index_name": "SPWIN Atlas World Cup 2026 Gold Match Index",
            "generated_on": datetime.utcnow().date().isoformat(),
            "repository": "rako-collab/spwin-atlas",
            "base_path": "data/world_cup_2026/gold",
            "quality_grade": "Gold",
            "archive_policy": "Rule 7 immutable historical data",
            "production_engine": "SPWIN v2.5.1",
            "sort_order": "date_desc",
            "records": [],
        }

    existing = {r["match_id"]: r for r in index.get("records", [])}
    for record in records:
        existing[record["match_id"]] = {
            "date": record["date"],
            "match_id": record["match_id"],
            "match": record["match"],
            "stage": record["stage"],
            "score": record["score"],
            "file": filename_for(record),
        }

    sorted_records = sorted(existing.values(), key=lambda r: (r["date"], r["match_id"]), reverse=True)
    index["records"] = sorted_records
    index["total_records"] = len(sorted_records)
    index["generated_on"] = datetime.utcnow().date().isoformat()
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def iter_input_files(args: argparse.Namespace) -> Iterable[Path]:
    if args.input:
        yield Path(args.input)
    if args.input_dir:
        for p in sorted(Path(args.input_dir).glob("*.txt")):
            yield p


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SPWIN Atlas Gold JSON records from raw pasted odds text.")
    parser.add_argument("--input", help="Single raw .txt file")
    parser.add_argument("--input-dir", help="Folder containing raw .txt files")
    parser.add_argument("--out", required=True, help="Output folder for Gold JSON drafts")
    parser.add_argument("--index", help="Optional MATCH_INDEX.json path to update")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output files")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    built: list[dict[str, Any]] = []
    for raw_path in iter_input_files(args):
        raw = raw_path.read_text(encoding="utf-8")
        record = build_record(raw)
        out_path = out_dir / filename_for(record)
        if out_path.exists() and not args.force:
            raise FileExistsError(f"Refusing to overwrite existing file: {out_path}")
        out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        built.append(record)
        print(f"built {out_path}")

    if args.index:
        update_index(Path(args.index), built, out_dir)
        print(f"updated {args.index}")

    print(f"completed: {len(built)} record(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

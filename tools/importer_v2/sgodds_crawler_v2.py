#!/usr/bin/env python3
"""
SPWIN Historical Importer v2 — SGOdds Archive Crawler

Discovers SGOdds results-past-odds World Cup match links and saves detail pages
as HTML snapshots for importer_v2/sgodds_importer_v2.py.

This crawler is intentionally polite and bounded:
- Starts from the public archive URL.
- Follows only /football/results-past-odds/... match detail links.
- Filters by league text or URL/team patterns where possible.
- Supports max pages and delay controls.
- Saves source snapshots; parsing happens separately.

Usage:

python tools/importer_v2/sgodds_crawler_v2.py \
  --start-url https://sgodds.com/football/results-past-odds \
  --output sources/sgodds/world_cup_2026/html \
  --pages 5 \
  --delay 1.5

Then run:

python tools/importer_v2/sgodds_importer_v2.py \
  --input sources/sgodds/world_cup_2026/html \
  --output data/world_cup_2026 \
  --mode html
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Set
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_HOST = "sgodds.com"
ARCHIVE_PATH = "/football/results-past-odds"

WORLD_CUP_TEAM_KEYWORDS = {
    "Argentina", "Australia", "Austria", "Belgium", "Bosnia", "Brazil", "Canada", "Cape-Verde", "Cape Verde",
    "Colombia", "Congo", "Croatia", "Curacao", "Czech", "Ecuador", "Egypt", "England", "France", "Germany",
    "Ghana", "Haiti", "Holland", "Iran", "Iraq", "Ivory-Coast", "Ivory Coast", "Japan", "Jordan", "Korea",
    "Mexico", "Morocco", "New-Zealand", "New Zealand", "Norway", "Panama", "Paraguay", "Portugal", "Qatar",
    "Saudi-Arabia", "Saudi Arabia", "Scotland", "Senegal", "South-Africa", "South Africa", "Spain", "Sweden",
    "Switzerland", "Tunisia", "Turkey", "Uruguay", "USA", "Uzbekistan"
}


@dataclass(frozen=True)
class MatchLink:
    title: str
    url: str
    event_id: str


def fetch_url(url: str, timeout: int = 30) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "SPWIN-Atlas-ResearchBot/2.0 (+https://github.com/rako-collab/spwin-atlas)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def archive_page_url(start_url: str, page: int) -> str:
    if page <= 1:
        return start_url
    separator = "&" if "?" in start_url else "?"
    return f"{start_url}{separator}page={page}"


def is_sgodds_results_link(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc in {"", BASE_HOST, f"www.{BASE_HOST}"} and parsed.path.startswith(ARCHIVE_PATH + "/")


def looks_like_world_cup_match(title_or_url: str) -> bool:
    normalized = title_or_url.replace("-", " ")
    return any(keyword.replace("-", " ") in normalized for keyword in WORLD_CUP_TEAM_KEYWORDS)


def extract_match_links(html: str, base_url: str) -> List[MatchLink]:
    links: List[MatchLink] = []

    # Match detail links look like:
    # /football/results-past-odds/South-Africa-vs-Canada-140174
    for href, title in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S):
        url = urljoin(base_url, href)
        if not is_sgodds_results_link(url):
            continue
        clean_title = re.sub(r"<[^>]+>", " ", title)
        clean_title = re.sub(r"\s+", " ", clean_title).strip()
        event = re.search(r"-(\d{5,6})(?:$|[?#])", url)
        if not event:
            continue
        combined = f"{clean_title} {url}"
        if not looks_like_world_cup_match(combined):
            continue
        links.append(MatchLink(title=clean_title or Path(urlparse(url).path).name, url=url, event_id=event.group(1)))

    # De-duplicate while preserving order.
    seen: Set[str] = set()
    unique: List[MatchLink] = []
    for link in links:
        if link.url not in seen:
            unique.append(link)
            seen.add(link.url)
    return unique


def safe_filename(link: MatchLink) -> str:
    slug = Path(urlparse(link.url).path).name
    return f"{link.event_id}_{slug}.html"


def write_manifest(path: Path, links: Iterable[MatchLink]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_id", "title", "url", "snapshot_file"])
        writer.writeheader()
        for link in links:
            writer.writerow({
                "event_id": link.event_id,
                "title": link.title,
                "url": link.url,
                "snapshot_file": safe_filename(link),
            })


def crawl(start_url: str, output_dir: Path, pages: int, delay: float, dry_run: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    all_links: List[MatchLink] = []
    seen_urls: Set[str] = set()

    for page in range(1, pages + 1):
        page_url = archive_page_url(start_url, page)
        print(f"Discovering archive page {page}: {page_url}")
        html = fetch_url(page_url)
        links = extract_match_links(html, page_url)
        for link in links:
            if link.url not in seen_urls:
                all_links.append(link)
                seen_urls.add(link.url)
        time.sleep(delay)

    write_manifest(output_dir / "manifest.csv", all_links)
    print(f"Discovered {len(all_links)} candidate World Cup match links")

    if dry_run:
        print("Dry run enabled; snapshots not downloaded")
        return

    for idx, link in enumerate(all_links, start=1):
        target = output_dir / safe_filename(link)
        if target.exists():
            print(f"[{idx}/{len(all_links)}] exists: {target.name}")
            continue
        print(f"[{idx}/{len(all_links)}] downloading {link.url}")
        html = fetch_url(link.url)
        target.write_text(html, encoding="utf-8")
        time.sleep(delay)

    print(f"Snapshots saved to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and snapshot SGOdds World Cup past odds pages")
    parser.add_argument("--start-url", default="https://sgodds.com/football/results-past-odds")
    parser.add_argument("--output", required=True, help="Snapshot output directory")
    parser.add_argument("--pages", type=int, default=5, help="Number of archive pages to inspect")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between requests in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Only discover links and write manifest")
    args = parser.parse_args()

    crawl(args.start_url, Path(args.output), args.pages, args.delay, args.dry_run)


if __name__ == "__main__":
    main()

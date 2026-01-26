from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.fisheries.noaa.gov"
LIST_URL = (
    "https://www.fisheries.noaa.gov/species-directory/threatened-endangered"
    "?oq=&field_species_categories_vocab=All&field_region_vocab=All&items_per_page=350"
)

OUT_PATH = Path("pipeline/out/noaa_list.json")

@dataclass
class SpeciesListItem:
    source: str
    source_record_id: str
    common_name: str
    detail_url: str

def _normalize_space(s: str) -> str:
    return " ".join(s.split()).strip()

def _slug_from_detail_url(detail_url: str) -> str:
    path = urlparse(detail_url).path.rstrip("/")
    slug = path.split("/")[-1]
    return slug or detail_url

def scrape() -> list[SpeciesListItem]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "endangered-ocean/0.1 (local dev)",
            "Accept": "text/html,application/xhtml+xml",
        }
    )

    resp = session.get(LIST_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # find links that go to /species/<slug>
    anchors = soup.select('a[href^="/species/"]')

    results: list[SpeciesListItem] = []
    seen: set[str] = set()  # avoid duplication

    for a in anchors:
        common_name = _normalize_space(a.get_text(" ", strip=True))
        href = a.get("href")
        if not href or not common_name:
            continue

        detail_url = urljoin(BASE_URL, href)
        if detail_url in seen:
            continue
        seen.add(detail_url)

        results.append(
            SpeciesListItem(
                source="noaa",
                source_record_id=_slug_from_detail_url(detail_url),
                common_name=common_name,
                detail_url=detail_url,
            )
        )
    return results

def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    items = scrape()
    items_sorted = sorted(items, key=lambda x: (x.common_name.lower(), x.detail_url))

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump([asdict(x) for x in items_sorted], f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(items_sorted)} items -> {OUT_PATH}")
    if items_sorted:
        print("Example:")
        print(json.dumps(asdict(items_sorted[0]), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

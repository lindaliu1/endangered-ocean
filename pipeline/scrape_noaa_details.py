import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin
import os
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.fisheries.noaa.gov"

IN_PATH = Path("pipeline/out/noaa_list.json")
OUT_PATH = Path("pipeline/out/noaa_details.json")

# rate limiting/caching
CACHE_DIR = Path(os.getenv("NOAA_CACHE_DIR", "pipeline/.cache/noaa"))
REQUEST_DELAY_S = float(os.getenv("NOAA_DELAY_SECONDS", "0.6"))
NOAA_LIMIT = int(os.getenv("NOAA_LIMIT", "0"))  # 0 = no limit

# caching is ON by default for local dev; set NOAA_CACHE=0/false/no to disable.
NOAA_CACHE_ENABLED = os.getenv("NOAA_CACHE", "1").lower() in {"1", "true", "yes"}

@dataclass
class SpeciesItem:
    source: str
    source_record_id: str
    common_name: str
    scientific_name: str
    status: str
    depth_m: int | None
    depth_notes: str
    depth_source: str
    image_url: str
    threats: list[str]

# helper used for normalizing strings
def _normalize_space(s: str) -> str:
    return " ".join(s.split()).strip()

# collection of helpers to scrape each field
def extract_scientific_name(soup: BeautifulSoup) -> str:
    scientific_name = soup.select_one("p.species-overview__header-subname")
    scientific_name = scientific_name.get_text(strip=True) if scientific_name else ""
    return scientific_name

def extract_status(soup: BeautifulSoup) -> str:
    status = soup.select_one("div.species-overview__status")
    status = status.get_text(strip=True) if status else ""
    if "threatened" in status.lower():
        status = "Threatened"
    elif "endangered" in status.lower():
        status = "Endangered"
    else:
        status = "Other"
    return status

def extract_image_url(soup: BeautifulSoup) -> str:
    image = soup.select_one("img.img-responsive")
    image_src = (
        (image.get("src") if image else None)
        or (image.get("data-src") if image else None)
    )
    image_url = urljoin(BASE_URL, image_src) if image_src else ""
    return image_url

# extract exact depth
def extract_depth(depth_notes: str) -> int | None:
    # todo
    return None

def extract_depth_notes(soup: BeautifulSoup) -> str:
    # extract the paragraph(s) under the "Where They Live" section.
    depth_notes = ""
    where_heading_exists = soup.find(
        string=lambda s: isinstance(s, str)
        and s.strip().lower() == "where they live"
    )
    if where_heading_exists and getattr(where_heading_exists, "parent", None):
        heading_tag = where_heading_exists.parent  # e.g. <h3 class="species-profile__subtitle">...
        paragraphs: list[str] = []

        # collect all paragraphs in the div under "where we live" header
        node = heading_tag
        node = node.find_next_sibling()
        if node and getattr(node, "name", None) == "div":
            for p in node.find_all("p", recursive=False):
                text = _normalize_space(p.get_text(" ", strip=True))
                if text:
                    paragraphs.append(text)

        depth_notes = "\n\n".join(paragraphs)
    return depth_notes

def define_depth_source(depth_m: str) -> str:
    # todo
    return ""

def extract_threats(soup: BeautifulSoup) -> list[str]:
    for label in soup.select("div.species-overview__facts-label"):
        label_text = _normalize_space(label.get_text(" ", strip=True)).lower()
        if label_text == "threats":
            value = label.find_next_sibling("div", class_="species-overview__facts-value")
            if not value:
                continue
            raw_string = _normalize_space(value.get_text(" ", strip=True))
            if not raw_string:
                return []

            parts = [p.strip() for p in raw_string.split(",") if p.strip()]
            print(parts)
            # remove duplicates
            seen: set[str] = set()
            threats: list[str] = []
            for p in parts:
                key = p.lower()
                if key not in seen:
                    seen.add(key)
                    threats.append(p)
            return threats

    return []

def _cache_path_for(source_record_id: str) -> Path:
    return CACHE_DIR / f"{source_record_id}.html"

def _get_detail_html(session: requests.Session, url: str, source_record_id: str) -> str:
    """Fetch HTML with optional on-disk caching."""
    cache_path = _cache_path_for(source_record_id)
    if NOAA_CACHE_ENABLED:
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    html = resp.text

    if NOAA_CACHE_ENABLED:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(html, encoding="utf-8")

    # be polite to NOAA
    if REQUEST_DELAY_S > 0:
        time.sleep(REQUEST_DELAY_S)

    return html

def scrape() -> list[SpeciesItem]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "endangered-ocean/0.1 (local dev)",
            "Accept": "text/html,application/xhtml+xml",
        }
    )

    results: list[SpeciesItem] = []

    # for each detail url from the json list, scrape the details page
    list_items = json.loads(IN_PATH.read_text())
    if NOAA_LIMIT and NOAA_LIMIT > 0:
        list_items = list_items[:NOAA_LIMIT]

    for species_list_item in list_items:
        detail_url = species_list_item["detail_url"]

        html = _get_detail_html(session, detail_url, species_list_item["source_record_id"])
        soup = BeautifulSoup(html, "html.parser")

        # depth normalization handling
        depth_notes = extract_depth_notes(soup)
        depth_m = extract_depth(depth_notes)
        depth_source = define_depth_source(depth_m)

        results.append(
            SpeciesItem(
                source=species_list_item["source"],
                source_record_id=species_list_item["source_record_id"],
                common_name=species_list_item["common_name"],
                scientific_name=extract_scientific_name(soup),
                status=extract_status(soup),
                depth_m=depth_m,
                depth_notes=depth_notes,
                depth_source=depth_source,
                image_url=extract_image_url(soup),
                threats=extract_threats(soup),
            )
        )

    return results

def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    items = scrape()
    items_sorted = sorted(items, key=lambda x: (x.common_name.lower(), x.source_record_id))

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump([asdict(x) for x in items_sorted], f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(items_sorted)} items -> {OUT_PATH}")
    print(f"Example:")
    print(json.dumps(asdict(items_sorted[0]), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
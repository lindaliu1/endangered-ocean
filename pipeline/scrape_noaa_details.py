import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin
import os
import time
import re

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
    min_depth_m: int | None
    max_depth_m: int | None
    depth_notes: str
    depth_source: str
    image_url: str
    threats: list[str]

# helper used for normalizing strings
def _normalize_space(s: str) -> str:
    return " ".join(s.split()).strip()

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

def _normalize_common_name(name: str) -> str:
    cleaned = re.sub(r"\s*\(protected\)\s*", " ", name, flags=re.IGNORECASE)
    return _normalize_space(cleaned)

def extract_scientific_name(soup: BeautifulSoup) -> str:
    scientific_name = soup.select_one("p.species-overview__header-subname")
    scientific_name = scientific_name.get_text(strip=True) if scientific_name else ""
    return scientific_name

def extract_status(soup: BeautifulSoup) -> str:
    status = soup.select_one("div.species-overview__status")
    status = status.get_text(strip=True) if status else ""
    # normalize status
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
def _to_meters(value: float, unit: str) -> float:
    unit_l = unit.lower()
    if unit_l in {"m", "meter", "meters"}:
        return value
    if unit_l in {"ft", "feet"}:
        return value * 0.3048
    return value


def _parse_explicit_depth_range_m(depth_notes: str) -> tuple[int | None, int | None]:
    """parse an explicit depth range from depth_notes

    returns (min_depth_m, max_depth_m) as ints (rounded). if a single explicit
    depth is found, returns (depth_m, depth_m). if nothing is found, returns (None, None).

    notes:
    - requires depth context words (depth/deep/depths) *within the same sentence* to reduce false positives.
    - skips sentences likely referring to body length.
    - normalizes feet/ft -> meters.
    """
    if not depth_notes:
        return None, None

    def split_sentences(text: str) -> list[str]:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        return [str.strip() for str in re.split(r"(?<=[.!?])\s+", text) if str.strip()]

    sentences = split_sentences(depth_notes)
    if not sentences:
        return None, None

    num = r"\d{1,4}(?:,\d{3})?"
    unit = r"m|meters?|ft|feet"

    # range patterns
    between_re = re.compile(
        rf"\b(?:at\s+depths?\s+)?(?:depths?\s*)?(?:between|from)\s+(?P<a>{num})\s*(?:to|and|-|–)\s*(?P<b>{num})\s*(?P<unit>{unit})\b",
        re.IGNORECASE,
    )
    range_re = re.compile(
        rf"\b(?:at\s+|in\s+)?(?:water\s+)?(?:depths?\s*(?:of|ranging\s+from)?\s*)?(?P<a>{num})\s*(?:to|-|–)\s*(?P<b>{num})\s*(?P<unit>{unit})\b",
        re.IGNORECASE,
    )

    # single-depth patterns
    single_deep_re = re.compile(
        rf"\b(?:to\s+about\s+|to\s+|about\s+)?(?P<a>{num})\s*(?P<unit>{unit})\s+(?:deep|depths?)\b",
        re.IGNORECASE,
    )
    lt_re = re.compile(
        rf"\b(?:<|less\s+than)\s*(?P<a>{num})\s*(?P<unit>{unit})\b(?:\s+(?:deep|depths?))?",
        re.IGNORECASE,
    )
    # "as deep as 640 feet" / "as deep as 1,082 meters"
    as_deep_as_re = re.compile(
        rf"\bas\s+deep\s+as\s+(?P<a>{num})\s*(?P<unit>{unit})\b",
        re.IGNORECASE,
    )
    # "in depths to 426 feet" / "depths to 1,082 meters"
    depths_to_re = re.compile(
        rf"\bdepths?\s+to\s+(?P<a>{num})\s*(?P<unit>{unit})\b",
        re.IGNORECASE,
    )
    # "diving to 1,000-meter depths" (or "1,000 meter depths")
    diving_to_re = re.compile(
        rf"\bdiv(?:e|es|ing)\s+to\s+(?P<a>{num})\s*[- ]?\s*(?P<unit>{unit})\s+(?:depths?|deep)\b",
        re.IGNORECASE,
    )

    depth_context_re = re.compile(r"\b(depth|depths|deep)\b", re.IGNORECASE)
    length_context_re = re.compile(r"\b(length|long|in\s+length)\b", re.IGNORECASE)

    for sent in sentences:
        s = _normalize_space(sent)
        if not depth_context_re.search(s):
            continue
        if length_context_re.search(s):
            continue

        for pattern in (between_re, range_re):
            match = pattern.search(s)
            if match:
                num1 = float(match.group("a").replace(",", ""))
                num2 = float(match.group("b").replace(",", ""))
                unit = match.group("unit")
                explicit_min = _to_meters(min(num1, num2), unit)
                explicit_max = _to_meters(max(num1, num2), unit)
                return int(round(explicit_min)), int(round(explicit_max))

        for pattern in (single_deep_re, as_deep_as_re, depths_to_re, diving_to_re):
            match = pattern.search(s)
            if match:
                num1 = float(match.group("a").replace(",", ""))
                unit = match.group("unit")
                meters = _to_meters(num1, unit)
                val = int(round(meters))
                return val, val

        match = lt_re.search(s)
        if match:
            num1 = float(match.group("a").replace(",", ""))
            unit = match.group("unit")
            meters = _to_meters(num1, unit)
            val = int(round(meters))
            return 0, val

    return None, None


def _infer_depth_bucket_range_m(depth_notes: str) -> tuple[int | None, int | None, str]:
    """infer depth range from keywords when explicit depth is missing.

    buckets:
    - shallow: 0–20m
    - continental shelf: 20–200m
    - deep: 200–1000m

    returns (min_depth_m, max_depth_m, bucket_name).
    """
    if not depth_notes:
        return None, None, ""

    text = _normalize_space(depth_notes).lower()

    deep_keywords = [
        "deep sea",
        "deepwater",
        "deep-water",
        "offshore",
        "oceanic",
        "pelagic",
        "upper slope",
        "continental slope",
        "abyss",
        "bathyal",
        "over deep water",
        "deeper waters",
        "deeper than",
    ]
    if any(word in text for word in deep_keywords):
        return 200, 1000, "deep"

    shelf_keywords = [
        "continental shelf",
        "shelf waters",
        "shelf break",
        "outer shelf",
        "over the continental shelf",
    ]
    if any(word in text for word in shelf_keywords):
        return 20, 200, "continental_shelf"

    shallow_keywords = [
        "intertidal",
        "subtidal",
        "shallow",
        "nearshore",
        "inshore",
        "coastal",
        "reef",
        "lagoons",
        "lagoon",
        "estuaries",
        "estuary",
        "river mouth",
        "seagrass",
        "mangrove",
        "bays",
        "bay",
    ]
    if any(word in text for word in shallow_keywords):
        return 0, 20, "shallow"

    return None, None, ""

def extract_depth_range(depth_notes: str) -> tuple[int | None, int | None]:
    # depth range extraction: prioritizes explicit first, bucket inference if explicit missing
    explicit_min, explicit_max = _parse_explicit_depth_range_m(depth_notes)
    if explicit_min is not None or explicit_max is not None:
        return explicit_min, explicit_max

    inferred_min, inferred_max, _bucket = _infer_depth_bucket_range_m(depth_notes)
    return inferred_min, inferred_max


def define_depth_source(depth_notes: str, min_depth_m: int | None, max_depth_m: int | None) -> str:
    if min_depth_m is None and max_depth_m is None:
        return "unknown"

    explicit_min, explicit_max = _parse_explicit_depth_range_m(depth_notes)
    if explicit_min is not None or explicit_max is not None:
        return "explicit"

    inferred_min, inferred_max, bucket = _infer_depth_bucket_range_m(depth_notes)
    if bucket and (inferred_min is not None or inferred_max is not None):
        return f"bucket:{bucket}"

    return "unknown"

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

# extract and normalize threats by categorizing into top 7 major threat themes
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

def normalize_threats(threats: list[str]) -> list[str]:
    """
    note that not all scraped threats are categorized, only the major ones
    """
    if not threats:
        return []
    
    # keywords for each normalized category
    #climate change
    cc_keywords = [
        "climate change",
        "ocean acidification",
        "ocean warming",
        "sea level rise",
        "temperatures",
    ]
    # disease
    disease_keywords = [
        "disease",
        "diseases",
    ]
    # fishing
    fishing_keywords = [
        "fishing",
        "bycatch",
        "overfishing",
        "fisheries",
        "entanglement",
        "vessel",
        "vessel-based",
        "harvest",
        "overharvest",
    ]
    # habitat loss
    habitat_keywords = [
        "habitat",
        "habitats",
        "dredging",
        "habitat",
    ]
    # oil and general pollution
    pollution_keywords = [
        "oil",
        "spill",
        "gas",
        "pollution",
        "pollutants",
        "contaminants",
        "toxic",
        "toxins",
        "debris",
    ]
    # predation
    predation_keywords = [
        "predation",
        "predators",
        "harassment",
    ]
    # low population
    population_keywords = [
        "population",
    ]
    
    normalized_threat_list = []
    seen = set()
    for threat in threats:
        threat_lower = threat.lower()
        if any(keyword in threat_lower for keyword in cc_keywords):
            seen.add("climate change")
        elif any(keyword in threat_lower for keyword in disease_keywords):
            seen.add("disease")
        elif any(keyword in threat_lower for keyword in fishing_keywords):
            seen.add("fishing")
        elif any(keyword in threat_lower for keyword in habitat_keywords):
            seen.add("habitat loss")
        elif any(keyword in threat_lower for keyword in pollution_keywords):
            seen.add("pollution")
        elif any(keyword in threat_lower for keyword in predation_keywords):
            seen.add("predation")
        elif any(keyword in threat_lower for keyword in population_keywords):
            seen.add("low population")
    for n_threat in seen:
        normalized_threat_list.append(n_threat)

    return normalized_threat_list


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
        min_depth_m, max_depth_m = extract_depth_range(depth_notes)
        depth_source = define_depth_source(depth_notes, min_depth_m, max_depth_m)

        # threats normalization handling
        threats = extract_threats(soup)
        normalized_threats = normalize_threats(threats)

        results.append(
            SpeciesItem(
                source=species_list_item["source"],
                source_record_id=species_list_item["source_record_id"],
                common_name=_normalize_common_name(species_list_item["common_name"]),
                scientific_name=extract_scientific_name(soup),
                status=extract_status(soup),
                min_depth_m=min_depth_m,
                max_depth_m=max_depth_m,
                depth_notes=depth_notes,
                depth_source=depth_source,
                image_url=extract_image_url(soup),
                threats=normalized_threats,
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
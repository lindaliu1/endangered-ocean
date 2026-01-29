from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

import hashlib
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

# rembg try catch exception if deployment fails
try:
    from rembg import remove as rembg_remove  # type: ignore
except Exception:  # pragma: no cover
    rembg_remove = None

from backend.db import db_connection, get_database_url
from backend.queries import GET_SPECIES_SQL, LIST_SPECIES_SQL, LIST_THREATS_SQL
from backend.schemas import SpeciesOut, Status, ThreatOut

app = FastAPI(title="Endangered Ocean API", version="0.1.0")

<<<<<<< HEAD
# CORS
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
if _allowed_origins_env:
    ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
else:
    # Local Next.js dev defaults
    ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

=======
# CORS for local Next.js dev.
>>>>>>> parent of 3666916 (prepare for backend deployment via render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True}

@app.get("/api/debug/db")
def debug_db_url() -> dict[str, str]:
    # redacted db url to help confirm environment wiring in dev
    return {"database_url": get_database_url(redact_password=True)}

# api call for species list
@app.get("/api/species", response_model=list[SpeciesOut])
def list_species(
    status: Optional[Status] = Query(
        default=None, description="filter by conservation status"
    ),
    threat: Optional[str] = Query(
        default=None, description='filter by threat name (e.g. "climate change")'
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SpeciesOut]:
    params = {
        "status": status,
        "threat": (threat.strip() if threat else None),
        "limit": limit,
        "offset": offset,
    }
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(LIST_SPECIES_SQL, params)
            rows = cur.fetchall()

    return [
        SpeciesOut(
            id=r[0],
            source=r[1],
            source_record_id=r[2],
            detail_url=r[3],
            common_name=r[4],
            scientific_name=r[5],
            status=r[6],
            image_url=r[7],
            min_depth_m=r[8],
            max_depth_m=r[9],
            threats=list(r[10] or []),
        )
        for r in rows
    ]

# api call for species by id
@app.get("/api/species/{species_id}", response_model=SpeciesOut)
def get_species(species_id: int) -> SpeciesOut:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(GET_SPECIES_SQL, {"id": species_id})
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="species not found")

    return SpeciesOut(
        id=row[0],
        source=row[1],
        source_record_id=row[2],
        detail_url=row[3],
        common_name=row[4],
        scientific_name=row[5],
        status=row[6],
        image_url=row[7],
        min_depth_m=row[8],
        max_depth_m=row[9],
        threats=list(row[10] or []),
    )

# api call for threats list
@app.get("/api/threats", response_model=list[ThreatOut])
def list_threats() -> list[ThreatOut]:
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(LIST_THREATS_SQL)
            rows = cur.fetchall()

    return [ThreatOut(id=int(r[0]), name=str(r[1])) for r in rows]

# ---- helpers to proxy image_url image, remove background and convert to png ----
ALLOWED_IMAGE_HOSTS = {
    "www.fisheries.noaa.gov",
    "fisheries.noaa.gov",
}

# verify url is from allowed hosts (NOAA only for now)
def _validate_noaa_image_url(raw_url: str) -> str:
    raw_url = (raw_url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="missing url")
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="invalid url scheme")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_IMAGE_HOSTS:
        raise HTTPException(status_code=400, detail="host not allowed")
    return raw_url

# fetch remote image bytes and return (content, content_type)
def _fetch_remote_image_bytes(url: str) -> tuple[bytes, str]:
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            resp = client.get(
                url,
                headers={
                    "User-Agent": "endangered-ocean/0.1 (+local dev)",
                    "Accept": "image/*,*/*;q=0.8",
                },
            )
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="failed to fetch remote image")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"remote image returned {resp.status_code}",
        )

    content_type = resp.headers.get("content-type") or "application/octet-stream"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="remote content was not an image")

    return resp.content, content_type

# ---- caching bg-remove images for faster performance ----
_BG_REMOVE_CACHE_DIR = Path("backend/.cache/bg_remove")
_BG_REMOVE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# images with background removed, ready to be pixelated on the frontend
# add cache to make loading faster after first request
@app.get("/api/image/bg-remove")
def bg_remove_image(
    url: str = Query(..., description="NOAA image url to background-remove"),
    cache: bool = Query(
        True, description="use cached PNG if available (set to false to force recompute)"
    ),
) -> Response:
    if rembg_remove is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "bg-remove unavailable: rembg/onnxruntime not installed in this environment"
            ),
        )

    # fetch NOAA image and return a png with transparent background
    safe_url = _validate_noaa_image_url(url)

    url_hash = hashlib.sha256(safe_url.encode("utf-8")).hexdigest()
    cache_path = _BG_REMOVE_CACHE_DIR / f"{url_hash}.png"

    # serve from cache
    if cache and cache_path.exists():
        out_bytes = cache_path.read_bytes()
        etag = f'W/"{url_hash}"'
        # 7 days cache
        return Response(
            content=out_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
                "ETag": etag,
                "X-Cache": "HIT",
            },
        )
    
    # if not in cache, fetch and process
    img_bytes, _content_type = _fetch_remote_image_bytes(safe_url)
    try:
        out_bytes = rembg_remove(img_bytes)  # type: ignore[misc]
    except Exception:
        # rembg can fail on unusual inputs
        raise HTTPException(status_code=500, detail="background removal failed")

    # cache write
    try:
        tmp_path = cache_path.with_suffix(".tmp")
        tmp_path.write_bytes(out_bytes)
        os.replace(tmp_path, cache_path)
    except Exception:
        pass

    etag = f'W/"{url_hash}"'
    return Response(
        content=out_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=604800, immutable",
            "ETag": etag,
            "X-Cache": "MISS",
        },
    )

"""
@app.get("/api/image")
def proxy_image(url: str = Query(..., description="NOAA image url to proxy")) -> Response:
    # proxy an image from allowed NOAA hosts.
    # avoids browser CORS restrictions for frontend image access and manipulation
    safe_url = _validate_noaa_image_url(url)

    img_bytes, content_type = _fetch_remote_image_bytes(safe_url)
    return Response(content=img_bytes, media_type=content_type)
"""

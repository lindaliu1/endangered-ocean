from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

from backend.db import db_transaction

DEFAULT_INPUT_PATH = (
    Path(__file__).resolve().parents[1] / "pipeline" / "out" / "noaa_details.json"
)

def _read_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))

# sql commands to populate the tables with upsert logic
UPSERT_SPECIES_SQL = """
INSERT INTO species (
  source,
  source_record_id,
  detail_url,
  common_name,
  scientific_name,
  status,
  image_url,
  min_depth_m,
  max_depth_m,
  depth_notes,
  depth_source
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (source, source_record_id)
DO UPDATE SET
  detail_url = EXCLUDED.detail_url,
  common_name = EXCLUDED.common_name,
  scientific_name = EXCLUDED.scientific_name,
  status = EXCLUDED.status,
  image_url = EXCLUDED.image_url,
  min_depth_m = EXCLUDED.min_depth_m,
  max_depth_m = EXCLUDED.max_depth_m,
  depth_notes = EXCLUDED.depth_notes,
  depth_source = EXCLUDED.depth_source
RETURNING id;
"""

UPSERT_THREAT_SQL = """
INSERT INTO threat (name)
VALUES (%s)
ON CONFLICT (name)
DO UPDATE SET name = EXCLUDED.name
RETURNING id;
"""

DELETE_SPECIES_THREATS_SQL = """
DELETE FROM species_threat
WHERE species_id = %s;
"""

INSERT_SPECIES_THREAT_SQL = """
INSERT INTO species_threat (species_id, threat_id)
VALUES (%s, %s)
ON CONFLICT (species_id, threat_id) DO NOTHING;
"""

COUNT_SPECIES_SQL = "SELECT COUNT(*) FROM species;"

# fill in species table
def upsert_species(cur, row: dict[str, Any]) -> int:
    cur.execute(
        UPSERT_SPECIES_SQL,
        (
            row.get("source"),
            row.get("source_record_id"),
            row.get("detail_url"),
            row.get("common_name"),
            row.get("scientific_name"),
            row.get("status"),
            row.get("image_url"),
            row.get("min_depth_m"),
            row.get("max_depth_m"),
            row.get("depth_notes"),
            row.get("depth_source"),
        ),
    )
    return int(cur.fetchone()[0])

# fill in threat table
def upsert_threat(cur, name: str) -> int:
    clean = (name or "").strip()
    if not clean:
        raise ValueError("threat name is empty")
    cur.execute(UPSERT_THREAT_SQL, (clean,))
    return int(cur.fetchone()[0])

# fill in species_threat relationship table
def replace_species_threats(cur, species_id: int, threat_names: Iterable[str]) -> int:
    cur.execute(DELETE_SPECIES_THREATS_SQL, (species_id,))
    inserted = 0
    for t in threat_names:
        t = (t or "").strip()
        if not t:
            continue
        threat_id = upsert_threat(cur, t)
        cur.execute(INSERT_SPECIES_THREAT_SQL, (species_id, threat_id))
        # psycopg2 rowcount is 1 if inserted, 0 if conflict/do nothing
        inserted += int(cur.rowcount or 0)
    return inserted

def main() -> None:
    input_path = Path(os.getenv("INPUT_JSON", str(DEFAULT_INPUT_PATH))).resolve()
    rows = _read_json(input_path)
    with db_transaction() as conn:
        with conn.cursor() as cur:
            species_count = 0
            link_count = 0
            for row in rows:
                s_id = upsert_species(cur, row)
                species_count += 1
                link_count += replace_species_threats(
                    cur, s_id, (row.get("threats") or [])
                )
            cur.execute(COUNT_SPECIES_SQL)
            total_species = int(cur.fetchone()[0])
    print(
        f"OK: upserted {species_count} species; inserted {link_count} species_threat links; "
        f"db species rows now {total_species}"
    )

if __name__ == "__main__":
    main()

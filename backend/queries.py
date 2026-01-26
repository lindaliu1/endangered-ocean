# raw sql queries for the fastapi layer.
# removed some fields not needed by frontend

LIST_SPECIES_SQL = """
SELECT
  s.id,
  s.source,
  s.source_record_id,
  s.detail_url,
  s.common_name,
  s.scientific_name,
  s.status,
  s.image_url,
  s.min_depth_m,
  s.max_depth_m,
  COALESCE(array_remove(array_agg(DISTINCT t.name), NULL), ARRAY[]::text[]) AS threats
FROM species s
LEFT JOIN species_threat st ON st.species_id = s.id
LEFT JOIN threat t ON t.id = st.threat_id
WHERE
  (%(status)s IS NULL OR s.status = %(status)s)
  AND (
    %(threat)s IS NULL OR s.id IN (
      SELECT st2.species_id
      FROM species_threat st2
      JOIN threat t2 ON t2.id = st2.threat_id
      WHERE t2.name = %(threat)s
    )
  )
GROUP BY s.id
ORDER BY s.common_name ASC
LIMIT %(limit)s
OFFSET %(offset)s;
"""

GET_SPECIES_SQL = """
SELECT
  s.id,
  s.source,
  s.source_record_id,
  s.detail_url,
  s.common_name,
  s.scientific_name,
  s.status,
  s.image_url,
  s.min_depth_m,
  s.max_depth_m,
  COALESCE(array_remove(array_agg(DISTINCT t.name), NULL), ARRAY[]::text[]) AS threats
FROM species s
LEFT JOIN species_threat st ON st.species_id = s.id
LEFT JOIN threat t ON t.id = st.threat_id
WHERE s.id = %(id)s
GROUP BY s.id;
"""

LIST_THREATS_SQL = """
SELECT id, name
FROM threat
ORDER BY name ASC;
"""

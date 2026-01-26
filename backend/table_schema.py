from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS species (
  id SERIAL PRIMARY KEY,
  source TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  detail_url TEXT NOT NULL,
  common_name TEXT NOT NULL,
  scientific_name TEXT NOT NULL,
  status TEXT NOT NULL,
  image_url TEXT NOT NULL,
  min_depth_m DOUBLE PRECISION,
  max_depth_m DOUBLE PRECISION,
  depth_notes TEXT,
  depth_source TEXT,
  CONSTRAINT uq_species_source_record UNIQUE (source, source_record_id),
  CONSTRAINT ck_species_min_depth_nonnegative CHECK (min_depth_m IS NULL OR min_depth_m >= 0),
  CONSTRAINT ck_species_max_depth_nonnegative CHECK (max_depth_m IS NULL OR max_depth_m >= 0)
);

CREATE TABLE IF NOT EXISTS threat (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  CONSTRAINT uq_threat_name UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS species_threat (
  species_id INTEGER NOT NULL REFERENCES species(id) ON DELETE CASCADE,
  threat_id INTEGER NOT NULL REFERENCES threat(id) ON DELETE CASCADE,
  CONSTRAINT uq_species_threat UNIQUE (species_id, threat_id)
);

CREATE INDEX IF NOT EXISTS idx_species_status ON species(status);
CREATE INDEX IF NOT EXISTS idx_threat_name ON threat(name);
CREATE INDEX IF NOT EXISTS idx_species_threat_species_id ON species_threat(species_id);
CREATE INDEX IF NOT EXISTS idx_species_threat_threat_id ON species_threat(threat_id);
"""

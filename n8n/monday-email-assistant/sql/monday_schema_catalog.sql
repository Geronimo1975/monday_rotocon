-- Single-row cache of the workspace board/column catalog, refreshed daily.
CREATE TABLE IF NOT EXISTS rotocon_finance.monday_schema_catalog (
  id          INT PRIMARY KEY DEFAULT 1,
  catalog     JSONB NOT NULL,
  board_count INT NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT monday_schema_catalog_singleton CHECK (id = 1)
);

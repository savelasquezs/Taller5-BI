BEGIN;

ALTER TABLE registros_produccion ALTER COLUMN referencia_id DROP NOT NULL;

INSERT INTO referencias (nombre) VALUES ('Stilo Kids 22cc (6 col)')
ON CONFLICT (nombre) DO NOTHING;

COMMIT;

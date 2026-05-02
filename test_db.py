"""Migrate DB: add sheet_update_json column + extraction_queue table."""
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text, inspect
from backend.db.base import engine, Base
from backend.db import models  # registers all models

insp = inspect(engine)
existing_tables = insp.get_table_names()
print(f"Existing tables: {existing_tables}")

# Add sheet_update_json column if missing
with engine.connect() as conn:
    cols = [c["name"] for c in insp.get_columns("matches")]
    if "sheet_update_json" not in cols:
        conn.execute(text("ALTER TABLE matches ADD COLUMN sheet_update_json JSONB"))
        conn.commit()
        print("Added sheet_update_json column to matches")
    else:
        print("sheet_update_json column already exists")

# Create extraction_queue table if missing
if "extraction_queue" not in existing_tables:
    models.ExtractionQueue.__table__.create(bind=engine)
    print("Created extraction_queue table")
else:
    print("extraction_queue table already exists")

# Update any 'extracted' status matches to 'points_calculated' (old status removed)
with engine.connect() as conn:
    result = conn.execute(text("UPDATE matches SET status = 'completed' WHERE status = 'extracted'"))
    conn.commit()
    print(f"Migrated {result.rowcount} 'extracted' rows to 'completed'")

print("Migration complete!")
print(f"Tables: {inspect(engine).get_table_names()}")

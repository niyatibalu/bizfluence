"""SQLite-friendly additive migrations for new columns."""

from sqlalchemy import inspect, text

from app.database import engine


NEW_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "creator_profiles": [
        ("instagram_url", "VARCHAR(512) DEFAULT ''"),
        ("youtube_url", "VARCHAR(512) DEFAULT ''"),
        ("linkedin_url", "VARCHAR(512) DEFAULT ''"),
        ("other_links", "TEXT DEFAULT ''"),
        ("research_notes", "TEXT DEFAULT ''"),
        ("audience_description", "TEXT DEFAULT ''"),
    ],
    "companies": [
        ("research_notes", "TEXT DEFAULT ''"),
    ],
    "offer_briefs": [
        ("generation_note", "TEXT DEFAULT ''"),
    ],
}


def ensure_schema() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in NEW_COLUMNS.items():
            if table not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

import sqlite3
from pathlib import Path

def init_db(db_path: Path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        outcome BOOLEAN,
        outcome_date TEXT,
        search_keywords TEXT,
        llm_referee_criteria TEXT
    )
    """)

    # 2. Sources Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        url TEXT,
        type TEXT,
        language TEXT
    )
    """)

    # 3. The Vault: Raw Articles (Content-Addressable)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vault_articles (
        article_hash TEXT PRIMARY KEY,
        raw_text TEXT,
        metadata_json TEXT,
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 4. The Vault: Extractions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vault_extractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_hash TEXT,
        event_id TEXT,
        model_version TEXT,
        stance REAL,
        certainty REAL,
        specificity REAL,
        hedge_ratio REAL,
        source_authority REAL,
        claim_english TEXT,
        quote TEXT,
        run_date TEXT,
        FOREIGN KEY(article_hash) REFERENCES vault_articles(article_hash),
        FOREIGN KEY(event_id) REFERENCES events(id)
    )
    """)

    # 5. The Factum Atlas (The Matrix / Soft Links)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS atlas (
        event_id TEXT,
        source_id TEXT,
        article_hash TEXT,
        extraction_id INTEGER,
        source_specific_metadata TEXT,
        PRIMARY KEY(event_id, source_id, article_hash),
        FOREIGN KEY(event_id) REFERENCES events(id),
        FOREIGN KEY(source_id) REFERENCES sources(id),
        FOREIGN KEY(article_hash) REFERENCES vault_articles(article_hash),
        FOREIGN KEY(extraction_id) REFERENCES vault_extractions(id)
    )
    """)

    conn.commit()
    conn.close()
    print(f"Factum Atlas SQLite database initialized at {db_path}")

if __name__ == "__main__":
    root = Path(__file__).parent.parent.parent.parent
    db_path = root / "data" / "atlas_v1.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

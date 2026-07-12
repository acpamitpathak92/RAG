"""Creates the local SQLite schema and sqlite-vec virtual table (idempotent - safe to re-run)."""
from backend.shared.config.settings import get_settings
from backend.shared.storage.vector_store import init_default_db

if __name__ == "__main__":
    conn = init_default_db(get_settings().rag_db_path)
    print(f"Initialized schema at {get_settings().rag_db_path}")
    conn.close()

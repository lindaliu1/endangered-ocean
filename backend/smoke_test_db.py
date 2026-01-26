import os
from dotenv import load_dotenv

from backend.db import db_connection, get_database_url

def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("Missing DATABASE_URL. Create a .env file (see .env.example).")
    print(f"Connecting to {get_database_url(redact_password=True)}")
    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            val = cur.fetchone()[0]
            print(f"DB OK: {val}")

if __name__ == "__main__":
    main()

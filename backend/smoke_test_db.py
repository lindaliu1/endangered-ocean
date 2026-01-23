import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("Missing DATABASE_URL. Create a .env file (see .env.example).")

    # Helpful print to confirm which DB you're hitting
    url = make_url(database_url)
    print(f"Connecting to {url.drivername}://{url.host}:{url.port}/{url.database} as {url.username}")

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        val = conn.execute(text("SELECT 1")).scalar_one()
        print(f"DB OK: {val}")


if __name__ == "__main__":
    main()

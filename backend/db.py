import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as PgConnection

# load environment from .env if present
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "missing DATABASE_URL. create a .env file or set DATABASE_URL in your environment."
    )

@contextmanager
def db_connection() -> Iterator[PgConnection]:
    """
    psycopg2 connection
    note: autocommit enabled; use for read-only queries/manual transation management
    """
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()

@contextmanager
def db_transaction() -> Iterator[PgConnection]:
    """
    psycopg2 connection within a transaction
    commits on success; rolls back on exception
    """

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_database_url(redact_password: bool = True) -> str:
    # redact password from DATABASE_URL for safe logging
    if not redact_password:
        return DATABASE_URL
    # postgresql://user:pass@host:5432/db -> postgresql://user:***@host:5432/db
    try:
        scheme, rest = DATABASE_URL.split("://", 1)
        creds_and_host, path = rest.split("@", 1)
        if ":" in creds_and_host:
            user, _pw = creds_and_host.split(":", 1)
            return f"{scheme}://{user}:***@{path}"
    except ValueError:
        pass
    return DATABASE_URL

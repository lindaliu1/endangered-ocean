from backend.db import db_transaction
from backend.table_schema import SCHEMA_SQL

# create all the tables in the database
def main() -> None:
    with db_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
    print("OK: tables ensured")

if __name__ == "__main__":
    main()

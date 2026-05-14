# merapy-oracledb

Oracle Database adapter for merapy. Implements the `SQLDatabase` Protocol using SQLAlchemy 2.x async with the `oracledb` driver (formerly `cx_Oracle`).

Mirrors [candi-plugin/oracledb-adaptor](https://github.com/golangid/candi-plugin/tree/master/oracledb-adaptor).

## Install

```bash
pip install merapy-oracledb oracledb sqlalchemy[asyncio]
```

## Use

```python
from merapy_oracledb import init_oracle_database
from merapy.codebase.factory.dependency import DependencyBuilder

db = init_oracle_database(
    dsn_write="oracle+oracledb://user:pass@localhost:1521/?service_name=XEPDB1",
    dsn_read="oracle+oracledb://user:pass@replica:1521/?service_name=XEPDB1",  # optional
    pool_size=10,
    max_overflow=5,
)

deps = DependencyBuilder().with_sql_db(db).build()
```

The returned `OracleSQLDatabase` satisfies the merapy `SQLDatabase` Protocol — it plugs in wherever the built-in Postgres adapter does. Alembic migrations work the same way with `oracle+oracledb://` in `alembic.ini`.

## DSN format

```
oracle+oracledb://user:password@host:port/?service_name=ORCLPDB1
```

## Status

Implemented — `SQLDatabase` Protocol via SQLAlchemy async + oracledb driver.

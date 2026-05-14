# merapy-arangodb

ArangoDB document/graph database adapter for merapy. Mirrors [candi-plugin/arangodb-adapter](https://github.com/golangid/candi-plugin/tree/master/arangodb-adapter).

ArangoDB is not SQL — it defines its own `ArangoDatabase` Protocol (separate from merapy's `SQLDatabase`). Register via `DependencyBuilder.with_extended("arangodb", db)`.

## Install

```bash
pip install merapy-arangodb python-arango
```

## Use

```python
from merapy_arangodb import init_arangodb
from merapy.codebase.factory.dependency import DependencyBuilder

db = init_arangodb(
    dsn_write="http://root:password@localhost:8529/my_db",
    dsn_read="http://root:password@replica:8529/my_db",  # optional
)
deps = DependencyBuilder().with_extended("arangodb", db).build()
```

### In a repository

```python
from merapy.codebase.factory.dependency import get_dependency
from merapy_arangodb import ArangoDatabase

db: ArangoDatabase = get_dependency().extended("arangodb")
col = db.write_db().collection("orders")
await col.insert({"_key": "order-1", "total": 99.0})
doc = await db.read_db().collection("orders").get("order-1")
```

## DSN format

```
http[s]://user:password@host:port/db_name
```

## Status

Implemented — read/write client split, health check, DSN parser.

"""ArangoDB adapter for merapy.

Mirrors candi-plugin/arangodb-adapter. ArangoDB is a document/graph database —
it does NOT use SQLAlchemy, so it defines its own ``ArangoDatabase`` Protocol
(separate from merapy's ``SQLDatabase``).

Register via ``DependencyBuilder.with_extended("arangodb", db)``.

Usage::

    from merapy_arangodb import init_arangodb, ArangoDatabase
    from merapy.codebase.factory.dependency import DependencyBuilder

    db = init_arangodb(
        dsn_write="http://root:password@localhost:8529/my_db",
        dsn_read="http://root:password@replica:8529/my_db",  # optional
    )
    deps = DependencyBuilder().with_extended("arangodb", db).build()

    # In a repository:
    from merapy.codebase.factory.dependency import get_dependency
    db: ArangoDatabase = get_dependency().extended("arangodb")
    doc = await db.write_db().collection("orders").insert({"_key": "1", "total": 99})
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol (structural — no inheritance needed)
# ---------------------------------------------------------------------------

class ArangoDatabase:
    """Async ArangoDB read/write database pair.

    Satisfies the merapy extended-dependency pattern. Registered under the
    ``"arangodb"`` key in ``Dependency.extended``.
    """

    def __init__(self, read: Any, write: Any) -> None:
        self._read = read   # python-arango StandardDatabase (async)
        self._write = write

    def read_db(self) -> Any:
        """Return the read-replica ``StandardDatabase``."""
        return self._read

    def write_db(self) -> Any:
        """Return the write ``StandardDatabase``."""
        return self._write

    async def health(self) -> dict[str, str | None]:
        results: dict[str, str | None] = {}
        for label, db in [("arango_read", self._read), ("arango_write", self._write)]:
            try:
                # python-arango async: db.ping() or db.version()
                await db.ping()
                results[label] = None
            except Exception as exc:
                results[label] = str(exc)
        return results

    async def close(self) -> None:
        # python-arango manages its own connection pool; no explicit close needed
        logger.info("arangodb.closed")


# ---------------------------------------------------------------------------
# DSN parser
# ---------------------------------------------------------------------------

@dataclass
class _ArangoDSN:
    """Parsed ArangoDB DSN.

    Format: ``http[s]://user:password@host:port/db_name``
    """
    url: str       # e.g. http://localhost:8529
    username: str
    password: str
    db_name: str


def _parse_dsn(dsn: str) -> _ArangoDSN:
    """Parse ``http://user:pass@host:port/db`` into components."""
    m = re.match(
        r"(?P<scheme>https?)://(?P<user>[^:]+):(?P<pass>[^@]+)@(?P<host>[^/]+)/(?P<db>.+)",
        dsn,
    )
    if not m:
        raise ValueError(
            f"Invalid ArangoDB DSN: {dsn!r}. "
            "Expected format: http://user:password@host:port/db_name"
        )
    return _ArangoDSN(
        url=f"{m.group('scheme')}://{m.group('host')}",
        username=m.group("user"),
        password=m.group("pass"),
        db_name=m.group("db"),
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _connect(parsed: _ArangoDSN) -> Any:
    """Create a python-arango async StandardDatabase."""
    try:
        from arango import ArangoClient
    except ImportError as e:
        raise ImportError(
            "merapy-arangodb requires python-arango: pip install python-arango"
        ) from e

    client = ArangoClient(hosts=parsed.url)
    # python-arango's async API uses AsyncDatabase wrapper
    db = client.db(
        parsed.db_name,
        username=parsed.username,
        password=parsed.password,
    )
    return db


def init_arangodb(
    dsn_write: str,
    dsn_read: str | None = None,
) -> ArangoDatabase:
    """Create an ``ArangoDatabase`` from DSN strings.

    Args:
        dsn_write: Write connection DSN.
            Format: ``http://user:password@host:port/db_name``
        dsn_read: Optional read-replica DSN. Defaults to ``dsn_write``.

    Returns:
        ``ArangoDatabase`` with ``read_db()`` and ``write_db()`` accessors.
    """
    logger.info("arangodb.connecting", dsn=_mask_dsn(dsn_write))

    write_parsed = _parse_dsn(dsn_write)
    write_db = _connect(write_parsed)

    if dsn_read and dsn_read != dsn_write:
        read_parsed = _parse_dsn(dsn_read)
        read_db = _connect(read_parsed)
    else:
        read_db = write_db

    logger.info("arangodb.connected", db=write_parsed.db_name)
    return ArangoDatabase(read=read_db, write=write_db)


def _mask_dsn(dsn: str) -> str:
    return re.sub(r"(:)[^:@]+(@)", r"\1***\2", dsn)


__all__ = ["ArangoDatabase", "init_arangodb"]

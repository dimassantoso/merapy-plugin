"""Oracle Database adapter for merapy.

Implements the merapy ``SQLDatabase`` Protocol using SQLAlchemy 2.x async
with the ``oracledb`` driver (formerly cx_Oracle).

DSN format: ``oracle+oracledb://user:password@host:port/?service_name=ORCLPDB1``

Usage::

    from merapy_oracledb import init_oracle_database
    from merapy.codebase.factory.dependency import DependencyBuilder

    db = init_oracle_database(
        dsn_read="oracle+oracledb://user:pass@localhost:1521/?service_name=XEPDB1",
        dsn_write="oracle+oracledb://user:pass@localhost:1521/?service_name=XEPDB1",
    )
    deps = DependencyBuilder().with_sql_db(db).build()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

logger = logging.getLogger(__name__)


class OracleSQLDatabase:
    """``SQLDatabase`` Protocol implementation backed by python-oracledb + SQLAlchemy async.

    Satisfies the merapy ``SQLDatabase`` Protocol structurally — no inheritance needed.
    """

    def __init__(
        self,
        read_engine: "AsyncEngine",
        write_engine: "AsyncEngine",
        session_factory_: "async_sessionmaker",
    ) -> None:
        self._read_engine = read_engine
        self._write_engine = write_engine
        self._session_factory = session_factory_

    def read_engine(self) -> "AsyncEngine":
        return self._read_engine

    def write_engine(self) -> "AsyncEngine":
        return self._write_engine

    def session_factory(self) -> "async_sessionmaker":
        return self._session_factory

    async def health(self) -> dict[str, str | None]:
        from sqlalchemy import text
        results: dict[str, str | None] = {}
        for label, engine in [("oracle_read", self._read_engine), ("oracle_write", self._write_engine)]:
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1 FROM DUAL"))
                results[label] = None
            except Exception as exc:
                results[label] = str(exc)
        return results

    async def close(self) -> None:
        await self._read_engine.dispose()
        if self._write_engine is not self._read_engine:
            await self._write_engine.dispose()
        logger.info("oracle_db.closed")


def init_oracle_database(
    dsn_write: str,
    dsn_read: str | None = None,
    *,
    pool_size: int = 10,
    max_overflow: int = 5,
    pool_pre_ping: bool = True,
    echo: bool = False,
) -> OracleSQLDatabase:
    """Create an ``OracleSQLDatabase`` from DSN strings.

    Args:
        dsn_write: SQLAlchemy async DSN for the write connection.
            Format: ``oracle+oracledb://user:pass@host:port/?service_name=XEPDB1``
        dsn_read: Optional read-replica DSN. Defaults to ``dsn_write`` (single node).
        pool_size: SQLAlchemy connection pool size.
        max_overflow: Max connections above pool_size.
        pool_pre_ping: Test connections before use (recommended).
        echo: Log all SQL statements (development only).

    Returns:
        ``OracleSQLDatabase`` satisfying the merapy ``SQLDatabase`` Protocol.
    """
    try:
        import oracledb  # noqa: F401 — ensure driver is importable
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
    except ImportError as e:
        raise ImportError(
            "merapy-oracledb requires oracledb and sqlalchemy[asyncio]: "
            "pip install oracledb sqlalchemy[asyncio]"
        ) from e

    logger.info("oracle_db.connecting", dsn_write=_mask_dsn(dsn_write))

    write_engine = create_async_engine(
        dsn_write,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        echo=echo,
    )
    read_engine = (
        create_async_engine(
            dsn_read,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=pool_pre_ping,
            echo=echo,
        )
        if dsn_read and dsn_read != dsn_write
        else write_engine
    )

    factory = sessionmaker(  # type: ignore[call-overload]
        bind=write_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("oracle_db.connected")
    return OracleSQLDatabase(read_engine, write_engine, factory)


def _mask_dsn(dsn: str) -> str:
    """Mask password in DSN for safe logging."""
    import re
    return re.sub(r"(:)[^:@]+(@)", r"\1***\2", dsn)


__all__ = ["OracleSQLDatabase", "init_oracle_database"]

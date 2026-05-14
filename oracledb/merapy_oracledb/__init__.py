"""Oracle DB adapter for merapy SQL layer. Skeleton."""

from __future__ import annotations


class OracleSQLDatabase:
    """`SQLDatabase` impl backed by python-oracledb. TODO: implement."""

    name = "oracle"

    async def health(self) -> dict[str, str | None]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


__all__ = ["OracleSQLDatabase"]

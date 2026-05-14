"""ArangoDB adapter for merapy. Skeleton."""

from __future__ import annotations


class ArangoDatabase:
    """Async ArangoDB client wrapper exposing a merapy-friendly surface.

    TODO: implement read/write client split, health check, ``Closer`` impl.
    """

    name = "arangodb"

    async def health(self) -> dict[str, str | None]:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


__all__ = ["ArangoDatabase"]

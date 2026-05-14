"""STOMP broker + worker for kapynis. Skeleton."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory


class STOMPBroker:
    name = "stomp"

    async def close(self) -> None:
        raise NotImplementedError


class STOMPWorker:
    name = "stomp-worker"

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service

    async def serve(self) -> None:
        raise NotImplementedError

    async def shutdown(self) -> None:
        raise NotImplementedError


__all__ = ["STOMPBroker", "STOMPWorker"]

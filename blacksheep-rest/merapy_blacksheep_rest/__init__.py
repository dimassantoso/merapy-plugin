"""BlackSheep `RESTRouter` + `AppServerFactory` for merapy. Skeleton."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory


class BlackSheepRESTServer:
    """BlackSheep-backed REST `AppServerFactory`. TODO: implement."""

    name = "blacksheep-rest"

    def __init__(self, service: "ServiceFactory") -> None:
        self._service = service

    async def serve(self) -> None:
        raise NotImplementedError

    async def shutdown(self) -> None:
        raise NotImplementedError


__all__ = ["BlackSheepRESTServer"]

"""Sanic-backed `AppServerFactory`. Skeleton — see ../README.md."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kapynis.codebase.factory.service_factory import ServiceFactory


class SanicRESTServer:
    """Sanic implementation of kapynis's REST `AppServerFactory`.

    Mirrors the pattern of `candi-plugin/fiber-rest` for Go candi:
    a separately installable package providing an alternative HTTP engine
    behind the same `RESTRouter` Protocol.

    Implementation TODO:
      1. Build a `Sanic` app, mount middleware (CORS / tracer / log).
      2. Wrap `sanic.Blueprint` as `RESTRouter` (analogous to `route_wrapper.py`
         in `kapynis/codebase/app/rest_server/`).
      3. Iterate `service.modules()` and call `module.rest_handler().mount(router)`.
      4. Run via `Sanic.serve()` in `serve()` and `app.stop()` in `shutdown()`.
    """

    name = "sanic-rest"

    def __init__(self, service: "ServiceFactory", host: str = "0.0.0.0", port: int = 8000) -> None:
        self._service = service
        self._host = host
        self._port = port

    async def serve(self) -> None:
        raise NotImplementedError("SanicRESTServer is a skeleton")

    async def shutdown(self) -> None:
        raise NotImplementedError("SanicRESTServer is a skeleton")

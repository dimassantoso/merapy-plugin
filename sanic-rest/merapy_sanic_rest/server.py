"""Sanic-backed AppServerFactory for merapy.

Mirrors candi-plugin/fiber-rest: alternative HTTP engine behind the same
RESTRouter Protocol. Module handlers work unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class SanicRESTServer:
    """AppServerFactory running Sanic under asyncio.

    Drop-in replacement for merapy's built-in FastAPI / Litestar REST servers.
    Module REST handlers that depend only on the RESTRouter Protocol work
    unchanged.

    Args:
        service: merapy ServiceFactory.
        host: Bind host (default ``0.0.0.0``).
        port: Bind port (default ``8000``).
        workers: Number of Sanic worker processes (default 1 for asyncio compat).
        debug: Enable Sanic debug mode.
    """

    name = "sanic-rest"

    def __init__(
        self,
        service: "ServiceFactory",
        host: str = "0.0.0.0",
        port: int = 8000,
        *,
        workers: int = 1,
        debug: bool = False,
    ) -> None:
        try:
            import sanic  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "merapy-sanic-rest requires sanic: pip install sanic"
            ) from e

        self._service = service
        self._host = host
        self._port = port
        self._workers = workers
        self._debug = debug
        self._app = self._build()
        self._server_task: asyncio.Task[None] | None = None

    def _build(self):  # type: ignore[return]
        from sanic import Sanic
        from sanic.response import json as sanic_json
        from sanic_ext import Extend  # type: ignore[import-untyped]

        env = self._service.config().env

        app = Sanic(env.service_name.replace("-", "_"))

        # CORS — sanic-ext provides this
        try:
            Extend(app)
            app.config.CORS_ORIGINS = ",".join(env.cors_allow_origins)
        except Exception:
            pass  # sanic-ext optional

        # Health endpoint
        @app.get(env.http_root_path or "/")
        async def _health(request):  # type: ignore[no-untyped-def]
            return sanic_json({
                "service": env.service_name,
                "environment": env.environment,
                "status": "ok",
            })

        # Mount module REST handlers
        from merapy_sanic_rest.route_wrapper import SanicRouteWrapper
        root = SanicRouteWrapper(
            prefix=env.http_root_path.rstrip("/") or "",
            name="merapy_root",
        )
        mounted: list[str] = []
        for module in self._service.modules():
            handler = module.rest_handler()
            if handler is None:
                continue
            handler.mount(root)
            mounted.append(module.name)
        root.finalize(app)

        logger.info("sanic_rest.mounted", modules=mounted, port=self._port)
        return app

    async def serve(self) -> None:
        loop = asyncio.get_running_loop()
        server = await self._app.create_server(
            host=self._host,
            port=self._port,
            debug=self._debug,
            return_asyncio_server=True,
        )
        if server is None:
            raise RuntimeError("Sanic failed to create server")
        await server.startup()
        logger.info("sanic_rest.serving", host=self._host, port=self._port)
        await server.serve_forever()

    async def shutdown(self) -> None:
        await self._app.stop()
        logger.info("sanic_rest.stopped")

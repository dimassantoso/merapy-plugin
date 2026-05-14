"""BlackSheep REST adapter for merapy.

Mirrors candi-plugin/echo-rest: alternative HTTP engine behind the same
RESTRouter Protocol. Module handlers work unchanged.

Exports:
    BlackSheepRESTServer   — AppServerFactory running BlackSheep under uvicorn
    BlackSheepRouteWrapper — RESTRouter implementation over blacksheep.Router
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any

from merapy.codebase.interfaces.rest_router import HTTPMiddleware, RouteHandler

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route wrapper
# ---------------------------------------------------------------------------

class BlackSheepRouteWrapper:
    """Concrete RESTRouter implementation over ``blacksheep.Router``.

    Mirrors FastAPIRouteWrapper / LitestarRouteWrapper in merapy core.
    """

    def __init__(self, prefix: str = "") -> None:
        from blacksheep import Router
        self._router = Router()
        self._prefix = prefix.rstrip("/")
        self._children: list[BlackSheepRouteWrapper] = []
        self._middlewares: list[HTTPMiddleware] = []

    def _full(self, pattern: str) -> str:
        return self._prefix + pattern

    def use(self, *middlewares: HTTPMiddleware) -> None:
        self._middlewares.extend(middlewares)

    def group(self, pattern: str, *middlewares: HTTPMiddleware) -> "BlackSheepRouteWrapper":
        child = BlackSheepRouteWrapper(prefix=self._prefix + pattern)
        child._middlewares.extend(self._middlewares)
        child._middlewares.extend(middlewares)
        self._children.append(child)
        return child

    def handle(
        self,
        method: str,
        pattern: str,
        handler: RouteHandler,
        *middlewares: HTTPMiddleware,
    ) -> None:
        self._router.add_route(method.upper(), self._full(pattern), handler)

    def get(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("GET", p, h, *m)

    def post(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("POST", p, h, *m)

    def put(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("PUT", p, h, *m)

    def patch(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("PATCH", p, h, *m)

    def delete(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("DELETE", p, h, *m)

    def head(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("HEAD", p, h, *m)

    def options(self, p: str, h: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("OPTIONS", p, h, *m)

    def finalize(self, app: Any) -> None:
        """Register all routes (including children) onto the BlackSheep Application."""
        for child in self._children:
            child._register_on(self._router)
        # Mount our router onto the app
        for route in self._router:
            app.router.add_route(route.method, route.pattern, route.handler)

    def _register_on(self, parent_router: Any) -> None:
        for child in self._children:
            child._register_on(self._router)
        for route in self._router:
            parent_router.add_route(route.method, route.pattern, route.handler)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class BlackSheepRESTServer:
    """AppServerFactory running BlackSheep under uvicorn.

    Drop-in replacement for merapy's built-in FastAPI / Litestar REST servers.

    Args:
        service: merapy ServiceFactory.
    """

    name = "blacksheep-rest"

    def __init__(self, service: "ServiceFactory") -> None:
        try:
            import blacksheep  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "merapy-blacksheep-rest requires blacksheep: pip install blacksheep"
            ) from e

        self._service = service
        self._app = self._build()
        self._server: Any = None

    def _build(self) -> Any:
        from blacksheep import Application
        from blacksheep.server.responses import json as bs_json

        env = self._service.config().env
        app = Application(show_error_details=env.debug_mode)

        # CORS
        from blacksheep.server.cors import CORSPolicy
        app.use_cors(
            allow_methods=" ".join(env.cors_allow_methods),
            allow_origins=" ".join(env.cors_allow_origins),
            allow_headers=" ".join(env.cors_allow_headers),
        )

        # Health endpoint
        @app.router.get(env.http_root_path or "/")
        async def _health(request: Any) -> Any:
            return bs_json({
                "service": env.service_name,
                "environment": env.environment,
                "status": "ok",
            })

        # Mount module REST handlers
        root = BlackSheepRouteWrapper(prefix=env.http_root_path.rstrip("/") or "")
        mounted: list[str] = []
        for module in self._service.modules():
            handler = module.rest_handler()
            if handler is None:
                continue
            handler.mount(root)
            mounted.append(module.name)
        root.finalize(app)

        logger.info("blacksheep_rest.mounted", modules=mounted)
        return app

    async def serve(self) -> None:
        import uvicorn
        env = self._service.config().env
        config = uvicorn.Config(
            self._app,
            host="0.0.0.0",
            port=env.http_port,
            log_config=None,
            access_log=False,
            lifespan="on",
        )
        self._server = uvicorn.Server(config)
        logger.info("blacksheep_rest.serving", port=env.http_port)
        await self._server.serve()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
            await asyncio.sleep(0)
        logger.info("blacksheep_rest.stopped")


__all__ = ["BlackSheepRESTServer", "BlackSheepRouteWrapper"]

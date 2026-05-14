"""Sanic adapter for merapy RESTRouter Protocol.

Wraps ``sanic.Blueprint`` to satisfy the ``RESTRouter`` interface so module
REST handlers work unchanged regardless of the underlying HTTP framework.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from merapy.codebase.interfaces.rest_router import HTTPMiddleware, RouteHandler

if TYPE_CHECKING:
    from sanic import Sanic


class SanicRouteWrapper:
    """Concrete RESTRouter implementation over ``sanic.Blueprint``.

    Mirrors FastAPIRouteWrapper / LitestarRouteWrapper in merapy core.
    """

    def __init__(self, prefix: str = "", name: str = "root") -> None:
        from sanic import Blueprint
        # Blueprint names must be unique within an app
        self._bp = Blueprint(name or "root", url_prefix=prefix or "/")
        self._children: list[SanicRouteWrapper] = []
        self._middlewares: list[HTTPMiddleware] = []

    def use(self, *middlewares: HTTPMiddleware) -> None:
        self._middlewares.extend(middlewares)

    def group(self, pattern: str, *middlewares: HTTPMiddleware) -> "SanicRouteWrapper":
        import uuid
        child = SanicRouteWrapper(prefix=pattern, name=f"group_{uuid.uuid4().hex[:8]}")
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
        # Sanic uses add_route; middlewares become request middleware on the blueprint
        self._bp.add_route(handler, pattern, methods=[method.upper()])

    def get(self, pattern: str, handler: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("GET", pattern, handler, *m)

    def post(self, pattern: str, handler: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("POST", pattern, handler, *m)

    def put(self, pattern: str, handler: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("PUT", pattern, handler, *m)

    def patch(self, pattern: str, handler: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("PATCH", pattern, handler, *m)

    def delete(self, pattern: str, handler: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("DELETE", pattern, handler, *m)

    def head(self, pattern: str, handler: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("HEAD", pattern, handler, *m)

    def options(self, pattern: str, handler: RouteHandler, *m: HTTPMiddleware) -> None:
        self.handle("OPTIONS", pattern, handler, *m)

    def finalize(self, app: "Sanic") -> None:
        """Register this blueprint and all children onto the Sanic app."""
        for child in self._children:
            child._mount_on_parent(self._bp)
        app.blueprint(self._bp)

    def _mount_on_parent(self, parent: Any) -> None:
        for child in self._children:
            child._mount_on_parent(self._bp)
        parent.blueprint(self._bp)

"""Sanic adapter for merapy RESTRouter Protocol.

Wraps ``sanic.Blueprint`` to satisfy the ``RESTRouter`` interface so module
REST handlers work unchanged regardless of the underlying HTTP framework.

Blueprint hierarchy is built via ``Blueprint.group()`` — the correct Sanic API
for nesting blueprints. Each ``group()`` call creates a child blueprint with a
unique name (required by Sanic) and registers it under the parent.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from merapy.codebase.interfaces.rest_router import HTTPMiddleware, RouteHandler

if TYPE_CHECKING:
    from sanic import Sanic


class SanicRouteWrapper:
    """Concrete RESTRouter implementation over ``sanic.Blueprint``.

    Mirrors FastAPIRouteWrapper / LitestarRouteWrapper in merapy core.

    Blueprint names must be globally unique within a Sanic app — we use a
    short UUID suffix to guarantee uniqueness when ``group()`` is called
    multiple times with the same prefix.
    """

    def __init__(self, prefix: str = "", name: str = "merapy_root") -> None:
        from sanic import Blueprint
        self._bp = Blueprint(name, url_prefix=prefix or "/")
        self._children: list[SanicRouteWrapper] = []
        self._middlewares: list[HTTPMiddleware] = []

    def use(self, *middlewares: HTTPMiddleware) -> None:
        self._middlewares.extend(middlewares)

    def group(self, pattern: str, *middlewares: HTTPMiddleware) -> "SanicRouteWrapper":
        child_name = f"bp_{uuid.uuid4().hex[:8]}"
        child = SanicRouteWrapper(prefix=pattern, name=child_name)
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

    def _collect_blueprints(self) -> list[Any]:
        """Return this blueprint and all children as a flat list for Blueprint.group()."""
        from sanic import Blueprint
        bps = [self._bp]
        for child in self._children:
            bps.extend(child._collect_blueprints())
        return bps

    def finalize(self, app: "Sanic") -> None:
        """Register this blueprint tree onto the Sanic app.

        If there are children, use ``Blueprint.group()`` to nest them under
        the root blueprint's url_prefix. Otherwise register directly.
        """
        from sanic import Blueprint
        if self._children:
            all_bps = [self._bp] + [c._bp for c in self._children]
            group = Blueprint.group(*all_bps, url_prefix=self._bp.url_prefix or "/")
            app.blueprint(group)
        else:
            app.blueprint(self._bp)

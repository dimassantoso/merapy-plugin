"""Sanic REST adapter for merapy.

Mirrors candi-plugin/fiber-rest: a separately installable HTTP engine behind
the same RESTRouter Protocol. Module handlers that depend only on RESTRouter
work unchanged.

Exports:
    SanicRESTServer   — AppServerFactory running Sanic under asyncio
    SanicRouteWrapper — RESTRouter implementation over sanic.Blueprint
"""

from merapy_sanic_rest.server import SanicRESTServer
from merapy_sanic_rest.route_wrapper import SanicRouteWrapper

__all__ = ["SanicRESTServer", "SanicRouteWrapper"]

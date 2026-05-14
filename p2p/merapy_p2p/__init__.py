"""Raw TCP/UDP peer-to-peer AppServerFactory for merapy.

Mirrors candi-plugin/p2p which uses raw net.Listen (TCP) and net.ListenPacket (UDP).
No libp2p — just asyncio streams.

Handler pattern: message prefix before the first ':' byte routes to the handler.
e.g. b"auth:{"user":"x"}" → handler registered as "auth"
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

# Separator byte — same as candi (ASCII ':' = 58)
_SEP = b":"

HandlerFunc = Callable[["P2PContext"], Awaitable[None]]


@dataclass
class P2PContext:
    """Context passed to each P2P handler — mirrors candi's p2p.Context."""
    message: bytes
    _writer: asyncio.StreamWriter

    async def write(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()


@dataclass
class _HandlerEntry:
    prefix: str
    handler: HandlerFunc


class HandlerGroup:
    """Collects P2P handlers from a module's server handler."""

    def __init__(self) -> None:
        self._handlers: list[_HandlerEntry] = []

    def register(self, prefix: str, handler: HandlerFunc) -> None:
        self._handlers.append(_HandlerEntry(prefix=prefix, handler=handler))

    @property
    def handlers(self) -> list[_HandlerEntry]:
        return self._handlers


# ---------------------------------------------------------------------------
# TCP server
# ---------------------------------------------------------------------------

class P2PTCPServer:
    """Raw asyncio TCP server — AppServerFactory for merapy.

    Usage in service config::

        from merapy_p2p import P2PTCPServer, HandlerGroup

        # In module's server_handler(Server.P2P_TCP):
        class MyP2PHandler:
            def mount_handlers(self, group: HandlerGroup) -> None:
                group.register("ping", self._handle_ping)

            async def _handle_ping(self, ctx: P2PContext) -> None:
                await ctx.write(b"pong")

        # In service applications:
        applications.append(P2PTCPServer(service, host="0.0.0.0", port=9100))
    """

    name = "p2p-tcp"

    def __init__(
        self,
        service: "ServiceFactory",
        host: str = "0.0.0.0",
        port: int = 9100,
        *,
        buffer_size: int = 4096,
        max_concurrent: int = 100,
    ) -> None:
        self._service = service
        self._host = host
        self._port = port
        self._buffer_size = buffer_size
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._handlers: dict[str, HandlerFunc] = {}
        self._server: asyncio.Server | None = None

    def _collect_handlers(self) -> None:
        from merapy.codebase.types import Server as SrvType
        for module in self._service.modules():
            h = module.server_handler(SrvType("p2p_tcp"))  # type: ignore[arg-type]
            if h is None:
                continue
            group = HandlerGroup()
            h.mount_handlers(group)  # type: ignore[attr-defined]
            for entry in group.handlers:
                self._handlers[entry.prefix] = entry.handler
                logger.info("p2p_tcp.registered", prefix=entry.prefix, module=module.name)

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        async with self._semaphore:
            try:
                data = await reader.read(self._buffer_size)
                if not data:
                    return
                # Split on first ':' — prefix:payload
                parts = data.split(_SEP, 1)
                prefix = parts[0].decode(errors="replace")
                payload = parts[1] if len(parts) > 1 else b""
                handler = self._handlers.get(prefix)
                if handler is None:
                    logger.warning("p2p_tcp.no_handler", prefix=prefix)
                    writer.write(b"ERR:no handler")
                    await writer.drain()
                    return
                ctx = P2PContext(message=payload, _writer=writer)
                await handler(ctx)
            except Exception:
                logger.exception("p2p_tcp.handler_error")
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass

    async def serve(self) -> None:
        self._collect_handlers()
        self._server = await asyncio.start_server(
            self._handle_connection, self._host, self._port
        )
        logger.info(
            "p2p_tcp.serving",
            host=self._host,
            port=self._port,
            handlers=list(self._handlers.keys()),
        )
        async with self._server:
            await self._server.serve_forever()

    async def shutdown(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            logger.info("p2p_tcp.stopped")


# ---------------------------------------------------------------------------
# UDP server
# ---------------------------------------------------------------------------

class _UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, handlers: dict[str, HandlerFunc], loop: asyncio.AbstractEventLoop) -> None:
        self._handlers = handlers
        self._loop = loop
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        parts = data.split(_SEP, 1)
        prefix = parts[0].decode(errors="replace")
        payload = parts[1] if len(parts) > 1 else b""
        handler = self._handlers.get(prefix)
        if handler is None:
            logger.warning("p2p_udp.no_handler", prefix=prefix)
            return

        transport = self._transport

        class _UDPCtx:
            message = payload

            async def write(self, out: bytes) -> None:
                if transport:
                    transport.sendto(out, addr)

        self._loop.create_task(handler(_UDPCtx()))  # type: ignore[arg-type]


class P2PUDPServer:
    """Raw asyncio UDP server — AppServerFactory for merapy."""

    name = "p2p-udp"

    def __init__(
        self,
        service: "ServiceFactory",
        host: str = "0.0.0.0",
        port: int = 9101,
    ) -> None:
        self._service = service
        self._host = host
        self._port = port
        self._handlers: dict[str, HandlerFunc] = {}
        self._transport: asyncio.DatagramTransport | None = None

    def _collect_handlers(self) -> None:
        from merapy.codebase.types import Server as SrvType
        for module in self._service.modules():
            h = module.server_handler(SrvType("p2p_udp"))  # type: ignore[arg-type]
            if h is None:
                continue
            group = HandlerGroup()
            h.mount_handlers(group)  # type: ignore[attr-defined]
            for entry in group.handlers:
                self._handlers[entry.prefix] = entry.handler
                logger.info("p2p_udp.registered", prefix=entry.prefix, module=module.name)

    async def serve(self) -> None:
        self._collect_handlers()
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _UDPProtocol(self._handlers, loop),
            local_addr=(self._host, self._port),
        )
        logger.info(
            "p2p_udp.serving",
            host=self._host,
            port=self._port,
            handlers=list(self._handlers.keys()),
        )
        # Keep running until shutdown
        try:
            await asyncio.get_event_loop().create_future()  # run forever
        except asyncio.CancelledError:
            pass

    async def shutdown(self) -> None:
        if self._transport is not None:
            self._transport.close()
            logger.info("p2p_udp.stopped")


__all__ = ["P2PTCPServer", "P2PUDPServer", "P2PContext", "HandlerGroup"]

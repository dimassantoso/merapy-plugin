"""STOMP broker + worker for merapy.

Mirrors candi-plugin/stomp-broker exactly:
- STOMPBroker    — Broker Protocol (publisher + connection holder)
- STOMPWorker    — AppServerFactory (subscribes to destinations, dispatches handlers)
- STOMPPublisher — publishes to a STOMP destination

Handler pattern = STOMP destination (e.g. ``/queue/orders``).
Uses ``aiostomp`` for async STOMP over TCP.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, Any

from merapy.codebase.types import EventContext, Worker, WorkerHandlerEntry, WorkerHandlerGroup
from merapy.shared.publisher_argument import PublisherArgument

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

WORKER_TYPE = Worker("stomp_broker")

# Header key injected on every published message (mirrors candi's StompEventID)
_EVENT_ID_HEADER = "stomp-event-id"


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------

class STOMPPublisher:
    """Publishes messages to a STOMP destination via aiostomp."""

    def __init__(self, client: Any) -> None:
        self._client = client  # aiostomp.AioStomp

    async def publish_message(self, args: PublisherArgument) -> None:
        """Send to a STOMP destination.

        ``args.topic`` = destination (e.g. ``/queue/orders``).
        ``args.message`` = raw bytes body.
        ``args.headers`` = STOMP frame headers.
        """
        headers = dict(args.headers or {})
        headers.setdefault(_EVENT_ID_HEADER, str(uuid.uuid4()))
        headers.setdefault("content-type", "application/octet-stream")

        await self._client.send(
            args.topic,
            body=args.message or b"",
            headers=headers,
        )
        logger.debug("stomp.published", destination=args.topic)


# ---------------------------------------------------------------------------
# Broker
# ---------------------------------------------------------------------------

class STOMPBroker:
    """merapy Broker Protocol implementation backed by STOMP (aiostomp).

    Args:
        host: STOMP broker host.
        port: STOMP broker port (default 61613 for ActiveMQ/RabbitMQ STOMP).
        login: STOMP login username.
        passcode: STOMP login password.
        heartbeat: Heartbeat interval in ms (0 to disable).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 61613,
        login: str = "guest",
        passcode: str = "guest",
        *,
        heartbeat: int = 0,
    ) -> None:
        try:
            import aiostomp  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "merapy-stomp-broker requires aiostomp: pip install aiostomp"
            ) from e

        self._host = host
        self._port = port
        self._login = login
        self._passcode = passcode
        self._heartbeat = heartbeat
        self._client: Any = None
        self._publisher: STOMPPublisher | None = None

    async def connect(self) -> None:
        """Establish the STOMP connection. Called by STOMPWorker at startup."""
        import aiostomp

        self._client = aiostomp.AioStomp(
            self._host,
            self._port,
            heartbeat=self._heartbeat,
        )
        await self._client.connect(login=self._login, passcode=self._passcode)
        self._publisher = STOMPPublisher(self._client)
        logger.info("stomp_broker.connected", host=self._host, port=self._port)

    def name(self) -> Worker:
        return WORKER_TYPE

    def configuration(self) -> Any:
        return {"type": "stomp", "host": self._host, "port": self._port}

    def publisher(self) -> STOMPPublisher:
        if self._publisher is None:
            raise RuntimeError("STOMPBroker not connected — call connect() first")
        return self._publisher

    async def health(self) -> dict[str, str | None]:
        if self._client is None:
            return {str(WORKER_TYPE): "not connected"}
        try:
            # aiostomp doesn't expose a ping; check if transport is open
            connected = self._client._protocol is not None
            return {str(WORKER_TYPE): None if connected else "disconnected"}
        except Exception as exc:
            return {str(WORKER_TYPE): str(exc)}

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
        logger.info("stomp_broker.closed")


# ---------------------------------------------------------------------------
# Worker (subscriber)
# ---------------------------------------------------------------------------

class STOMPWorker:
    """AppServerFactory that subscribes to STOMP destinations.

    Each handler's ``pattern`` is the STOMP destination
    (e.g. ``/queue/orders``, ``/topic/events``).

    Args:
        service: merapy ServiceFactory.
        broker: A ``STOMPBroker`` instance.
    """

    name = "stomp-worker"

    def __init__(self, service: "ServiceFactory", broker: STOMPBroker) -> None:
        self._service = service
        self._broker = broker
        self._handlers: dict[str, WorkerHandlerEntry] = {}
        self._stop = asyncio.Event()

    def _collect_handlers(self) -> None:
        for module in self._service.modules():
            h = module.worker_handler(WORKER_TYPE)
            if h is None:
                continue
            group = WorkerHandlerGroup()
            h.mount_handlers(group)
            for entry in group.handlers:
                self._handlers[entry.pattern] = entry
                logger.info("stomp_worker.registered", destination=entry.pattern, module=module.name)

    async def serve(self) -> None:
        self._collect_handlers()

        # Connect broker (creates the aiostomp client)
        await self._broker.connect()

        if not self._handlers:
            logger.info("stomp_worker.no_handlers")
            await self._stop.wait()
            return

        # Subscribe to each destination
        for destination, entry in self._handlers.items():
            await self._broker._client.subscribe(
                destination,
                ack="client",
                handler=self._make_handler(entry),
            )
            logger.info("stomp_worker.subscribed", destination=destination)

        logger.info("stomp_worker.started", destinations=list(self._handlers.keys()))
        await self._stop.wait()

    def _make_handler(self, entry: WorkerHandlerEntry):
        """Return an aiostomp message handler coroutine for the given entry."""
        async def _handler(frame: Any, message: Any) -> None:
            headers: dict[str, str] = dict(frame.headers or {})
            body: bytes = frame.body if isinstance(frame.body, bytes) else (frame.body or b"")
            event_id = headers.get(_EVENT_ID_HEADER, "")

            ctx = EventContext(
                worker_type=str(WORKER_TYPE),
                handler_route=entry.pattern,
                key=event_id,
                body=body,
                headers=headers,
            )
            try:
                await entry.handler(ctx)
                if entry.auto_ack:
                    await message.ack()
            except Exception:
                logger.exception("stomp_worker.handler_error", destination=entry.pattern)

        return _handler

    async def shutdown(self) -> None:
        self._stop.set()
        await self._broker.close()
        logger.info("stomp_worker.stopped")


__all__ = ["STOMPBroker", "STOMPWorker", "STOMPPublisher", "WORKER_TYPE"]

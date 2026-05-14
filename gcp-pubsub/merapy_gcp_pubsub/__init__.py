"""GCP Pub/Sub broker + subscriber worker for merapy.

Mirrors candi-plugin/gcppubsub exactly:
- GCPPubSubBroker  — Broker Protocol (publisher side)
- GCPPubSubWorker  — AppServerFactory (subscriber side)
- GCPPubSubPublisher — publishes to a topic

Handler pattern = topic name. Subscription ID = ``{subscriber_id}_{topic}``.
Topic and subscription are auto-created if they don't exist.
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

WORKER_TYPE: Worker = Worker.GCP_PUBSUB


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------

class GCPPubSubPublisher:
    """Publishes messages to a GCP Pub/Sub topic."""

    def __init__(self, client: Any) -> None:
        self._client = client  # google.cloud.pubsub_v1.PublisherClient

    async def publish_message(self, args: PublisherArgument) -> None:
        """Publish to a topic.

        ``args.topic`` = fully-qualified topic path, e.g.
        ``projects/my-project/topics/my-topic``, or just the topic name
        (the broker will prepend the project path).
        """
        body = args.message if args.message else b""
        attributes = {k: str(v) for k, v in args.headers.items()}
        attributes.setdefault("merapy-event-id", str(uuid.uuid4()))

        loop = asyncio.get_running_loop()
        future = self._client.publish(args.topic, body, **attributes)
        # PublisherClient.publish returns a concurrent.futures.Future — wrap it
        message_id = await loop.run_in_executor(None, future.result)
        logger.debug("gcppubsub.published", topic=args.topic, message_id=message_id)


# ---------------------------------------------------------------------------
# Broker
# ---------------------------------------------------------------------------

class GCPPubSubBroker:
    """merapy Broker Protocol implementation backed by GCP Pub/Sub.

    Args:
        project: GCP project ID.
        credentials_file: Path to service account JSON (uses ADC if omitted).
    """

    def __init__(
        self,
        project: str,
        credentials_file: str | None = None,
    ) -> None:
        try:
            from google.cloud import pubsub_v1
        except ImportError as e:
            raise ImportError(
                "merapy-gcp-pubsub requires google-cloud-pubsub: "
                "pip install google-cloud-pubsub"
            ) from e

        self._project = project
        kwargs: dict[str, Any] = {}
        if credentials_file:
            from google.oauth2 import service_account
            kwargs["credentials"] = service_account.Credentials.from_service_account_file(
                credentials_file,
                scopes=["https://www.googleapis.com/auth/pubsub"],
            )

        self._pub_client = pubsub_v1.PublisherClient(**kwargs)
        self._sub_client = pubsub_v1.SubscriberClient(**kwargs)
        self._publisher = GCPPubSubPublisher(self._pub_client)

    def name(self) -> Worker:
        return WORKER_TYPE

    def configuration(self) -> Any:
        return {"type": "gcp-pubsub", "project": self._project}

    def publisher(self) -> GCPPubSubPublisher:
        return self._publisher

    def topic_path(self, topic: str) -> str:
        if topic.startswith("projects/"):
            return topic
        return self._pub_client.topic_path(self._project, topic)

    def subscription_path(self, subscription_id: str) -> str:
        return self._sub_client.subscription_path(self._project, subscription_id)

    async def health(self) -> dict[str, str | None]:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: list(self._pub_client.list_topics(
                    request={"project": f"projects/{self._project}", "page_size": 1}
                )),
            )
            return {str(WORKER_TYPE): None}
        except Exception as exc:
            return {str(WORKER_TYPE): str(exc)}

    async def close(self) -> None:
        self._pub_client.transport.close()
        self._sub_client.transport.close()
        logger.info("gcppubsub_broker.closed")


# ---------------------------------------------------------------------------
# Worker (subscriber)
# ---------------------------------------------------------------------------

class GCPPubSubWorker:
    """AppServerFactory that subscribes to GCP Pub/Sub topics.

    Each handler's ``pattern`` is the topic name (or full path).
    Subscription ID = ``{subscriber_id}_{topic_name}``.
    Topic and subscription are auto-created if they don't exist.

    Args:
        service: merapy ServiceFactory.
        broker: A ``GCPPubSubBroker`` instance.
        subscriber_id: Prefix for subscription IDs (e.g. service name).
        max_messages: Max messages pulled per request.
        ack_deadline_seconds: Seconds before unacked message redelivers.
    """

    name = "gcp-pubsub-worker"

    def __init__(
        self,
        service: "ServiceFactory",
        broker: GCPPubSubBroker,
        subscriber_id: str = "merapy",
        *,
        max_messages: int = 10,
        ack_deadline_seconds: int = 20,
    ) -> None:
        self._service = service
        self._broker = broker
        self._subscriber_id = subscriber_id
        self._max_messages = max_messages
        self._ack_deadline = ack_deadline_seconds
        self._handlers: dict[str, WorkerHandlerEntry] = {}
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    def _collect_handlers(self) -> None:
        for module in self._service.modules():
            h = module.worker_handler(WORKER_TYPE)
            if h is None:
                continue
            group = WorkerHandlerGroup()
            h.mount_handlers(group)
            for entry in group.handlers:
                self._handlers[entry.pattern] = entry
                logger.info("gcppubsub_worker.registered", topic=entry.pattern, module=module.name)

    def _ensure_topic(self, topic_path: str) -> None:
        from google.api_core.exceptions import AlreadyExists
        try:
            self._broker._pub_client.create_topic(request={"name": topic_path})
            logger.info("gcppubsub_worker.topic_created", topic=topic_path)
        except AlreadyExists:
            pass

    def _ensure_subscription(self, sub_path: str, topic_path: str) -> None:
        from google.api_core.exceptions import AlreadyExists
        try:
            self._broker._sub_client.create_subscription(request={
                "name": sub_path,
                "topic": topic_path,
                "ack_deadline_seconds": self._ack_deadline,
            })
            logger.info("gcppubsub_worker.subscription_created", sub=sub_path)
        except AlreadyExists:
            pass

    async def _pull_loop(
        self,
        sub_path: str,
        entry: WorkerHandlerEntry,
    ) -> None:
        loop = asyncio.get_running_loop()
        while not self._stop.is_set():
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._broker._sub_client.pull(
                        request={"subscription": sub_path, "max_messages": self._max_messages},
                        timeout=5,
                    ),
                )
            except Exception:
                logger.exception("gcppubsub_worker.pull_error", sub=sub_path)
                await asyncio.sleep(1)
                continue

            ack_ids: list[str] = []
            for msg in response.received_messages:
                pm = msg.message
                headers = dict(pm.attributes)
                ctx = EventContext(
                    worker_type=str(WORKER_TYPE),
                    handler_route=entry.pattern,
                    key=pm.message_id,
                    body=bytes(pm.data),
                    headers=headers,
                )
                try:
                    await entry.handler(ctx)
                    if entry.auto_ack:
                        ack_ids.append(msg.ack_id)
                except Exception:
                    logger.exception("gcppubsub_worker.handler_error", topic=entry.pattern)

            if ack_ids:
                await loop.run_in_executor(
                    None,
                    lambda ids=ack_ids: self._broker._sub_client.acknowledge(
                        request={"subscription": sub_path, "ack_ids": ids}
                    ),
                )

            if not response.received_messages:
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

    async def serve(self) -> None:
        self._collect_handlers()
        if not self._handlers:
            logger.info("gcppubsub_worker.no_handlers")
            await self._stop.wait()
            return

        loop = asyncio.get_running_loop()
        for topic_name, entry in self._handlers.items():
            topic_path = self._broker.topic_path(topic_name)
            sub_id = f"{self._subscriber_id}_{topic_name.split('/')[-1]}"
            sub_path = self._broker.subscription_path(sub_id)

            await loop.run_in_executor(None, self._ensure_topic, topic_path)
            await loop.run_in_executor(None, self._ensure_subscription, sub_path, topic_path)

            task = asyncio.create_task(self._pull_loop(sub_path, entry), name=f"gcppubsub:{topic_name}")
            self._tasks.append(task)
            logger.info("gcppubsub_worker.subscribed", topic=topic_path, sub=sub_path)

        logger.info("gcppubsub_worker.started", topics=list(self._handlers.keys()))
        await self._stop.wait()

    async def shutdown(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("gcppubsub_worker.stopped")


__all__ = ["GCPPubSubBroker", "GCPPubSubWorker", "GCPPubSubPublisher", "WORKER_TYPE"]

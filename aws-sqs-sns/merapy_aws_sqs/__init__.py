"""AWS SQS broker + worker, and SNS publisher for merapy.

candi-plugin reference: candi-plugin/amazonsqs (SQS only — no SNS in candi).
SNS is added here as the natural AWS fan-out complement to SQS.

Roles
-----
SQSBroker    — implements merapy Broker Protocol (publisher = SQS, consumer via SQSWorker)
SQSWorker    — AppServerFactory: polls SQS queues, dispatches to module handlers
SNSPublisher — standalone publisher that sends to SNS topics (ARN as topic)

Usage
-----
    from merapy_aws_sqs import SQSBroker, SQSWorker, SNSPublisher
    from merapy.codebase.types import Worker

    # In load_service_configs:
    broker = SQSBroker(region="ap-southeast-1")
    deps = DependencyBuilder().with_broker(Worker.AMAZONSQS, broker).build()

    # In service applications:
    applications.append(SQSWorker(service, broker))

    # Publish to SQS queue URL:
    await broker.publisher().publish_message(PublisherArgument(
        topic="https://sqs.ap-southeast-1.amazonaws.com/123/my-queue",
        message=b'{"event":"order_created"}',
    ))

    # Publish to SNS topic ARN:
    sns = SNSPublisher(region="ap-southeast-1")
    await sns.publish_message(PublisherArgument(
        topic="arn:aws:sns:ap-southeast-1:123456789:my-topic",
        message=b'{"event":"order_created"}',
    ))
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

# Use the first-class enum value added to merapy core
WORKER_TYPE: Worker = Worker.AMAZONSQS


# ---------------------------------------------------------------------------
# SQS Publisher
# ---------------------------------------------------------------------------

class SQSPublisher:
    """Publishes messages to an SQS queue URL via aioboto3.

    Performance: reuses the aioboto3 session across calls; the context manager
    opens/closes a single botocore client per ``publish_message`` call which is
    the correct pattern for aioboto3 (clients are not thread-safe but are
    coroutine-safe within a single task).
    """

    __slots__ = ("_session", "_endpoint_url")

    def __init__(self, session: Any, endpoint_url: str | None = None) -> None:
        self._session = session
        self._endpoint_url = endpoint_url

    async def publish_message(self, args: PublisherArgument) -> None:
        """Send a message to an SQS queue.

        ``args.topic``   — full SQS queue URL.
        ``args.message`` — raw bytes body.
        ``args.key``     — optional deduplication / group ID (FIFO queues).
        ``args.headers`` — sent as MessageAttributes (String type).
        """
        body = args.message.decode() if args.message else ""
        attributes: dict[str, Any] = {
            k: {"DataType": "String", "StringValue": v}
            for k, v in args.headers.items()
        }
        attributes.setdefault("merapy-event-id", {
            "DataType": "String",
            "StringValue": str(uuid.uuid4()),
        })

        send_kwargs: dict[str, Any] = {
            "QueueUrl": args.topic,
            "MessageBody": body,
            "MessageAttributes": attributes,
        }
        # FIFO queue support
        if args.key:
            send_kwargs["MessageGroupId"] = args.key
            send_kwargs["MessageDeduplicationId"] = args.key

        async with self._session.client("sqs", endpoint_url=self._endpoint_url) as client:
            await client.send_message(**send_kwargs)
        logger.debug("sqs.published", queue=args.topic, key=args.key)


# ---------------------------------------------------------------------------
# SNS Publisher
# ---------------------------------------------------------------------------

class SNSPublisher:
    """Publishes messages to an SNS topic ARN via aioboto3.

    SNS is publish-only (fan-out). Subscribers (SQS queues, Lambda, HTTP
    endpoints) are configured in AWS — this plugin only handles the publish side.

    ``args.topic`` must be the full SNS topic ARN.
    """

    __slots__ = ("_session", "_endpoint_url")

    def __init__(
        self,
        region: str = "us-east-1",
        *,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        try:
            import aioboto3
        except ImportError as exc:
            raise ImportError(
                "merapy-aws-sqs-sns requires aioboto3: pip install aioboto3"
            ) from exc

        self._session = aioboto3.Session(
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self._endpoint_url = endpoint_url

    async def publish_message(self, args: PublisherArgument) -> None:
        """Publish to an SNS topic ARN.

        ``args.topic``   — SNS topic ARN.
        ``args.message`` — raw bytes payload.
        ``args.headers`` — SNS MessageAttributes (String type).
        """
        body = args.message.decode() if args.message else ""
        attributes: dict[str, Any] = {
            k: {"DataType": "String", "StringValue": v}
            for k, v in args.headers.items()
        }

        async with self._session.client("sns", endpoint_url=self._endpoint_url) as client:
            resp = await client.publish(
                TopicArn=args.topic,
                Message=body,
                MessageAttributes=attributes,
            )
        logger.debug("sns.published", topic=args.topic, message_id=resp.get("MessageId"))


# ---------------------------------------------------------------------------
# SQS Broker (implements merapy Broker Protocol)
# ---------------------------------------------------------------------------

class SQSBroker:
    """merapy Broker Protocol implementation backed by AWS SQS.

    Registers under ``Worker.AMAZONSQS`` in the Dependency container.

    Args:
        region: AWS region name.
        aws_access_key_id: Optional explicit credentials (uses env/IAM role if omitted).
        aws_secret_access_key: Optional explicit credentials.
        endpoint_url: Override endpoint (e.g. LocalStack: ``http://localhost:4566``).
    """

    __slots__ = ("_session", "_endpoint_url", "_publisher")

    def __init__(
        self,
        region: str = "us-east-1",
        *,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        endpoint_url: str | None = None,
    ) -> None:
        try:
            import aioboto3
        except ImportError as exc:
            raise ImportError(
                "merapy-aws-sqs-sns requires aioboto3: pip install aioboto3"
            ) from exc

        self._session = aioboto3.Session(
            region_name=region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self._endpoint_url = endpoint_url
        self._publisher = SQSPublisher(self._session, endpoint_url)

    def name(self) -> Worker:
        return WORKER_TYPE

    def configuration(self) -> dict[str, Any]:
        return {"type": "aws-sqs", "region": self._session.region_name}

    def publisher(self) -> SQSPublisher:
        return self._publisher

    async def health(self) -> dict[str, str | None]:
        try:
            async with self._session.client("sqs", endpoint_url=self._endpoint_url) as client:
                await client.list_queues(MaxResults=1)
            return {str(WORKER_TYPE): None}
        except Exception as exc:
            return {str(WORKER_TYPE): str(exc)}

    async def close(self) -> None:
        logger.info("sqs_broker.closed")


# ---------------------------------------------------------------------------
# SQS Worker (AppServerFactory — polls queues, dispatches to handlers)
# ---------------------------------------------------------------------------

class SQSWorker:
    """AppServerFactory that polls SQS queues and dispatches to module handlers.

    Each handler's ``pattern`` is the SQS queue URL or queue name (resolved
    to a URL via ``GetQueueUrl`` at startup).

    Performance notes:
    - Uses SQS long-polling (``wait_seconds=20``) to minimise empty-poll cost.
    - All queues are polled concurrently via ``asyncio.gather`` each tick.
    - A single aioboto3 client is reused for the lifetime of ``serve()``.

    Args:
        service: The merapy ServiceFactory.
        broker: An ``SQSBroker`` instance.
        max_messages: Max messages per ``receive_message`` call (1–10).
        wait_seconds: Long-poll wait time in seconds (0–20). 20 recommended.
        visibility_timeout: Seconds a message is hidden after receipt.
        poll_interval: Seconds between polls when all queues are empty.
    """

    name = "sqs-worker"

    __slots__ = (
        "_service", "_broker", "_max_messages", "_wait_seconds",
        "_visibility_timeout", "_poll_interval", "_handlers", "_stop",
    )

    def __init__(
        self,
        service: "ServiceFactory",
        broker: SQSBroker,
        *,
        max_messages: int = 10,
        wait_seconds: int = 20,
        visibility_timeout: int = 30,
        poll_interval: float = 1.0,
    ) -> None:
        self._service = service
        self._broker = broker
        self._max_messages = max(1, min(10, max_messages))
        self._wait_seconds = max(0, min(20, wait_seconds))
        self._visibility_timeout = visibility_timeout
        self._poll_interval = poll_interval
        self._handlers: dict[str, WorkerHandlerEntry] = {}  # queue_url → handler
        self._stop = asyncio.Event()

    def _collect_handlers(self) -> None:
        for module in self._service.modules():
            wh = module.worker_handler(WORKER_TYPE)
            if wh is None:
                continue
            group = WorkerHandlerGroup()
            wh.mount_handlers(group)
            for entry in group.handlers:
                self._handlers[entry.pattern] = entry
                logger.info("sqs_worker.registered", queue=entry.pattern, module=module.name)

    async def _resolve_queue_urls(self, client: Any) -> dict[str, str]:
        """Resolve queue names → full URLs. No-op if pattern is already a URL."""
        resolved: dict[str, str] = {}
        for pattern in self._handlers:
            if pattern.startswith("http"):
                resolved[pattern] = pattern
            else:
                resp = await client.get_queue_url(QueueName=pattern)
                resolved[pattern] = resp["QueueUrl"]
                logger.info("sqs_worker.resolved", name=pattern, url=resolved[pattern])
        return resolved

    async def _poll_queue(
        self,
        client: Any,
        queue_url: str,
        entry: WorkerHandlerEntry,
    ) -> None:
        resp = await client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=self._max_messages,
            WaitTimeSeconds=self._wait_seconds,
            VisibilityTimeout=self._visibility_timeout,
            MessageAttributeNames=["All"],
        )
        for msg in resp.get("Messages", []):
            headers = {
                k: v.get("StringValue", "")
                for k, v in msg.get("MessageAttributes", {}).items()
            }
            ctx = EventContext(
                worker_type=str(WORKER_TYPE),
                handler_route=queue_url,
                key=msg.get("MessageId", ""),
                body=msg.get("Body", "").encode(),
                headers=headers,
            )
            try:
                await entry.handler(ctx)
                if entry.auto_ack:
                    await client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=msg["ReceiptHandle"],
                    )
            except Exception:
                logger.exception("sqs_worker.handler_error", queue=queue_url)

    async def serve(self) -> None:
        self._collect_handlers()
        if not self._handlers:
            logger.info("sqs_worker.no_handlers")
            await self._stop.wait()
            return

        # Single client for the lifetime of serve() — avoids per-poll overhead
        async with self._broker._session.client(
            "sqs", endpoint_url=self._broker._endpoint_url
        ) as client:
            url_to_entry = {
                url: self._handlers[pattern]
                for pattern, url in (await self._resolve_queue_urls(client)).items()
            }
            logger.info("sqs_worker.started", queues=list(url_to_entry.keys()))

            while not self._stop.is_set():
                await asyncio.gather(
                    *(self._poll_queue(client, url, entry)
                      for url, entry in url_to_entry.items()),
                    return_exceptions=True,
                )
                if not self._stop.is_set():
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval)
                    except asyncio.TimeoutError:
                        pass

    async def shutdown(self) -> None:
        self._stop.set()
        logger.info("sqs_worker.stopped")


__all__ = ["SQSBroker", "SQSWorker", "SQSPublisher", "SNSPublisher", "WORKER_TYPE"]

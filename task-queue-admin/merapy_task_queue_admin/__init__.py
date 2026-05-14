"""Enhanced task-queue worker with Mongo and Redis storage backends for merapy.

The core ``TaskQueueWorker`` in merapy only supports SQL persistent storage.
This plugin adds:

1. ``MongoJobStore``  — stores jobs in MongoDB (mirrors candi's preferred backend)
2. ``RedisJobStore``  — stores jobs in Redis (fast, ephemeral, good for dev/test)
3. ``TaskQueueAdminWorker`` — drop-in replacement for ``TaskQueueWorker`` that
   accepts a pluggable ``JobStore`` instead of requiring SQL.

The GraphQL dashboard (``dashboard.py``) is already built into merapy core and
works with any backend that implements ``JobStore``.

Usage::

    from merapy_task_queue_admin import TaskQueueAdminWorker, MongoJobStore, RedisJobStore

    # Mongo backend:
    store = MongoJobStore(mongo_db=deps.mongo_db())
    applications.append(TaskQueueAdminWorker(service, store=store))

    # Redis backend (dev/test):
    store = RedisJobStore(redis=deps.redis_pool().write())
    applications.append(TaskQueueAdminWorker(service, store=store))
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from merapy.codebase.factory.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job status (mirrors merapy core JobStatus)
# ---------------------------------------------------------------------------

class JobStatus(StrEnum):
    QUEUEING = "QUEUEING"
    RETRYING = "RETRYING"
    SUCCESS  = "SUCCESS"
    FAILURE  = "FAILURE"
    STOPPED  = "STOPPED"


# ---------------------------------------------------------------------------
# Job dataclass
# ---------------------------------------------------------------------------

class Job:
    __slots__ = (
        "id", "task_name", "arguments", "retries", "max_retry",
        "status", "error", "result", "trace_id", "created_at",
        "updated_at", "finished_at", "interval",
    )

    def __init__(
        self,
        task_name: str,
        arguments: str = "{}",
        max_retry: int = 3,
        status: str = JobStatus.QUEUEING,
        interval: str = "",
    ) -> None:
        self.id = str(uuid.uuid4())
        self.task_name = task_name
        self.arguments = arguments
        self.retries = 0
        self.max_retry = max_retry
        self.status = status
        self.error = ""
        self.result = ""
        self.trace_id = ""
        self.interval = interval
        now = datetime.now(tz=timezone.utc)
        self.created_at = now
        self.updated_at = now
        self.finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_name": self.task_name,
            "arguments": self.arguments,
            "retries": self.retries,
            "max_retry": self.max_retry,
            "status": self.status,
            "error": self.error,
            "result": self.result,
            "trace_id": self.trace_id,
            "interval": self.interval,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Job":
        j = cls.__new__(cls)
        j.id = d["id"]
        j.task_name = d["task_name"]
        j.arguments = d.get("arguments", "{}")
        j.retries = d.get("retries", 0)
        j.max_retry = d.get("max_retry", 3)
        j.status = d.get("status", JobStatus.QUEUEING)
        j.error = d.get("error", "")
        j.result = d.get("result", "")
        j.trace_id = d.get("trace_id", "")
        j.interval = d.get("interval", "")
        j.created_at = datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.now(tz=timezone.utc)
        j.updated_at = datetime.fromisoformat(d["updated_at"]) if d.get("updated_at") else datetime.now(tz=timezone.utc)
        j.finished_at = datetime.fromisoformat(d["finished_at"]) if d.get("finished_at") else None
        return j


# ---------------------------------------------------------------------------
# JobStore Protocol (abstract base)
# ---------------------------------------------------------------------------

class JobStore(ABC):
    """Abstract storage backend for task queue jobs."""

    @abstractmethod
    async def enqueue(self, job: Job) -> None: ...

    @abstractmethod
    async def dequeue_batch(self, task_names: list[str], limit: int = 50) -> list[Job]: ...

    @abstractmethod
    async def update_status(
        self,
        job_id: str,
        status: str,
        *,
        error: str = "",
        result: str = "",
        retries: int | None = None,
        finished_at: datetime | None = None,
    ) -> None: ...

    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None: ...

    @abstractmethod
    async def count_by_status(self, task_name: str) -> dict[str, int]: ...

    @abstractmethod
    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# MongoDB backend
# ---------------------------------------------------------------------------

class MongoJobStore(JobStore):
    """Stores task queue jobs in MongoDB.

    Collection: ``task_queue_jobs`` (created automatically).

    Args:
        mongo_db: A Motor ``AsyncIOMotorDatabase`` instance
            (from ``merapy.codebase.factory.dependency.get_dependency().mongo_db()``).
        collection: Collection name (default ``task_queue_jobs``).
    """

    def __init__(self, mongo_db: Any, collection: str = "task_queue_jobs") -> None:
        self._col = mongo_db[collection]

    async def enqueue(self, job: Job) -> None:
        doc = job.to_dict()
        doc["_id"] = doc.pop("id")
        await self._col.insert_one(doc)

    async def dequeue_batch(self, task_names: list[str], limit: int = 50) -> list[Job]:
        now = datetime.now(tz=timezone.utc).isoformat()
        cursor = self._col.find(
            {"task_name": {"$in": task_names}, "status": JobStatus.QUEUEING},
            sort=[("created_at", 1)],
            limit=limit,
        )
        jobs = []
        async for doc in cursor:
            doc["id"] = doc.pop("_id")
            jobs.append(Job.from_dict(doc))
        # Mark as RETRYING
        if jobs:
            ids = [j.id for j in jobs]
            await self._col.update_many(
                {"_id": {"$in": ids}},
                {"$set": {"status": JobStatus.RETRYING, "updated_at": now}},
            )
        return jobs

    async def update_status(
        self,
        job_id: str,
        status: str,
        *,
        error: str = "",
        result: str = "",
        retries: int | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        update: dict[str, Any] = {
            "status": status,
            "error": error,
            "result": result,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        if retries is not None:
            update["retries"] = retries
        if finished_at is not None:
            update["finished_at"] = finished_at.isoformat()
        await self._col.update_one({"_id": job_id}, {"$set": update})

    async def get_job(self, job_id: str) -> Job | None:
        doc = await self._col.find_one({"_id": job_id})
        if doc is None:
            return None
        doc["id"] = doc.pop("_id")
        return Job.from_dict(doc)

    async def count_by_status(self, task_name: str) -> dict[str, int]:
        pipeline = [
            {"$match": {"task_name": task_name}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        result = {s: 0 for s in JobStatus}
        async for doc in self._col.aggregate(pipeline):
            result[doc["_id"]] = doc["count"]
        return result

    async def close(self) -> None:
        logger.info("mongo_job_store.closed")


# ---------------------------------------------------------------------------
# Redis backend
# ---------------------------------------------------------------------------

class RedisJobStore(JobStore):
    """Stores task queue jobs in Redis.

    Uses sorted sets for queues (score = created_at timestamp) and hashes
    for job data. Good for development and ephemeral workloads.

    Args:
        redis: An async Redis client
            (from ``merapy.codebase.factory.dependency.get_dependency().redis_pool().write()``).
        key_prefix: Redis key prefix (default ``tq``).
    """

    def __init__(self, redis: Any, key_prefix: str = "tq") -> None:
        self._redis = redis
        self._prefix = key_prefix

    def _job_key(self, job_id: str) -> str:
        return f"{self._prefix}:job:{job_id}"

    def _queue_key(self, task_name: str) -> str:
        return f"{self._prefix}:queue:{task_name}"

    async def enqueue(self, job: Job) -> None:
        pipe = self._redis.pipeline()
        pipe.hset(self._job_key(job.id), mapping={k: str(v) if v is not None else "" for k, v in job.to_dict().items()})
        pipe.zadd(self._queue_key(job.task_name), {job.id: job.created_at.timestamp()})
        await pipe.execute()

    async def dequeue_batch(self, task_names: list[str], limit: int = 50) -> list[Job]:
        jobs: list[Job] = []
        per_task = max(1, limit // len(task_names)) if task_names else limit
        for task_name in task_names:
            ids = await self._redis.zrange(self._queue_key(task_name), 0, per_task - 1)
            for job_id in ids:
                job_id_str = job_id.decode() if isinstance(job_id, bytes) else job_id
                raw = await self._redis.hgetall(self._job_key(job_id_str))
                if not raw:
                    continue
                d = {(k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v) for k, v in raw.items()}
                job = Job.from_dict(d)
                job.status = JobStatus.RETRYING
                await self._redis.hset(self._job_key(job_id_str), "status", JobStatus.RETRYING)
                await self._redis.zrem(self._queue_key(task_name), job_id_str)
                jobs.append(job)
        return jobs

    async def update_status(
        self,
        job_id: str,
        status: str,
        *,
        error: str = "",
        result: str = "",
        retries: int | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        mapping: dict[str, str] = {
            "status": status,
            "error": error,
            "result": result,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        if retries is not None:
            mapping["retries"] = str(retries)
        if finished_at is not None:
            mapping["finished_at"] = finished_at.isoformat()
        await self._redis.hset(self._job_key(job_id), mapping=mapping)

    async def get_job(self, job_id: str) -> Job | None:
        raw = await self._redis.hgetall(self._job_key(job_id))
        if not raw:
            return None
        d = {(k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v) for k, v in raw.items()}
        return Job.from_dict(d)

    async def count_by_status(self, task_name: str) -> dict[str, int]:
        # Scan all jobs for this task — not efficient for large datasets
        # For production use MongoJobStore
        pattern = f"{self._prefix}:job:*"
        counts = {s: 0 for s in JobStatus}
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(cursor, match=pattern, count=100)
            for key in keys:
                raw = await self._redis.hmget(key, "task_name", "status")
                tn = raw[0].decode() if raw[0] else ""
                st = raw[1].decode() if raw[1] else ""
                if tn == task_name and st in counts:
                    counts[st] += 1
            if cursor == 0:
                break
        return counts

    async def close(self) -> None:
        logger.info("redis_job_store.closed")


# ---------------------------------------------------------------------------
# TaskQueueAdminWorker — drop-in replacement with pluggable storage
# ---------------------------------------------------------------------------

class TaskQueueAdminWorker:
    """Drop-in replacement for merapy's ``TaskQueueWorker`` with pluggable storage.

    Accepts any ``JobStore`` (Mongo, Redis, or custom) instead of requiring SQL.
    The built-in GraphQL dashboard is still served on ``TASK_QUEUE_DASHBOARD_PORT``.

    Args:
        service: merapy ServiceFactory.
        store: A ``JobStore`` implementation (``MongoJobStore`` or ``RedisJobStore``).
        poll_interval: Seconds between polls when queue is empty.
    """

    name = "task-queue-admin"

    def __init__(
        self,
        service: "ServiceFactory",
        store: JobStore,
        *,
        poll_interval: float = 1.0,
    ) -> None:
        self._service = service
        self._store = store
        self._poll_interval = poll_interval
        self._stop = asyncio.Event()
        self._handlers: dict[str, Any] = {}
        self._semaphore: asyncio.Semaphore | None = None

    def _collect_handlers(self) -> None:
        from merapy.codebase.app._worker_base import collect_handlers
        from merapy.codebase.types import Worker
        entries = collect_handlers(self._service, Worker.TASK_QUEUE)
        for module, entry in entries:
            self._handlers.setdefault(entry.pattern, []).append((module, entry))

    async def serve(self) -> None:
        from merapy.codebase.app.task_queue_worker.dashboard import TaskQueueDashboard

        env = self._service.config().env
        self._semaphore = asyncio.Semaphore(env.max_workers)
        self._collect_handlers()

        # Serve the built-in dashboard (it reads from _worker_ref which we patch below)
        # We create a minimal shim so the dashboard can query our store
        dashboard = TaskQueueDashboard(self, port=env.task_queue_dashboard_port)  # type: ignore[arg-type]
        dashboard_task = asyncio.create_task(dashboard.serve(), name="task-queue-admin-dashboard")

        try:
            if not self._handlers:
                logger.info("task_queue_admin.no_handlers")
                await self._stop.wait()
                return

            logger.info(
                "task_queue_admin.started",
                tasks=list(self._handlers.keys()),
                store=type(self._store).__name__,
                dashboard=f"http://localhost:{env.task_queue_dashboard_port}",
            )

            while not self._stop.is_set():
                jobs = await self._store.dequeue_batch(list(self._handlers.keys()))
                if not jobs:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=self._poll_interval)
                    except asyncio.TimeoutError:
                        pass
                    continue
                await asyncio.gather(*(self._run(job) for job in jobs))
        finally:
            dashboard_task.cancel()
            await asyncio.gather(dashboard_task, return_exceptions=True)
            await self._store.close()

    async def _run(self, job: Job) -> None:
        assert self._semaphore is not None
        handlers = self._handlers.get(job.task_name, [])
        async with self._semaphore:
            from merapy.codebase.types import EventContext, Worker
            ctx = EventContext(
                worker_type=Worker.TASK_QUEUE.value,
                handler_route=job.task_name,
                key=job.id,
                body=job.arguments.encode(),
                headers={"retries": str(job.retries), "max_retry": str(job.max_retry)},
            )
            error: Exception | None = None
            start_at = datetime.now(tz=timezone.utc)
            for _module, entry in handlers:
                try:
                    await entry.handler(ctx)
                except Exception as exc:
                    error = exc
                    logger.exception("task_queue_admin.handler_error", task=job.task_name)
                    break

            finished_at = datetime.now(tz=timezone.utc)
            new_retries = job.retries + 1
            if error is None:
                await self._store.update_status(
                    job.id, JobStatus.SUCCESS,
                    retries=new_retries, finished_at=finished_at,
                )
            elif new_retries >= job.max_retry:
                await self._store.update_status(
                    job.id, JobStatus.FAILURE,
                    error=str(error), retries=new_retries, finished_at=finished_at,
                )
            else:
                # Re-enqueue for retry
                job.retries = new_retries
                job.error = str(error)
                job.status = JobStatus.QUEUEING
                job.updated_at = finished_at
                await self._store.enqueue(job)

    async def shutdown(self) -> None:
        self._stop.set()
        logger.info("task_queue_admin.stopped")


__all__ = [
    "JobStore",
    "MongoJobStore",
    "RedisJobStore",
    "TaskQueueAdminWorker",
    "Job",
    "JobStatus",
]

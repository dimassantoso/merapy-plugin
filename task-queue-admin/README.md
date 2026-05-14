# merapy-task-queue-admin

Pluggable storage backends (MongoDB, Redis) for merapy's task queue worker. The core `TaskQueueWorker` only supports SQL — this plugin adds `MongoJobStore`, `RedisJobStore`, and `TaskQueueAdminWorker` as a drop-in replacement.

The built-in GraphQL dashboard is still served on `TASK_QUEUE_DASHBOARD_PORT`.

## Install

```bash
pip install merapy-task-queue-admin
# plus your chosen backend:
pip install motor          # for MongoDB
pip install redis          # for Redis
```

## Use — MongoDB backend

```python
from merapy_task_queue_admin import TaskQueueAdminWorker, MongoJobStore

store = MongoJobStore(mongo_db=deps.mongo_db())
applications.append(TaskQueueAdminWorker(service, store=store))
```

## Use — Redis backend (dev/test)

```python
from merapy_task_queue_admin import TaskQueueAdminWorker, RedisJobStore

store = RedisJobStore(redis=deps.redis_pool().write())
applications.append(TaskQueueAdminWorker(service, store=store))
```

## Custom backend

Implement `JobStore` ABC:

```python
from merapy_task_queue_admin import JobStore, Job

class MyJobStore(JobStore):
    async def enqueue(self, job: Job) -> None: ...
    async def dequeue_batch(self, task_names, limit=50) -> list[Job]: ...
    async def update_status(self, job_id, status, **kwargs) -> None: ...
    async def get_job(self, job_id) -> Job | None: ...
    async def count_by_status(self, task_name) -> dict[str, int]: ...
    async def close(self) -> None: ...
```

## Module handlers

Same as the core task queue — handlers registered under `Worker.TASK_QUEUE` work unchanged.

## Status

Implemented — `MongoJobStore`, `RedisJobStore`, `TaskQueueAdminWorker` with pluggable storage.

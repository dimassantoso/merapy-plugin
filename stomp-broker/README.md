# merapy-stomp-broker

STOMP protocol broker + worker for merapy. Compatible with ActiveMQ, RabbitMQ STOMP plugin, and any STOMP-speaking broker. Mirrors [candi-plugin/stomp-broker](https://github.com/golangid/candi-plugin/tree/master/stomp-broker).

## Install

```bash
pip install merapy-stomp-broker aiostomp
```

## Use

```python
from merapy_stomp import STOMPBroker, STOMPWorker, WORKER_TYPE

broker = STOMPBroker(
    host="localhost",
    port=61613,
    login="guest",
    passcode="guest",
)
deps = DependencyBuilder().with_broker(WORKER_TYPE, broker).build()
applications.append(STOMPWorker(service, broker))
```

### Module handler

```python
from merapy.codebase.types import EventContext
from merapy_stomp import WORKER_TYPE

class OrderSTOMPHandler:
    def mount_handlers(self, group):
        group.add("/queue/orders", self._handle)  # STOMP destination

    async def _handle(self, ctx: EventContext) -> None:
        print(ctx.key, ctx.body)
```

### Publish

```python
from merapy.shared.publisher_argument import PublisherArgument

await broker.publisher().publish_message(PublisherArgument(
    topic="/queue/orders",
    message=b'{"event":"order_created"}',
    headers={"content-type": "application/json"},
))
```

## Status

Implemented — async STOMP via aiostomp, client-ack mode, event ID header injection.

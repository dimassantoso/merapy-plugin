# merapy-p2p

Raw TCP/UDP peer-to-peer `AppServerFactory` for merapy. Mirrors [candi-plugin/p2p](https://github.com/golangid/candi-plugin/tree/master/p2p).

> **Note:** Despite the name, this is **not** libp2p. candi's p2p plugin uses raw `net.Listen` (TCP) and `net.ListenPacket` (UDP) — this port uses `asyncio.start_server` / `create_datagram_endpoint`. No external dependencies required.

## Install

```bash
pip install merapy-p2p
```

## Protocol

Messages are framed as `prefix:payload` bytes. The prefix routes to the registered handler:

```
b"ping:hello" → handler registered as "ping" receives b"hello"
```

## Use

```python
from merapy_p2p import P2PTCPServer, P2PUDPServer, HandlerGroup, P2PContext

# In your module's server_handler:
class MyP2PHandler:
    def mount_handlers(self, group: HandlerGroup) -> None:
        group.register("ping", self._handle_ping)
        group.register("echo", self._handle_echo)

    async def _handle_ping(self, ctx: P2PContext) -> None:
        await ctx.write(b"pong")

    async def _handle_echo(self, ctx: P2PContext) -> None:
        await ctx.write(ctx.message)

# In service applications:
applications.append(P2PTCPServer(service, host="0.0.0.0", port=9100))
# or
applications.append(P2PUDPServer(service, host="0.0.0.0", port=9101))
```

## Status

Implemented — TCP and UDP servers with asyncio, no external dependencies.

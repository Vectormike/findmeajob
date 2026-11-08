import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

QUEUE_SIZE = 200


class Broker:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()

    def publish(self, kind: str, **data: Any) -> None:
        for queue in self._queues:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait({"kind": kind, **data})

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)
        self._queues.add(queue)
        try:
            yield queue
        finally:
            self._queues.discard(queue)


broker = Broker()

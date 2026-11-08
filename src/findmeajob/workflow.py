import asyncio
import logging
from collections import defaultdict
from typing import Any

from langgraph.store.base import BaseStore
from langgraph.types import Command

from findmeajob.agents.deps import Deps
from findmeajob.events import broker
from findmeajob.graph import build_graph
from findmeajob.memory import CASES, index_case, now

log = logging.getLogger(__name__)


class Workflow:
    def __init__(self, deps: Deps, checkpointer: Any, store: BaseStore) -> None:
        self.deps = deps
        self.store = store
        self.graph = build_graph(deps, checkpointer, store)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    @staticmethod
    def _config(case_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": case_id}}

    async def _invoke(self, case_id: str, payload: Any) -> None:
        try:
            await self.graph.ainvoke(payload, self._config(case_id))
        except Exception as error:
            log.exception("Case %s failed", case_id)
            item = await self.store.aget(CASES, case_id)
            message = f"the run crashed out: {error}"[:500]
            await self.store.aput(CASES, case_id, {**(item.value if item else {}), "error": message})
            broker.publish("case", case_id=case_id, error=message)
            return
        item = await self.store.aget(CASES, case_id)
        if item and item.value.get("error"):
            await self.store.aput(CASES, case_id, {**item.value, "error": ""})

    async def start(self, case_id: str, posting: dict[str, Any], filters: dict[str, str]) -> None:
        state = {"case_id": case_id, "posting": posting, "filters": filters, "stage": "new"}
        async with self._locks[case_id]:
            await index_case(self.store, state, "scout")
            await self._invoke(case_id, {**state, "mail": [], "debriefs": [], "sent": []})

    async def waiting(self, case_id: str) -> bool:
        snapshot = await self.graph.aget_state(self._config(case_id))
        return bool(snapshot.interrupts)

    async def resume(self, case_id: str, event: dict[str, Any]) -> bool:
        async with self._locks[case_id]:
            if not await self.waiting(case_id):
                return False
            await self._invoke(case_id, Command(resume={**event, "at": now()}))
            if event["type"] == "close":
                await index_case(self.store, await self.case(case_id), "you")
        return True

    async def retry(self, case_id: str) -> None:
        async with self._locks[case_id]:
            snapshot = await self.graph.aget_state(self._config(case_id))
            if snapshot.next and not snapshot.interrupts:
                await self._invoke(case_id, None)

    async def case(self, case_id: str) -> dict[str, Any]:
        snapshot = await self.graph.aget_state(self._config(case_id))
        return dict(snapshot.values)

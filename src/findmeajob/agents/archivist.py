from typing import Any, Literal

from langgraph.store.base import BaseStore
from langmem import create_manage_memory_tool
from pydantic import BaseModel

from findmeajob.agents.deps import Deps
from findmeajob.events import broker
from findmeajob.llm import ask
from findmeajob.memory import LESSONS, list_values
from findmeajob.state import CaseState

SYSTEM = (
    "You are Archivist. You keep the candidate's long-term memory. From a debrief, propose lessons worth keeping "
    "for future interviews and any real story the candidate told that their profile lacks. Drop anything that "
    "repeats an existing entry. Do not propose changes to the master CV."
)


class Proposal(BaseModel):
    kind: Literal["lesson", "story"]
    text: str


class Proposals(BaseModel):
    proposals: list[Proposal]


class Memory(BaseModel):
    kind: Literal["lesson", "story"]
    text: str
    status: Literal["proposed", "accepted", "dismissed"]
    case_id: str


def manage_tool(store: BaseStore) -> Any:
    return create_manage_memory_tool(namespace=LESSONS, schema=Memory, actions_permitted=("create",), store=store)


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    debrief = state["debriefs"][-1]
    existing = [entry["content"]["text"] for entry in await list_values(store, LESSONS)]
    found = await ask(
        deps.model,
        Proposals,
        SYSTEM,
        f"Debrief:\n{debrief}\n\nExisting entries:\n" + ("\n".join(f"- {text}" for text in existing) or "- none"),
    )
    tool = manage_tool(store)
    for proposal in found.proposals:
        memory = Memory(kind=proposal.kind, text=proposal.text, status="proposed", case_id=state["case_id"])
        await tool.ainvoke({"action": "create", "content": memory})
    if found.proposals:
        broker.publish("profile", proposals=len(found.proposals))
    return {}


def route(state: CaseState) -> str:
    return "chaser" if state["event"]["type"] == "notes" else "wait"

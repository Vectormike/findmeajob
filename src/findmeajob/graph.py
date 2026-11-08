from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.store.base import BaseStore
from langgraph.types import interrupt

from findmeajob.agents import archivist, brief, chaser, clerk, courier, critic, judge, tailor
from findmeajob.agents.deps import Deps
from findmeajob.events import broker
from findmeajob.memory import index_case, now, set_status
from findmeajob.state import CaseState

Agent = Callable[[CaseState, Deps, BaseStore], Awaitable[dict[str, Any]]]
WAIT_ROUTES = {"mail": "courier", "notes": "critic", "approve": "outbox", "discard": "outbox", "close": END}


def wait(state: CaseState) -> dict[str, Any]:
    event = interrupt({"waiting_for": "mail, meeting notes, or a decision on the draft"})
    if event["type"] == "close":
        return {"event": event, "stage": "closed"}
    return {"event": event}


async def outbox(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    draft = state.get("draft")
    if state["event"]["type"] == "discard" or not draft:
        return {"draft": None}
    body = state["event"].get("body") or draft["body"]
    try:
        await deps.gmail.send_mail(draft["to"], draft["subject"], body, draft["thread_id"], draft["in_reply_to"])
    except Exception as error:
        await set_status(store, "gmail", False, f"the send flopped: {error}"[:300])
        return {"draft": {**draft, "body": body, "error": f"the send flopped: {error}"}}
    await set_status(store, "gmail", True, f"Sent to {draft['to']}")
    return {"draft": None, "sent": [{**draft, "body": body, "at": now()}]}


def node(name: str, agent: Agent, deps: Deps) -> Callable[..., Awaitable[dict[str, Any]]]:
    async def run(state: CaseState, *, store: BaseStore) -> dict[str, Any]:
        broker.publish("working", case_id=state["case_id"], agent=name)
        update = await agent(state, deps, store)
        merged: dict[str, Any] = {**state, **update}
        for key in ("mail", "debriefs", "sent"):
            merged[key] = state.get(key, []) + update.get(key, [])
        await index_case(store, merged, name)
        return {**update, "last_agent": name}

    return run


def build_graph(deps: Deps, checkpointer: Any, store: BaseStore) -> Any:
    graph = StateGraph(CaseState)
    agents: dict[str, Agent] = {
        "judge": judge.run,
        "tailor": tailor.run,
        "clerk": clerk.run,
        "courier": courier.run,
        "brief": brief.run,
        "critic": critic.run,
        "archivist": archivist.run,
        "chaser": chaser.run,
        "outbox": outbox,
    }
    for name, agent in agents.items():
        graph.add_node(name, node("chaser" if name == "outbox" else name, agent, deps))
    graph.add_node("wait", wait)

    graph.add_edge(START, "judge")
    graph.add_conditional_edges("judge", lambda s: END if s["stage"] == "skipped" else "tailor", ["tailor", END])
    graph.add_edge("tailor", "clerk")
    graph.add_conditional_edges("clerk", lambda s: "wait" if s["stage"] == "applied" else END, ["wait", END])
    graph.add_conditional_edges("wait", lambda s: WAIT_ROUTES[s["event"]["type"]], list(set(WAIT_ROUTES.values())))
    graph.add_conditional_edges("courier", courier.route, ["brief", "critic", "chaser", "wait"])
    graph.add_edge("critic", "archivist")
    graph.add_conditional_edges("archivist", archivist.route, ["chaser", "wait"])
    for name in ("brief", "chaser", "outbox"):
        graph.add_edge(name, "wait")
    return graph.compile(checkpointer=checkpointer, store=store)

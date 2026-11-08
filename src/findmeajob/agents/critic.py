import json
from typing import Any

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from findmeajob.agents.deps import Deps
from findmeajob.llm import ask
from findmeajob.memory import now
from findmeajob.state import CaseState

SYSTEM = (
    "You are Critic. You debrief a candidate after an interview or a rejection. Compare what happened, from the "
    "meeting notes or the feedback email, with the questions and answers the candidate prepared. Say what landed, "
    "what was thin, which prepared answers went unused, and what could have been better, quoting the notes. "
    "Lessons must be short, general rules the candidate can reuse in later interviews."
)


class Debrief(BaseModel):
    landed: list[str]
    thin: list[str]
    unused_answers: list[str]
    could_be_better: list[str]
    lessons: list[str] = Field(description="Reusable rules for future interviews")


def evidence(state: CaseState) -> tuple[str, str]:
    event = state["event"]
    if event["type"] == "notes":
        notes = event["notes"]
        text = (
            f"Meeting: {notes['title']} ({notes['start_time']})\nSummary: {notes['summary']}\n"
            f"Key questions: {json.dumps(notes['key_questions'])}\n"
            f"Action items: {json.dumps(notes['action_items'])}\n\n"
            f"Transcript:\n{notes['transcript']}"
        )
        return "meeting notes", text
    mail = state["mail"][-1]
    return "feedback email", f"From: {mail['from']}\nSubject: {mail['subject']}\n\n{mail['body']}"


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    source, text = evidence(state)
    prepared = (state.get("brief") or {}).get("questions", [])
    debrief = await ask(
        deps.model,
        Debrief,
        SYSTEM,
        f"Role: {state['posting'].get('title')} at {state['posting'].get('company')}\n\n"
        f"Prepared questions and answers:\n{json.dumps(prepared, indent=1) if prepared else 'none'}\n\n"
        f"From the {source}:\n{text}",
    )
    update: dict[str, Any] = {"debriefs": [{"source": source, "at": now(), **debrief.model_dump()}]}
    if state["event"]["type"] == "notes":
        update["stage"] = "debriefed"
    return update

from typing import Any, Literal

from langgraph.store.base import BaseStore
from pydantic import BaseModel

from findmeajob.agents.deps import Deps
from findmeajob.llm import ask
from findmeajob.state import CaseState

SYSTEM = (
    "You are Courier. You read one email about a job application and classify it. "
    "acknowledgment: an automatic or human note that the application was received. "
    "recruiter_reply: a recruiter or hiring manager writing about next steps or asking something. "
    "interview_invite: an invitation to interview. scheduling: arranging or moving an interview time. "
    "rejection: the application or interview did not succeed. offer: a job offer. "
    "feedback: comments on the candidate's interview or application. unrelated: none of these."
)

Category = Literal[
    "acknowledgment", "recruiter_reply", "interview_invite", "scheduling", "rejection", "offer", "feedback", "unrelated"
]

STAGES = {
    "acknowledgment": "acknowledged",
    "recruiter_reply": "in_conversation",
    "interview_invite": "interview",
    "scheduling": "interview",
    "rejection": "rejected",
    "offer": "offer",
}


class MailRead(BaseModel):
    category: Category
    summary: str
    needs_answer: bool
    has_feedback: bool
    interview_time: str = ""


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    message = state["event"]["message"]
    read = await ask(
        deps.model,
        MailRead,
        SYSTEM,
        f"Application: {state['posting'].get('title')} at {state['posting'].get('company')}\n\n"
        f"From: {message['from']}\nSubject: {message['subject']}\nDate: {message['date']}\n\n{message['body']}",
    )
    update: dict[str, Any] = {"mail": [{**message, **read.model_dump()}]}
    if read.category in STAGES:
        update["stage"] = STAGES[read.category]
    return update


def route(state: CaseState) -> str:
    mail = state["mail"][-1]
    category = mail["category"]
    if category in ("interview_invite", "scheduling") and not state.get("brief"):
        return "brief"
    if category == "feedback" or (category == "rejection" and mail["has_feedback"]):
        return "critic"
    if mail["needs_answer"] and category not in ("acknowledgment", "rejection", "unrelated"):
        return "chaser"
    return "wait"

from typing import Any

from langgraph.store.base import BaseStore
from pydantic import BaseModel

from findmeajob.agents.deps import Deps
from findmeajob.llm import ask
from findmeajob.memory import profile_context
from findmeajob.state import CaseState

SYSTEM = (
    "You are Chaser. You draft a short, warm, professional email from the candidate. Reply to what was asked, "
    "or thank the interviewers and mention one specific point from the conversation. Use only facts from the "
    "profile and the thread. Never commit the candidate to a time or decision the thread does not support; "
    "offer options instead. Sign with the candidate's name."
)


class Draft(BaseModel):
    body: str


def recipient(state: CaseState) -> dict[str, Any] | None:
    for mail in reversed(state.get("mail", [])):
        if mail.get("category") not in (None, "acknowledgment", "unrelated") and mail.get("from_email"):
            return mail
    return None


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    thanks = state["event"]["type"] == "notes"
    last = recipient(state)
    if not last:
        return {}
    if thanks:
        context = f"Write a thank-you after the interview. Meeting summary:\n{state['event']['notes']['summary']}"
    else:
        context = f"Reply to this email:\nFrom: {last['from']}\nSubject: {last['subject']}\n\n{last['body']}"
    draft = await ask(deps.model, Draft, SYSTEM, f"{context}\n\nProfile:\n{await profile_context(store)}")
    return {
        "draft": {
            "kind": "thank_you" if thanks else "reply",
            "to": last["from_email"],
            "subject": last["subject"],
            "body": draft.body,
            "thread_id": last.get("thread_id"),
            "in_reply_to": last.get("message_id"),
        }
    }

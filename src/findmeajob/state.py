import operator
from typing import Annotated, Any, TypedDict

OPEN_STAGES = ("applied", "acknowledged", "in_conversation", "interview", "debriefed", "offer")
INBOX_STAGES = (*OPEN_STAGES, "blocked")
STAGE_GROUPS = {
    "needs_you": ("blocked",),
    "applied": ("applied",),
    "acknowledged": ("acknowledged", "in_conversation"),
    "interview": ("interview",),
    "debrief": ("debriefed",),
}


class CaseState(TypedDict, total=False):
    case_id: str
    filters: dict[str, str]
    posting: dict[str, Any]
    stage: str
    last_agent: str
    fit: dict[str, Any]
    cv: dict[str, Any]
    application: dict[str, Any]
    event: dict[str, Any]
    mail: Annotated[list[dict[str, Any]], operator.add]
    brief: dict[str, Any]
    debriefs: Annotated[list[dict[str, Any]], operator.add]
    draft: dict[str, Any] | None
    sent: Annotated[list[dict[str, Any]], operator.add]


def posting_text(posting: dict[str, Any]) -> str:
    return (
        f"Title: {posting.get('title', '')}\nCompany: {posting.get('company', '')}\n"
        f"Location: {posting.get('location', '')}\nSalary: {posting.get('salary') or 'not stated'}\n"
        f"URL: {posting.get('url', '')}\n\n{posting.get('description', '')}"
    )

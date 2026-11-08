from typing import Any, Literal

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from findmeajob.agents.deps import Deps
from findmeajob.llm import ask
from findmeajob.memory import is_skipped, profile_context, read_profile
from findmeajob.state import CaseState, posting_text

SYSTEM = (
    "You are Judge. You decide whether a job seeker should apply to a posting, from their profile and master CV. "
    "Count a must-have as covered only when the profile or CV shows it. Recommend apply when the must-haves are "
    "covered, stretch when one or two are missing but the rest fits, and skip when the role is out of reach, "
    "the location or work authorization rules it out, or there are serious red flags."
)


class FitNote(BaseModel):
    must_haves_covered: list[str] = Field(description="Must-have requirements the profile shows")
    must_haves_missing: list[str] = Field(description="Must-have requirements the profile does not show")
    seniority: str = Field(description="How the role's level compares to the profile")
    location_and_pay: str
    red_flags: list[str]
    recommendation: Literal["apply", "stretch", "skip"]
    reason: str


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    posting = state["posting"]
    profile = await read_profile(store)
    if is_skipped(posting.get("company", ""), profile["skip_companies"]):
        note = {"recommendation": "skip", "reason": "The company is on your skip list.", "red_flags": []}
        return {"fit": note, "stage": "skipped"}
    note = await ask(
        deps.model,
        FitNote,
        SYSTEM,
        f"Profile:\n{await profile_context(store)}\n\nPosting:\n{posting_text(posting)}",
    )
    return {"fit": note.model_dump(), "stage": "skipped" if note.recommendation == "skip" else "judged"}

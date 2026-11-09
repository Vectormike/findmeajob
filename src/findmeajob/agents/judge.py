from typing import Any, Literal

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from findmeajob.agents.deps import Deps
from findmeajob.llm import ask
from findmeajob.memory import is_skipped, profile_context, read_profile
from findmeajob.state import CaseState, posting_text

SYSTEM = (
    "You are Judge. You decide whether a job seeker should apply to a posting, from their profile and master CV. "
    "Count a must-have as covered only when the profile or CV shows it. Split the must-haves into technical fit "
    "(skills, tools, languages, systems, domain, years and level of experience) and behavioural fit (ways of "
    "working, ownership, communication, collaboration, leadership, mentoring, handling ambiguity). Keep each item "
    "short and give each fit a one-sentence verdict. Recommend apply when the must-haves are covered, stretch when "
    "one or two are missing but the rest fits, and skip when the role is out of reach, the location or work "
    "authorization rules it out, or there are serious red flags."
)


class FitArea(BaseModel):
    verdict: str = Field(description="One sentence on how well this side fits")
    covered: list[str] = Field(description="Must-haves on this side the profile shows")
    missing: list[str] = Field(description="Must-haves on this side the profile does not show")


class FitNote(BaseModel):
    technical: FitArea
    behavioural: FitArea
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
    fit = {
        **note.model_dump(),
        "must_haves_covered": [*note.technical.covered, *note.behavioural.covered],
        "must_haves_missing": [*note.technical.missing, *note.behavioural.missing],
    }
    return {"fit": fit, "stage": "skipped" if note.recommendation == "skip" else "judged"}

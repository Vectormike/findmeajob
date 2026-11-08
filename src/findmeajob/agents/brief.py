from typing import Any

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from findmeajob.agents.deps import Deps
from findmeajob.llm import ask
from findmeajob.memory import profile_context
from findmeajob.state import CaseState, posting_text
from findmeajob.tools.jobs.listing import html_to_text

FIRST_QUESTION = "Tell me about yourself"

SYSTEM = (
    "You are Brief. You prepare a candidate for an interview. From the research, the posting, the tailored CV, "
    "and the profile, write the questions this interview is likely to ask and answer each one in the candidate's "
    f"voice. The first question is always '{FIRST_QUESTION}'. Base answers on the candidate's real experience and "
    "stories; never invent events, skills, employers, or metrics. Where the research shows a known question, use it."
)


class Claim(BaseModel):
    text: str
    source_url: str


class InterviewResearch(BaseModel):
    company: list[Claim] = Field(description="What the company does, recent news, culture")
    interview_process: list[Claim] = Field(description="Reported interview stages and format")
    reported_questions: list[Claim] = Field(description="Questions candidates report being asked")
    role: list[Claim] = Field(description="What the team and role involve")


class Answered(BaseModel):
    question: str
    answer: str
    why_asked: str


class InterviewPrep(BaseModel):
    questions: list[Answered]
    gaps_to_prepare: list[str] = Field(description="Requirements where the candidate's story is thin")
    questions_to_ask_them: list[str]


def tell_me_first(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    first = [q for q in questions if q["question"].strip().lower().startswith(FIRST_QUESTION.lower())]
    return first[:1] + [q for q in questions if q not in first[:1]]


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    posting = state["posting"]
    found = await deps.research(
        deps.model,
        f"Research the interview for {posting.get('title')} at {posting.get('company')}. Check Reddit, Glassdoor "
        "public pages, forums, news, the company's own posts, and the posting. Posting:\n" + posting_text(posting),
        InterviewResearch,
    )
    invite = state["mail"][-1] if state.get("mail") else {}
    prep = await ask(
        deps.model,
        InterviewPrep,
        SYSTEM,
        f"Research:\n{found.model_dump_json(indent=1)}\n\nInvite:\n{invite.get('body', '')}\n\n"
        f"Posting:\n{posting_text(posting)}\n\nTailored CV:\n{html_to_text(state['cv']['cv_html'])}\n\n"
        f"Profile:\n{await profile_context(store)}",
    )
    result = prep.model_dump()
    result["questions"] = tell_me_first(result["questions"])
    return {"brief": {"research": found.model_dump(), **result, "interview_time": invite.get("interview_time", "")}}

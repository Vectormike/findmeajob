from typing import Any

from pydantic import BaseModel, Field

from findmeajob.llm import ask
from findmeajob.memory import Story, is_skipped

SYSTEM = (
    "Copy facts from a CV into the fields. Use only words that appear in the CV. "
    "Leave a field empty when the CV does not say it. Never guess an email, phone, location, "
    "title, skill, date, employer, or story. titles is a comma-separated list of roles they held. "
    "links is the URLs on the CV, separated by spaces. stories are a few roles: title is the role "
    "and company, text is what the CV says they did. current_company is only the employer of the "
    "role that is still going, marked Present, Current, or with no end date. Leave it empty when every role has ended."
)


class CvFacts(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: str = ""
    titles: str = ""
    skills: list[str] = Field(default_factory=list)
    work_authorization: str = ""
    current_company: str = ""
    stories: list[Story] = Field(default_factory=list)


def _said(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def merge_facts(profile: dict[str, Any], facts: CvFacts) -> dict[str, Any]:
    data = facts.model_dump()
    current = data.pop("current_company").strip()
    found = {key: value for key, value in data.items() if _said(value)}
    merged = {**profile, **found}
    if current and not is_skipped(current, merged["skip_companies"]):
        merged["skip_companies"] = [*merged["skip_companies"], current]
    return merged


async def read_cv(model: Any, text: str) -> CvFacts:
    return await ask(model, CvFacts, SYSTEM, text)

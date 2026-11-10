import json
import re
from pathlib import Path
from typing import Any, Literal

from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from findmeajob.agents.deps import Deps
from findmeajob.events import broker
from findmeajob.llm import ask
from findmeajob.memory import now, profile_context, set_status
from findmeajob.state import CaseState, posting_text
from findmeajob.tools.browser import Blocked
from findmeajob.tools.chrome import FILL_TIMEOUT_SECONDS, NETWORK_HICCUPS
from findmeajob.tools.jobs.listing import html_to_text

SALARY_FIELD = re.compile(r"salary|compensation|pay|remuneration|expected", re.I)
TRANSIENT = (
    "has been closed",
    "Target closed",
    "frame was detached",
    "Execution context was destroyed",
    *NETWORK_HICCUPS,
)
MAX_STEPS = 10
MAX_VALIDATION_RETRIES = 2

SYSTEM = (
    "You are Clerk. You answer every field of a job application form for the candidate, without asking them. "
    "Use the profile for personal facts, the tailored CV for experience, and the posting for role details. "
    "For salary, give the figure from the industry range provided, in the form's expected format. "
    "For market or role questions, answer from public industry knowledge. For behavioural questions, tell a "
    "profile story or the closest real experience from the CV; never invent events, skills, employers, or dates. "
    "For a select or radio field, the value must be one of its option labels. For a checkbox, answer yes or no. "
    "Use YYYY-MM-DD for date fields unless the label explicitly requests another format. "
    "Skip file fields. Set grounded to false only when a personal fact the form asks for is absent from the profile."
)


class SalaryRange(BaseModel):
    low: int
    high: int
    currency: str
    period: Literal["year", "month", "hour"]
    figure: int = Field(description="The figure to put on the form, inside the range")
    sources: list[str] = Field(description="URLs the range came from")


class FieldAnswer(BaseModel):
    field_id: str
    value: str
    source: Literal["profile", "cv", "posting", "industry", "salary_range"]
    grounded: bool


class FormAnswers(BaseModel):
    answers: list[FieldAnswer]


async def salary_range(deps: Deps, state: CaseState) -> SalaryRange:
    posting = state["posting"]
    filters = state.get("filters", {})
    task = (
        f"Find the published salary range for a {posting.get('title')} with {filters.get('skill') or 'this'} "
        f"skills in {filters.get('region') or posting.get('location') or 'the posting region'}. "
        f"Arrangement: {filters.get('arrangement') or 'any'}. Use salary surveys, job boards, and pay sites. "
        "Pick a figure in the upper half of the range."
    )
    return await deps.research(deps.model, task, SalaryRange)


async def answer(
    deps: Deps,
    store: BaseStore,
    state: CaseState,
    fields: list[dict[str, Any]],
    salary: SalaryRange | None = None,
    errors: list[str] | None = None,
) -> tuple[list[dict[str, Any]], SalaryRange | None]:
    if salary is None and any(SALARY_FIELD.search(field["label"]) for field in fields if field["type"] != "file"):
        salary = await salary_range(deps, state)
    user = (
        f"Form fields:\n{json.dumps(fields, indent=1)}\n\nProfile:\n{await profile_context(store)}\n\n"
        f"Tailored CV:\n{html_to_text(state['cv']['cv_html'])}\n\nPosting:\n{posting_text(state['posting'])}\n\n"
        f"Industry salary range: {salary.model_dump_json() if salary else 'not needed'}\n\n"
        f"Validation errors to correct: {json.dumps(errors or [])}"
    )
    answers = await ask(deps.model, FormAnswers, SYSTEM, user)
    return [a.model_dump() for a in answers.answers], salary


def missing_facts(fields: list[dict[str, Any]], answers: list[dict[str, Any]]) -> list[str]:
    required = {field["id"]: field["label"] for field in fields if field.get("required") and field["type"] != "file"}
    answered = {answer["field_id"]: answer for answer in answers}
    return [label for field_id, label in required.items() if not answered.get(field_id, {}).get("grounded")]


def transient(error: Exception) -> bool:
    text = str(error)
    return any(token in text for token in TRANSIENT)


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    posting = state["posting"]
    url = posting.get("apply_url") or posting["url"]
    application: dict[str, Any] = {"url": url, "at": now()}
    if not deps.chrome:
        return {
            "application": {**application, "blocked": "chrome isn't set up, so clerk can't fill anything."},
            "stage": "blocked",
        }
    def notify(waiting: bool) -> None:
        broker.publish("captcha", case_id=state["case_id"], waiting=waiting)

    for attempt in (1, 2):
        try:
            async with deps.chrome.fill_form(url, state["case_id"], notify) as session:
                steps: list[dict[str, Any]] = []
                all_fields: list[dict[str, Any]] = []
                all_answers: list[dict[str, Any]] = []
                salary: SalaryRange | None = None
                repeats: dict[str, int] = {}
                validation_errors: list[str] = []
                validation_retries = 0
                for step_number in range(1, MAX_STEPS + 1):
                    fields = await session.fields()
                    signature = json.dumps([(field["type"], field["label"]) for field in fields])
                    repeats[signature] = repeats.get(signature, 0) + 1
                    if repeats[signature] > MAX_VALIDATION_RETRIES + 1:
                        raise Blocked("the form got stuck on the same step after multiple fixes.")

                    answers: list[dict[str, Any]] = []
                    if fields:
                        answers, salary = await answer(deps, store, state, fields, salary, validation_errors)
                        missing = missing_facts(fields, answers)
                        if missing:
                            joined = ", ".join(missing)
                            raise Blocked(f"your profile is missing {joined}. add it and retry, we don't invent stuff.")
                        await session.fill(
                            fields, {item["field_id"]: item["value"] for item in answers}, Path(state["cv"]["pdf"])
                        )
                    outcome = await session.advance()
                    steps.append(
                        {
                            "number": step_number,
                            "fields": fields,
                            "answers": answers,
                            "outcome": outcome["status"],
                            "errors": outcome.get("errors", []),
                        }
                    )
                    if outcome["status"] == "validation":
                        validation_retries += 1
                        if validation_retries > MAX_VALIDATION_RETRIES:
                            raise Blocked("the form kept rejecting its answers: " + "; ".join(outcome["errors"])[:240])
                        validation_errors = outcome["errors"]
                        continue

                    validation_errors = []
                    validation_retries = 0
                    all_fields.extend(fields)
                    all_answers.extend(answers)
                    if outcome["status"] == "submitted":
                        application["confirmation"] = outcome["confirmation"]
                        break
                    if outcome["status"] == "unconfirmed":
                        raise Blocked("the form was sent, but the site did not show a reliable confirmation.")
                else:
                    raise Blocked(f"the application exceeded {MAX_STEPS} steps, so Clerk stopped safely.")
                application.update(
                    fields=all_fields,
                    answers=all_answers,
                    salary=salary.model_dump() if salary else None,
                    steps=steps,
                )
            break
        except Blocked as reason:
            await set_status(store, "chrome", True, f"Blocked on {url}")
            return {"application": {**application, "blocked": str(reason)}, "stage": "blocked"}
        except TimeoutError:
            stuck = f"the page stopped responding for {FILL_TIMEOUT_SECONDS // 60} minutes, so Clerk let go. retry it."
            await set_status(store, "chrome", False, stuck)
            return {"application": {**application, "blocked": stuck}, "stage": "blocked"}
        except Exception as error:
            if attempt == 1 and transient(error):
                continue
            await set_status(store, "chrome", False, f"chrome crashed out: {error}"[:300])
            return {"application": {**application, "blocked": f"chrome crashed out: {error}"}, "stage": "blocked"}
    await set_status(store, "chrome", True, f"Submitted {url}")
    return {"application": application, "stage": "applied"}

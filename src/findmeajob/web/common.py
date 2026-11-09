import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from fastapi import HTTPException, Request

from findmeajob.memory import CASES, STATUS, list_values
from findmeajob.workflow import Workflow

log = logging.getLogger(__name__)

AGENTS = {
    "scout": "Sweeps job boards for your region, skill, and arrangement and opens a case per new vacancy.",
    "judge": "Writes a fit note and decides apply, stretch, or skip.",
    "tailor": "Writes a CV for the job's requirements from your master CV and profile.",
    "clerk": "Fills the application form in Chrome, answers every question, and submits.",
    "courier": "Reads Gmail, files each email on its case, and routes it.",
    "brief": "Researches the interview and answers the likely questions.",
    "critic": "Debriefs from meeting notes or feedback: what landed and what could be better.",
    "chaser": "Drafts replies and thank-yous, and sends only after you approve.",
    "archivist": "Keeps your profile and proposes lessons from each debrief.",
}


def workflow_of(request: Request) -> Workflow:
    return request.app.state.workflow


def background(request: Request, work: Coroutine[Any, Any, Any]) -> None:
    task = asyncio.create_task(work)
    tasks: set[asyncio.Task[Any]] = request.app.state.tasks
    tasks.add(task)

    def done(finished: asyncio.Task[Any]) -> None:
        tasks.discard(finished)
        if not finished.cancelled() and finished.exception():
            log.error("Background work failed", exc_info=finished.exception())

    task.add_done_callback(done)


async def all_cases(workflow: Workflow) -> list[dict[str, Any]]:
    cases = await list_values(workflow.store, CASES)
    return sorted(cases, key=lambda case: case.get("updated_at", ""), reverse=True)


async def statuses(workflow: Workflow) -> dict[str, dict[str, Any]]:
    return {item["key"]: item for item in await list_values(workflow.store, STATUS)}


async def case_detail(workflow: Workflow, case_id: str) -> dict[str, Any]:
    values = await workflow.case(case_id)
    if not values:
        raise HTTPException(404, "that case doesn't exist. wrong link, or it already left the chat.")
    item = await workflow.store.aget(CASES, case_id)
    case = {k: v for k, v in values.items() if k != "cv"}
    cv = values.get("cv")
    if cv:
        case["cv"] = {k: v for k, v in cv.items() if k not in ("cv_html", "pdf")} | {"has_pdf": bool(cv.get("pdf"))}
    return {
        "case": case,
        "index": item.value if item else {},
        "waiting": await workflow.waiting(case_id),
        "retryable": await workflow.retryable(case_id),
    }

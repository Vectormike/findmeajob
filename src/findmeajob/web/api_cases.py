from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from playwright.async_api import Error as PlaywrightError
from pydantic import BaseModel, Field

from findmeajob.agents import inbox, scout
from findmeajob.memory import UNMATCHED, FormFact, list_values, read_profile, write_profile
from findmeajob.state import INBOX_STAGES, STAGE_GROUPS
from findmeajob.tools.jobs.listing import ARRANGEMENTS
from findmeajob.tools.jobs.regions import groups
from findmeajob.web.common import all_cases, background, case_detail, statuses, workflow_of

router = APIRouter(prefix="/api")


class ScoutRun(BaseModel):
    region: str
    skill: str
    arrangement: Literal[ARRANGEMENTS] = "any"  # type: ignore[valid-type]
    title_only: bool = False


class NewPosting(BaseModel):
    url: str


class Approval(BaseModel):
    body: str = ""


class Assignment(BaseModel):
    case_id: str


class Facts(BaseModel):
    facts: list[FormFact] = Field(min_length=1, max_length=20)


class LiveAction(BaseModel):
    kind: Literal["click", "type", "key", "scroll"]
    x: float = Field(0, ge=0, le=1)
    y: float = Field(0, ge=0, le=1)
    text: str = Field("", max_length=200)
    key: Literal["Enter", "Tab", "Backspace", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"] = "Enter"
    dy: float = Field(0, ge=-2000, le=2000)


def live_page(request: Request, case_id: str) -> Any:
    chrome = workflow_of(request).deps.chrome
    page = chrome.live.get(case_id) if chrome else None
    if not page:
        raise HTTPException(404, "nothing on this case is waiting for a captcha.")
    return page


@router.get("/inbox")
async def inbox_view(request: Request) -> dict[str, Any]:
    workflow = workflow_of(request)
    live = workflow.deps.chrome.live if workflow.deps.chrome else {}
    cases = [
        {**c, "captcha": c["key"] in live} for c in await all_cases(workflow) if c.get("stage") in INBOX_STAGES
    ]
    counts = {group: sum(c["stage"] in stages for c in cases) for group, stages in STAGE_GROUPS.items()}
    return {"cases": cases, "counts": counts, "unmatched": await list_values(workflow.store, UNMATCHED)}


@router.get("/cases")
async def cases_view(request: Request) -> dict[str, Any]:
    workflow = workflow_of(request)
    found = await statuses(workflow)
    return {
        "cases": await all_cases(workflow),
        "scout": found.get("scout"),
        "arrangements": ARRANGEMENTS,
        "regions": groups(),
    }


@router.get("/cases/{case_id}")
async def case_view(request: Request, case_id: str) -> dict[str, Any]:
    return await case_detail(workflow_of(request), case_id)


@router.post("/scout", status_code=202)
async def run_scout(request: Request, run: ScoutRun) -> dict[str, str]:
    settings = request.app.state.settings
    background(
        request,
        scout.run(
            workflow_of(request),
            run.region.strip(),
            run.skill.strip(),
            run.arrangement,
            settings.scout_max_cases,
            settings.the_muse_api_key,
            run.title_only,
        ),
    )
    return {"status": "running"}


@router.post("/cases", status_code=202)
async def add_posting(request: Request, posting: NewPosting) -> dict[str, str]:
    background(request, scout.add_link(workflow_of(request), posting.url.strip()))
    return {"status": "running"}


async def act(request: Request, case_id: str, event: dict[str, Any]) -> dict[str, Any]:
    workflow = workflow_of(request)
    if not await workflow.resume(case_id, event):
        raise HTTPException(409, "this case isn't waiting on you rn. the agents still got it.")
    return await case_detail(workflow, case_id)


@router.post("/cases/{case_id}/approve")
async def approve(request: Request, case_id: str, approval: Approval) -> dict[str, Any]:
    return await act(request, case_id, {"type": "approve", "body": approval.body.strip()})


@router.post("/cases/{case_id}/discard")
async def discard(request: Request, case_id: str) -> dict[str, Any]:
    return await act(request, case_id, {"type": "discard"})


@router.post("/cases/{case_id}/close")
async def close(request: Request, case_id: str) -> dict[str, Any]:
    return await act(request, case_id, {"type": "close"})


@router.post("/cases/{case_id}/retry", status_code=202)
async def retry(request: Request, case_id: str) -> dict[str, str]:
    background(request, workflow_of(request).retry(case_id))
    return {"status": "running"}


@router.post("/cases/{case_id}/retry/{agent}", status_code=202)
async def retry_agent(request: Request, case_id: str, agent: str) -> dict[str, str]:
    workflow = workflow_of(request)
    if agent not in await workflow.retryable(case_id):
        raise HTTPException(409, f"{agent} can't be retried on this case right now.")
    background(request, workflow.rerun(case_id, agent))
    return {"status": "running"}


@router.post("/cases/{case_id}/facts", status_code=202)
async def add_facts(request: Request, case_id: str, facts: Facts) -> dict[str, str]:
    workflow = workflow_of(request)
    if "clerk" not in await workflow.retryable(case_id):
        raise HTTPException(409, "clerk can't be retried on this case right now.")
    posting = (await workflow.case(case_id))["posting"]
    job = ", ".join(part for part in (posting.get("company"), posting.get("location")) if part)
    answered = {fact.question for fact in facts.facts}
    profile = await read_profile(workflow.store)
    kept = [f for f in profile["form_facts"] if not (f["question"] in answered and f["job"] == job)]
    added = [{**fact.model_dump(), "job": job} for fact in facts.facts]
    await write_profile(workflow.store, {**profile, "form_facts": [*kept, *added]})
    return await retry_agent(request, case_id, "clerk")


@router.get("/cases/{case_id}/live.jpg")
async def live_frame(request: Request, case_id: str) -> Response:
    try:
        image = await live_page(request, case_id).screenshot(type="jpeg", quality=70)
    except PlaywrightError as error:
        raise HTTPException(409, "the application page closed.") from error
    return Response(image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/cases/{case_id}/live")
async def live_act(request: Request, case_id: str, action: LiveAction) -> dict[str, str]:
    page = live_page(request, case_id)
    size = page.viewport_size or {"width": 1280, "height": 720}
    try:
        if action.kind == "click":
            await page.mouse.click(action.x * size["width"], action.y * size["height"])
        elif action.kind == "type":
            await page.keyboard.type(action.text)
        elif action.kind == "key":
            await page.keyboard.press(action.key)
        else:
            await page.mouse.wheel(0, action.dy)
    except PlaywrightError as error:
        raise HTTPException(409, "the application page closed.") from error
    return {"status": "ok"}


@router.get("/cases/{case_id}/cv")
async def cv_html(request: Request, case_id: str) -> HTMLResponse:
    cv = (await workflow_of(request).case(case_id)).get("cv")
    if not cv:
        raise HTTPException(404, "no cv yet. tailor is still cooking.")
    return HTMLResponse(cv["cv_html"], headers={"Content-Security-Policy": "script-src 'none'"})


@router.get("/cases/{case_id}/cv.pdf")
async def cv_pdf(request: Request, case_id: str, download: bool = False) -> FileResponse:
    cv = (await workflow_of(request).case(case_id)).get("cv") or {}
    if not cv.get("pdf") or not Path(cv["pdf"]).exists():
        raise HTTPException(404, "no pdf yet. give it a sec.")
    filename = f"cv-{case_id}.pdf" if download else None
    return FileResponse(cv["pdf"], media_type="application/pdf", filename=filename)


@router.post("/unmatched/{key}/assign", status_code=202)
async def assign(request: Request, key: str, assignment: Assignment) -> dict[str, str]:
    workflow = workflow_of(request)
    if not await workflow.waiting(assignment.case_id):
        raise HTTPException(409, "that case isn't sitting around waiting for mail.")
    background(request, inbox.assign(workflow, key, assignment.case_id))
    return {"status": "running"}


@router.delete("/unmatched/{key}")
async def dismiss(request: Request, key: str) -> dict[str, str]:
    await workflow_of(request).store.adelete(UNMATCHED, key)
    return {"status": "dismissed"}

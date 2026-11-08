from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from findmeajob.agents import inbox, scout
from findmeajob.memory import UNMATCHED, list_values
from findmeajob.state import OPEN_STAGES, STAGE_GROUPS
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


@router.get("/inbox")
async def inbox_view(request: Request) -> dict[str, Any]:
    workflow = workflow_of(request)
    cases = [c for c in await all_cases(workflow) if c.get("stage") in OPEN_STAGES]
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

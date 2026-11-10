import asyncio
import hashlib
import logging
from typing import Any

from pydantic import BaseModel

from findmeajob.events import broker
from findmeajob.llm import ask
from findmeajob.memory import CASES, index_case, is_skipped, list_values, now, read_profile, set_status
from findmeajob.tools.jobs import search_job_batches
from findmeajob.tools.jobs.listing import Listing
from findmeajob.workflow import Workflow

log = logging.getLogger(__name__)
SHORT_DESCRIPTION = 400
OPEN_AT_ONCE = 4


class Posting(BaseModel):
    title: str
    company: str
    location: str
    description: str
    apply_url: str
    salary: str


def case_id_for(*parts: str) -> str:
    return hashlib.sha1("|".join(part.strip().lower() for part in parts).encode()).hexdigest()[:12]


def job_key(company: str, title: str) -> str:
    return f"{company.strip().lower()}|{title.strip().lower()}"


def _detail(found: int, opened: int, rediscovered: int, skill: str, region: str, arrangement: str) -> str:
    fresh = "none new" if opened == 0 else f"{opened} new"
    familiar = f", {rediscovered} already here" if rediscovered else ""
    return f"clocked {found}, {fresh}{familiar}. {skill} / {region} / {arrangement}"


async def _fill(workflow: Workflow, listing: Listing, posting: dict[str, Any]) -> None:
    if len(listing.description) >= SHORT_DESCRIPTION:
        return
    try:
        posting["description"] = (await workflow.deps.fetch_page(listing.url))["text"]
    except Exception:
        log.warning("Could not read %s", listing.url)


async def _open(
    workflow: Workflow,
    case_id: str,
    posting: dict[str, Any],
    filters: dict[str, str],
    listing: Listing,
    gate: asyncio.Semaphore,
) -> None:
    async with gate:
        await _fill(workflow, listing, posting)
        await workflow.start(case_id, posting, filters)


async def run(
    workflow: Workflow,
    region: str,
    skill: str,
    arrangement: str,
    limit: int,
    the_muse_api_key: str | None = None,
    title_only: bool = False,
) -> int:
    filters = {"region": region, "skill": skill, "arrangement": arrangement}
    run_id = now()
    broker.publish("working", case_id="", agent="scout", detail=f"{skill} / {region} / {arrangement}")
    skip = (await read_profile(workflow.store))["skip_companies"]
    cases = await list_values(workflow.store, CASES)
    stored = {case["key"] for case in cases}
    known = {job_key(case.get("company", ""), case.get("title", "")): case["key"] for case in cases}
    existing = set(stored)
    rediscovered: list[str] = []
    picked: list[tuple[str, dict[str, Any], Listing]] = []
    found = 0
    try:
        async for listings in search_job_batches(region, skill, arrangement, the_muse_api_key, title_only):
            found += len(listings)
            batch: list[tuple[str, dict[str, Any], Listing]] = []
            for listing in listings:
                if len(picked) + len(batch) >= limit:
                    break
                case_id = known.get(job_key(listing.company, listing.title)) or case_id_for(
                    region, skill, arrangement, listing.company, listing.title
                )
                if is_skipped(listing.company, skip):
                    continue
                if case_id in stored:
                    if len(rediscovered) < limit and case_id not in rediscovered:
                        rediscovered.append(case_id)
                        broker.publish("discovered", case_id=case_id)
                    continue
                if case_id in existing:
                    continue
                existing.add(case_id)
                batch.append((case_id, listing.model_dump(), listing))
            await asyncio.gather(
                *(
                    index_case(
                        workflow.store,
                        {"case_id": case_id, "posting": posting, "filters": filters, "stage": "opening", "mail": []},
                        "scout",
                    )
                    for case_id, posting, _ in batch
                )
            )
            picked.extend(batch)
    except Exception as error:
        await set_status(workflow.store, "scout", False, f"the sweep flopped: {error}"[:300])
        raise
    await set_status(
        workflow.store,
        "scout",
        True,
        _detail(found, len(picked), len(rediscovered), skill, region, arrangement),
        run_id=run_id,
        case_ids=[*rediscovered, *(case_id for case_id, _, _ in picked)],
    )
    gate = asyncio.Semaphore(OPEN_AT_ONCE)
    results = await asyncio.gather(
        *(_open(workflow, case_id, posting, filters, listing, gate) for case_id, posting, listing in picked),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            log.error("Opening a case flopped", exc_info=result)
    return len(picked)


async def add_link(workflow: Workflow, url: str) -> str:
    page = await workflow.deps.fetch_page(url)
    posting = await ask(
        workflow.deps.model,
        Posting,
        "Extract the job posting from this page. Copy the description text as written. "
        "Use an empty string for anything the page does not state.",
        f"URL: {url}\nTitle: {page['title']}\n\n{page['text']}",
    )
    case_id = case_id_for(url)
    if not await workflow.store.aget(CASES, case_id):
        details = {**posting.model_dump(), "url": url, "source": "link"}
        await workflow.start(case_id, {**details, "apply_url": details["apply_url"] or url}, {})
    return case_id

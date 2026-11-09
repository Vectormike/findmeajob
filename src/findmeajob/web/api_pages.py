import asyncio
import hmac
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from findmeajob.agents import inbox
from findmeajob.events import broker
from findmeajob.memory import LESSONS, Profile, list_values, read_profile, set_status, write_profile
from findmeajob.profile_from_cv import merge_facts, read_cv
from findmeajob.tools.documents import extract_text
from findmeajob.tools.gmail import Gmail, authorize
from findmeajob.tools.readai import read_meeting_notes
from findmeajob.web.common import AGENTS, all_cases, background, statuses, workflow_of

router = APIRouter()
KEEPALIVE_SECONDS = 20
MAX_CV_BYTES = 5 * 1024 * 1024

INTEGRATIONS = [
    {
        "key": "gmail",
        "name": "Gmail",
        "agents": ["courier", "chaser"],
        "job": "Reads job mail and sends approved replies.",
    },
    {"key": "readai", "name": "Read AI", "agents": ["critic"], "job": "Sends meeting notes after each interview."},
    {"key": "chrome", "name": "Chrome", "agents": ["clerk"], "job": "Fills and submits application forms."},
    {"key": "xai", "name": "Grok", "agents": list(AGENTS), "job": "The model every agent thinks with."},
]


@router.get("/api/agents")
async def agents_view(request: Request) -> list[dict[str, Any]]:
    cases = await all_cases(workflow_of(request))
    cards = []
    for name, job in AGENTS.items():
        written = [case for case in cases if case.get("last_agent") == name]
        cards.append({"name": name, "job": job, "last": written[0] if written else None, "count": len(written)})
    return cards


@router.get("/api/profile")
async def profile_view(request: Request) -> dict[str, Any]:
    store = workflow_of(request).store
    entries = await list_values(store, LESSONS)
    memory = [{"key": entry["key"], **entry["content"]} for entry in entries]
    return {"profile": await read_profile(store), "memory": memory}


@router.put("/api/profile")
async def save_profile(request: Request, profile: Profile) -> dict[str, Any]:
    await write_profile(workflow_of(request).store, profile.model_dump())
    return await profile_view(request)


@router.put("/api/profile/cv")
async def upload_cv(request: Request, name: str) -> dict[str, Any]:
    data = await request.body()
    if len(data) > MAX_CV_BYTES:
        raise HTTPException(413, "5mb max and this file said watch me. shrink it and pull up again.")
    try:
        text = extract_text(name, data)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    workflow = workflow_of(request)
    profile = {**await read_profile(workflow.store), "master_cv": text, "master_cv_file": name}
    try:
        profile = merge_facts(profile, await read_cv(workflow.deps.model, text))
    except Exception as error:
        await write_profile(workflow.store, profile)
        raise HTTPException(502, "saved the file, but reading it into the form flopped. try again.") from error
    await write_profile(workflow.store, profile)
    return await profile_view(request)


@router.post("/api/profile/memory/{key}/{decision}")
async def decide_memory(request: Request, key: str, decision: Literal["accepted", "dismissed"]) -> dict[str, Any]:
    store = workflow_of(request).store
    item = await store.aget(LESSONS, key)
    if not item:
        raise HTTPException(404, "that note already dipped. refresh, it's gone.")
    content = {**item.value["content"], "status": decision}
    if decision == "accepted" and content["kind"] == "story":
        profile = await read_profile(store)
        title = content["text"].split(".")[0][:60]
        await write_profile(
            store, {**profile, "stories": [*profile["stories"], {"title": title, "text": content["text"]}]}
        )
    await store.aput(LESSONS, key, {**item.value, "content": content})
    return await profile_view(request)


@router.get("/api/integrations")
async def integrations_view(request: Request) -> list[dict[str, Any]]:
    workflow = workflow_of(request)
    settings = request.app.state.settings
    found = await statuses(workflow)
    configured = {
        "gmail": workflow.deps.gmail is not None or settings.gmail_credentials_file.exists(),
        "readai": bool(settings.readai_webhook_secret),
        "chrome": workflow.deps.chrome is not None,
        "xai": workflow.deps.model is not None,
    }
    active = {
        "gmail": workflow.deps.gmail is not None,
        "readai": bool(settings.readai_webhook_secret),
        "chrome": workflow.deps.chrome is not None,
        "xai": workflow.deps.model is not None,
    }
    return [
        {
            **card,
            "configured": configured[card["key"]],
            "active": active[card["key"]],
            "status": found.get(card["key"]),
        }
        for card in INTEGRATIONS
    ]


@router.post("/api/integrations/{key}/test")
async def test_integration(request: Request, key: str) -> dict[str, Any]:
    workflow = workflow_of(request)
    settings = request.app.state.settings
    try:
        if key == "gmail":
            if not workflow.deps.gmail:
                raise RuntimeError("Gmail isn't connected yet.")
            detail = f"Connected as {await workflow.deps.gmail.healthcheck()}"
        elif key == "readai":
            if not settings.readai_webhook_secret:
                raise RuntimeError("READAI_WEBHOOK_SECRET is missing.")
            detail = "Webhook is configured and ready for Read AI."
        elif key == "chrome":
            if not workflow.deps.chrome:
                raise RuntimeError("Clerk's browser isn't available.")
            await workflow.deps.chrome.healthcheck()
            detail = "Headless Clerk browser passed its check."
        elif key == "xai":
            if not workflow.deps.model:
                raise RuntimeError("XAI_API_KEY is missing.")
            detail = f"{settings.xai_model} is configured."
        else:
            raise HTTPException(404, "that integration doesn't exist.")
    except HTTPException:
        raise
    except Exception as error:
        await set_status(workflow.store, key, False, str(error)[:300])
        raise HTTPException(409, str(error)) from error
    await set_status(workflow.store, key, True, detail)
    return {"status": "connected", "detail": detail}


@router.post("/api/integrations/gmail/connect")
async def connect_gmail(request: Request) -> dict[str, str]:
    workflow = workflow_of(request)
    settings = request.app.state.settings
    if workflow.deps.gmail:
        return {"status": "connected", "detail": f"Connected as {await workflow.deps.gmail.healthcheck()}"}
    if not settings.gmail_credentials_file.exists():
        detail = f"Add your Google OAuth client file at {settings.gmail_credentials_file} first."
        await set_status(workflow.store, "gmail", False, detail)
        raise HTTPException(409, detail)
    try:
        await asyncio.to_thread(authorize, settings.gmail_credentials_file, settings.gmail_token_file)
        workflow.deps.gmail = Gmail(settings.gmail_token_file)
        email = await workflow.deps.gmail.healthcheck()
    except Exception as error:
        await set_status(workflow.store, "gmail", False, f"Gmail connection failed: {error}"[:300])
        raise HTTPException(409, f"Gmail connection failed: {error}") from error
    await set_status(workflow.store, "gmail", True, f"Connected as {email}")
    if not request.app.state.gmail_poller:
        request.app.state.gmail_poller = asyncio.create_task(
            inbox.poll_forever(workflow, settings.courier_poll_seconds)
        )
    return {"status": "connected", "detail": f"Connected as {email}"}


@router.get("/api/events", response_class=EventSourceResponse)
async def events(request: Request) -> AsyncIterator[ServerSentEvent]:
    async with broker.subscribe() as queue:
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(queue.get(), KEEPALIVE_SECONDS)
            except TimeoutError:
                yield ServerSentEvent(comment="keepalive")
                continue
            yield ServerSentEvent(event=event["kind"], data=event)


@router.post("/webhooks/readai/{secret}")
async def readai_webhook(request: Request, secret: str) -> dict[str, str]:
    expected = request.app.state.settings.readai_webhook_secret
    if not expected or not hmac.compare_digest(secret, expected):
        raise HTTPException(404)
    workflow = workflow_of(request)
    notes = read_meeting_notes(await request.json())
    await set_status(workflow.store, "readai", True, f"Notes for {notes['title']}")
    background(request, inbox.take_notes(workflow, notes))
    return {"status": "received"}

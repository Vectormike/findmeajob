import asyncio
import logging
import re
import time
from typing import Any

from findmeajob.events import broker
from findmeajob.memory import CASES, COURIER, UNMATCHED, list_values, now, set_status
from findmeajob.state import OPEN_STAGES
from findmeajob.workflow import Workflow

log = logging.getLogger(__name__)
FIRST_LOOKBACK_SECONDS = 7 * 24 * 3600
SEEN_KEPT = 500


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def score(case: dict[str, Any], emails: list[str], text: str, thread_id: str | None) -> int:
    company = squash(case.get("company", ""))
    if thread_id and thread_id in case.get("threads", []):
        return 10
    points = 0
    if any(email.lower() in case.get("contacts", []) for email in emails):
        points += 5
    if len(company) >= 3:
        if any(company in squash(email.split("@")[-1]) for email in emails):
            points += 3
        if company in squash(text):
            points += 2
            points += squash(case.get("title", "")) in squash(text)
    return points


def match(cases: list[dict[str, Any]], emails: list[str], text: str, thread_id: str | None = None) -> str | None:
    scored = sorted(((score(case, emails, text, thread_id), case["key"]) for case in cases), reverse=True)
    if not scored or scored[0][0] == 0 or (len(scored) > 1 and scored[1][0] == scored[0][0]):
        return None
    return scored[0][1]


async def open_cases(workflow: Workflow) -> list[dict[str, Any]]:
    return [case for case in await list_values(workflow.store, CASES) if case.get("stage") in OPEN_STAGES]


async def deliver(workflow: Workflow, key: str, event: dict[str, Any], case_id: str | None) -> None:
    if case_id and await workflow.resume(case_id, event):
        return
    await workflow.store.aput(UNMATCHED, key, {"event": event, "at": now()})
    broker.publish("unmatched", key=key)


async def take_mail(workflow: Workflow, message: dict[str, Any]) -> None:
    text = f"{message['from']}\n{message['subject']}\n{message['body'][:3000]}"
    case_id = match(await open_cases(workflow), [message["from_email"]], text, message["thread_id"])
    await deliver(workflow, f"mail-{message['id']}", {"type": "mail", "message": message}, case_id)


async def take_notes(workflow: Workflow, notes: dict[str, Any]) -> None:
    emails = [person["email"] for person in notes["participants"] if person.get("email")]
    case_id = match(await open_cases(workflow), emails, f"{notes['title']}\n{notes['summary']}")
    await deliver(workflow, f"notes-{notes['session_id']}", {"type": "notes", "notes": notes}, case_id)


async def assign(workflow: Workflow, key: str, case_id: str) -> bool:
    item = await workflow.store.aget(UNMATCHED, key)
    if not item or not await workflow.resume(case_id, item.value["event"]):
        return False
    await workflow.store.adelete(UNMATCHED, key)
    return True


async def poll(workflow: Workflow) -> int:
    cursor = await workflow.store.aget(COURIER, "cursor")
    state = cursor.value if cursor else {"after": int(time.time()) - FIRST_LOOKBACK_SECONDS, "seen": []}
    messages = sorted(await workflow.deps.gmail.read_mail(state["after"]), key=lambda m: m["internal_ms"])
    seen = set(state["seen"])
    fresh = [message for message in messages if message["id"] not in seen]
    for message in fresh:
        await take_mail(workflow, message)
        state["seen"].append(message["id"])
        state["after"] = max(state["after"], message["internal_ms"] // 1000 - 60)
        await workflow.store.aput(COURIER, "cursor", {**state, "seen": state["seen"][-SEEN_KEPT:]})
    return len(fresh)


async def poll_forever(workflow: Workflow, seconds: int) -> None:
    while True:
        try:
            count = await poll(workflow)
            await set_status(workflow.store, "gmail", True, f"Read {count} new emails")
        except Exception as error:
            log.exception("Courier poll failed")
            await set_status(workflow.store, "gmail", False, f"gmail is being difficult: {error}"[:300])
        await asyncio.sleep(seconds)

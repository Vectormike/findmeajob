from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.store.postgres.aio import AsyncPostgresStore
from pydantic import BaseModel, Field

from findmeajob.config import Settings
from findmeajob.events import broker

PROFILE = ("profile",)
LESSONS = ("profile", "lessons")
CASES = ("cases",)
STATUS = ("status",)
UNMATCHED = ("inbox", "unmatched")
COURIER = ("courier",)


class Story(BaseModel):
    title: str
    text: str


class FormFact(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=500)
    job: str = ""


class Profile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    links: str = ""
    titles: str = ""
    skills: list[str] = []
    work_authorization: str = ""
    skip_companies: list[str] = []
    stories: list[Story] = []
    form_facts: list[FormFact] = []
    master_cv: str = ""
    master_cv_file: str = ""


EMPTY_PROFILE: dict[str, Any] = Profile().model_dump()


def is_skipped(company: str, names: list[str]) -> bool:
    wanted = company.strip().lower()
    return bool(wanted) and wanted in {name.strip().lower() for name in names}


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@asynccontextmanager
async def open_memory(settings: Settings) -> AsyncIterator[tuple[Any, BaseStore]]:
    if not settings.uses_postgres:
        yield InMemorySaver(), InMemoryStore()
        return
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required when APP_ENV is dev or prod.")
    async with (
        AsyncPostgresSaver.from_conn_string(settings.database_url) as saver,
        AsyncPostgresStore.from_conn_string(settings.database_url) as store,
    ):
        await saver.setup()
        await store.setup()
        yield saver, store


async def list_values(store: BaseStore, namespace: tuple[str, ...], **kwargs: Any) -> list[dict[str, Any]]:
    items = await store.asearch(namespace, limit=1000, **kwargs)
    return [{"key": item.key, **item.value} for item in items]


async def read_profile(store: BaseStore) -> dict[str, Any]:
    item = await store.aget(PROFILE, "main")
    return {**EMPTY_PROFILE, **(item.value if item else {})}


async def write_profile(store: BaseStore, profile: dict[str, Any]) -> None:
    await store.aput(PROFILE, "main", {**EMPTY_PROFILE, **profile})


async def accepted_lessons(store: BaseStore) -> list[str]:
    lessons = await list_values(store, LESSONS)
    return [
        lesson["content"]["text"]
        for lesson in lessons
        if lesson["content"].get("status") == "accepted" and lesson["content"].get("kind") == "lesson"
    ]


def profile_text(profile: dict[str, Any], lessons: list[str]) -> str:
    stories = "\n\n".join(f"- {story['title']}: {story['text']}" for story in profile["stories"])
    lesson_lines = "\n".join(f"- {lesson}" for lesson in lessons) or "- none"
    facts = "\n".join(
        f"- {fact['question']} (asked by {fact['job'] or 'a past job'}): {fact['answer']}"
        for fact in profile["form_facts"]
    )
    return (
        f"Name: {profile['name']}\nEmail: {profile['email']}\nPhone: {profile['phone']}\n"
        f"Location: {profile['location']}\nLinks: {profile['links']}\nTitles: {profile['titles']}\n"
        f"Skills: {', '.join(profile['skills'])}\nWork authorization: {profile['work_authorization']}\n\n"
        f"Answers the candidate gave to form questions:\n{facts or '- none'}\n\n"
        f"Stories:\n{stories or '- none'}\n\nLessons from past interviews:\n{lesson_lines}\n\n"
        f"Master CV:\n{profile['master_cv']}"
    )


async def profile_context(store: BaseStore) -> str:
    return profile_text(await read_profile(store), await accepted_lessons(store))


async def index_case(store: BaseStore, state: dict[str, Any], agent: str) -> None:
    posting = state.get("posting", {})
    filters = state.get("filters", {})
    mail = state.get("mail", [])
    await store.aput(
        CASES,
        state["case_id"],
        {
            "company": posting.get("company", ""),
            "title": posting.get("title", ""),
            "url": posting.get("url", ""),
            "region": filters.get("region", ""),
            "skill": filters.get("skill", ""),
            "arrangement": filters.get("arrangement", ""),
            "stage": state.get("stage", ""),
            "last_agent": agent,
            "threads": sorted({m["thread_id"] for m in mail if m.get("thread_id")}),
            "contacts": sorted({m["from_email"] for m in mail if m.get("from_email")}),
            "updated_at": now(),
        },
    )
    broker.publish("case", case_id=state["case_id"], agent=agent, stage=state.get("stage", ""))


async def set_status(store: BaseStore, name: str, ok: bool, detail: str = "", **metadata: Any) -> None:
    await store.aput(STATUS, name, {"ok": ok, "detail": detail, "at": now(), **metadata})
    broker.publish("status", name=name, ok=ok, detail=detail, **metadata)

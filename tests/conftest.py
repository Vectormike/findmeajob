from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from findmeajob.agents.deps import Deps
from findmeajob.memory import write_profile
from findmeajob.workflow import Workflow
from tests.fakes import FakeChrome, FakeGmail, FakeModel, fake_fetch_page, fake_research

POSTING = {
    "source": "test",
    "title": "Backend Engineer",
    "company": "Acme",
    "url": "https://acme.example/jobs/1",
    "location": "Berlin",
    "apply_url": "",
    "description": "Node.js and Kafka.",
    "salary": "",
}
FILTERS = {"region": "germany", "skill": "Node.js", "arrangement": "any"}


@pytest.fixture
def deps(tmp_path: Any) -> Deps:
    return Deps(
        model=FakeModel(),
        data_dir=tmp_path,
        chrome=FakeChrome(),
        gmail=FakeGmail(),
        research=fake_research,
        fetch_page=fake_fetch_page,
    )


@pytest.fixture
async def workflow(deps: Deps) -> Workflow:
    flow = Workflow(deps, InMemorySaver(), InMemoryStore())
    await write_profile(
        flow.store, {"name": "Ada Lovelace", "email": "ada@example.com", "skills": ["Node.js", "Kafka"]}
    )
    return flow

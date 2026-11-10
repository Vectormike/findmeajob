import pytest

from findmeajob.agents import scout
from findmeajob.events import broker
from findmeajob.memory import CASES, STATUS
from findmeajob.tools.jobs.listing import Listing


@pytest.mark.parametrize(("region", "skill"), [("germany", "Node.js"), ("europe", "Backend Engineer")])
async def test_repeat_sweep_redisplays_existing_case_without_reopening(workflow, monkeypatch, region, skill):
    listing = Listing(
        source="test",
        title="Backend Engineer",
        company="Acme",
        url="https://acme.example/job",
        location="Berlin",
        description="Node.js",
    )
    case_id = scout.case_id_for("germany", "Node.js", "any", listing.company, listing.title)
    await workflow.store.aput(
        CASES,
        case_id,
        {"company": listing.company, "title": listing.title, "stage": "skipped"},
    )

    async def batches(region, skill, arrangement, the_muse_api_key=None, title_only=False):
        yield [listing]

    monkeypatch.setattr(scout, "search_job_batches", batches)
    async with broker.subscribe() as queue:
        opened = await scout.run(workflow, region, skill, "any", 20)
        events = []
        while not queue.empty():
            events.append(queue.get_nowait())

    assert opened == 0
    assert {"kind": "discovered", "case_id": case_id} in events
    status = await workflow.store.aget(STATUS, "scout")
    assert "none new, 1 already here" in status.value["detail"]
    assert status.value["run_id"]
    assert status.value["case_ids"] == [case_id]

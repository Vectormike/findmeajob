from findmeajob.agents.courier import MailRead
from tests.conftest import FILTERS, POSTING
from tests.fakes import message


async def test_blocked_clerk_can_be_retried_until_it_applies(workflow, deps):
    deps.model.grounded = False
    await workflow.start("c1", POSTING, FILTERS)
    assert (await workflow.case("c1"))["stage"] == "blocked"
    assert set(await workflow.retryable("c1")) == {"judge", "tailor", "clerk"}

    deps.model.grounded = True
    assert await workflow.rerun("c1", "clerk")
    case = await workflow.case("c1")
    assert case["stage"] == "applied"
    assert deps.chrome.filled == {"f0": "Ada Lovelace", "f1": "90000"}
    assert await workflow.waiting("c1")
    assert await workflow.retryable("c1") == []
    assert not await workflow.rerun("c1", "tailor")


async def test_a_skipped_case_can_be_judged_again(workflow, deps):
    deps.model.recommendation = "skip"
    await workflow.start("c1", POSTING, FILTERS)
    assert await workflow.retryable("c1") == ["judge"]

    deps.model.recommendation = "apply"
    assert await workflow.rerun("c1", "judge")
    assert (await workflow.case("c1"))["stage"] == "applied"


async def test_retry_reruns_only_the_latest_step_and_keeps_the_mail(workflow, deps):
    await workflow.start("c1", POSTING, FILTERS)
    deps.model.mail = MailRead(category="interview_invite", summary="Invite", needs_answer=False, has_feedback=False)
    await workflow.resume("c1", {"type": "mail", "message": message("Interview", "Tuesday?")})
    assert set(await workflow.retryable("c1")) == {"courier", "brief"}

    prompts = len(deps.model.prompts)
    assert await workflow.rerun("c1", "brief")
    case = await workflow.case("c1")
    assert len(deps.model.prompts) > prompts
    assert case["stage"] == "interview" and len(case["mail"]) == 1
    assert case["brief"]["questions"]
    assert await workflow.waiting("c1")

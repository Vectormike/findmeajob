from findmeajob.agents.courier import MailRead
from findmeajob.memory import CASES, LESSONS, list_values, read_profile, write_profile
from tests.conftest import FILTERS, POSTING
from tests.fakes import message


async def applied(workflow):
    await workflow.start("c1", POSTING, FILTERS)
    return await workflow.case("c1")


async def test_apply_runs_judge_tailor_clerk_then_waits(workflow, deps):
    case = await applied(workflow)
    assert case["stage"] == "applied"
    assert case["last_agent"] == "clerk"
    assert await workflow.waiting("c1")
    assert "<script>" not in case["cv"]["cv_html"] and "onclick" not in case["cv"]["cv_html"]
    assert deps.chrome.filled == {"f0": "Ada Lovelace", "f1": "90000"}
    assert case["application"]["salary"]["sources"] == ["https://pay.example"]
    index = (await workflow.store.aget(CASES, "c1")).value
    assert index["stage"] == "applied" and index["company"] == "Acme"


async def test_current_company_on_the_skip_list_ends_the_case(workflow):
    profile = await read_profile(workflow.store)
    await write_profile(workflow.store, {**profile, "skip_companies": ["acme"]})
    case = await applied(workflow)
    assert case["stage"] == "skipped"
    assert case["fit"]["reason"] == "The company is on your skip list."


async def test_skip_ends_the_case(workflow, deps):
    deps.model.recommendation = "skip"
    case = await applied(workflow)
    assert case["stage"] == "skipped"
    assert not await workflow.waiting("c1")


async def test_clerk_blocks_when_a_required_fact_is_missing(workflow, deps):
    deps.model.grounded = False
    case = await applied(workflow)
    assert case["stage"] == "blocked"
    assert "Full name" in case["application"]["blocked"]
    assert deps.chrome.filled == {}


async def test_mail_moves_the_case_and_invite_builds_the_brief(workflow, deps):
    await applied(workflow)
    await workflow.resume("c1", {"type": "mail", "message": message("Received", "We got your application")})
    assert (await workflow.case("c1"))["stage"] == "acknowledged"

    deps.model.mail = MailRead(category="interview_invite", summary="Invite", needs_answer=False, has_feedback=False)
    await workflow.resume("c1", {"type": "mail", "message": message("Interview", "Can we talk Tuesday?")})
    case = await workflow.case("c1")
    assert case["stage"] == "interview"
    assert case["brief"]["questions"][0]["question"] == "Tell me about yourself"
    index = (await workflow.store.aget(CASES, "c1")).value
    assert index["threads"] == ["t1"] and index["contacts"] == ["jane@acme.com"]


async def test_reply_is_sent_only_after_approval(workflow, deps):
    await applied(workflow)
    deps.model.mail = MailRead(category="recruiter_reply", summary="Asks", needs_answer=True, has_feedback=False)
    await workflow.resume("c1", {"type": "mail", "message": message("Quick question", "Are you available?")})
    case = await workflow.case("c1")
    assert case["draft"]["to"] == "jane@acme.com"
    assert deps.gmail.sent == []

    await workflow.resume("c1", {"type": "approve", "body": "Yes, Tuesday works."})
    case = await workflow.case("c1")
    assert deps.gmail.sent == [("jane@acme.com", "Quick question", "Yes, Tuesday works.")]
    assert case["draft"] is None and len(case["sent"]) == 1


async def test_notes_run_critic_archivist_and_draft_a_thank_you(workflow, deps):
    await applied(workflow)
    deps.model.mail = MailRead(category="interview_invite", summary="Invite", needs_answer=False, has_feedback=False)
    await workflow.resume("c1", {"type": "mail", "message": message("Interview", "Tuesday?")})
    notes = {
        "title": "Acme interview",
        "start_time": "now",
        "summary": "Talked Kafka",
        "key_questions": [],
        "action_items": [],
        "transcript": "Jane: tell me about yourself",
        "participants": [],
        "session_id": "s1",
    }
    await workflow.resume("c1", {"type": "notes", "notes": notes})
    case = await workflow.case("c1")
    assert case["stage"] == "debriefed"
    assert case["debriefs"][0]["could_be_better"] == ["Give metrics"]
    assert case["draft"]["kind"] == "thank_you"
    lessons = await list_values(workflow.store, LESSONS)
    assert [entry["content"]["text"] for entry in lessons] == ["Lead with a metric"]
    assert lessons[0]["content"]["status"] == "proposed"


async def test_close_ends_the_case(workflow):
    await applied(workflow)
    await workflow.resume("c1", {"type": "close"})
    assert (await workflow.store.aget(CASES, "c1")).value["stage"] == "closed"
    assert not await workflow.waiting("c1")

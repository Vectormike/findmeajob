from findmeajob.agents import inbox
from findmeajob.memory import UNMATCHED, list_values
from findmeajob.tools.readai import read_meeting_notes
from tests.conftest import FILTERS, POSTING
from tests.fakes import message

CASES = [
    {"key": "a", "company": "Acme", "title": "Backend Engineer", "threads": [], "contacts": []},
    {"key": "b", "company": "Globex", "title": "Node.js Developer", "threads": ["t9"], "contacts": []},
]


def test_match_by_company_domain_and_thread():
    assert inbox.match(CASES, ["no-reply@greenhouse.io"], "Your application to Acme") == "a"
    assert inbox.match(CASES, ["jane@globex.com"], "Hello") == "b"
    assert inbox.match(CASES, ["x@y.com"], "Hello", "t9") == "b"


def test_ambiguous_or_unknown_mail_does_not_match():
    assert inbox.match(CASES, ["x@y.com"], "Newsletter") is None
    assert inbox.match(CASES, ["x@y.com"], "Acme and Globex merge") is None


async def test_poll_files_mail_on_its_case_and_parks_the_rest(workflow, deps):
    await workflow.start("c1", POSTING, FILTERS)
    deps.gmail.inbox = [
        message("Application received", "Thanks for applying to Acme", sender="no-reply@greenhouse.io", ms=2000),
        message("Weekly digest", "News", sender="news@example.com", thread="t2", ms=3000),
    ]
    assert await inbox.poll(workflow) == 2
    assert (await workflow.case("c1"))["stage"] == "acknowledged"
    parked = await list_values(workflow.store, UNMATCHED)
    assert [item["key"] for item in parked] == ["mail-m-Weekly digest"]
    assert await inbox.poll(workflow) == 0


def test_read_ai_payload():
    notes = read_meeting_notes(
        {
            "session_id": "s1",
            "title": "Acme interview",
            "participants": [{"name": "Jane", "email": "Jane@Acme.com"}],
            "action_items": [{"text": "Send portfolio"}],
            "key_questions": ["Why Kafka?"],
            "transcript": {"speaker_blocks": [{"speaker": {"name": "Jane"}, "words": "Tell me about yourself"}]},
        }
    )
    assert notes["participants"] == [{"name": "Jane", "email": "jane@acme.com"}]
    assert notes["action_items"] == ["Send portfolio"] and notes["key_questions"] == ["Why Kafka?"]
    assert notes["transcript"] == "Jane: Tell me about yourself"

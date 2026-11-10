from findmeajob.agents.clerk import FieldAnswer, FormAnswers
from findmeajob.tools.browser_ats import GENERIC, strategy_for
from tests.conftest import FILTERS, POSTING
from tests.fakes import FIELDS, FakeChrome


async def run_case(workflow):
    await workflow.start("clerk-case", POSTING, FILTERS)
    return await workflow.case("clerk-case")


def answers(*items: tuple[str, str]) -> FormAnswers:
    return FormAnswers(
        answers=[
            FieldAnswer(field_id=field_id, value=value, source="profile", grounded=True)
            for field_id, value in items
        ]
    )


async def test_clerk_completes_dynamic_multi_step_form(workflow, deps):
    second_step = [{"id": "f0", "type": "text", "label": "Portfolio", "required": True}]
    deps.chrome = FakeChrome(
        steps=[FIELDS, second_step],
        outcomes=[
            {"status": "advanced", "url": "https://acme.example/apply/2"},
            {
                "status": "submitted",
                "confirmation": {"url": "https://acme.example/thanks", "page_text": "Thank you", "confirmed": "yes"},
            },
        ],
    )
    deps.model.form_answers = [
        answers(("f0", "Ada Lovelace"), ("f1", "90000")),
        answers(("f0", "https://ada.example")),
    ]

    case = await run_case(workflow)

    assert case["stage"] == "applied"
    assert [step["outcome"] for step in case["application"]["steps"]] == ["advanced", "submitted"]
    assert deps.chrome.fill_history == [
        {"f0": "Ada Lovelace", "f1": "90000"},
        {"f0": "https://ada.example"},
    ]


async def test_clerk_rescans_and_corrects_validation_errors(workflow, deps):
    deps.chrome = FakeChrome(
        steps=[FIELDS],
        outcomes=[
            {"status": "validation", "errors": ["Expected salary: enter digits only"]},
            {
                "status": "submitted",
                "confirmation": {"url": "https://acme.example/thanks", "page_text": "Thank you", "confirmed": "yes"},
            },
        ],
    )
    deps.model.form_answers = [
        answers(("f0", "Ada Lovelace"), ("f1", "EUR 90,000")),
        answers(("f0", "Ada Lovelace"), ("f1", "90000")),
    ]

    case = await run_case(workflow)

    assert case["stage"] == "applied"
    assert len(deps.chrome.fill_history) == 2
    assert "enter digits only" in deps.model.prompts[-1]


async def test_clerk_blocks_an_unconfirmed_submission(workflow, deps):
    deps.chrome = FakeChrome(
        outcomes=[
            {
                "status": "unconfirmed",
                "confirmation": {"url": POSTING["url"], "page_text": "Apply", "confirmed": "no"},
            }
        ]
    )

    case = await run_case(workflow)

    assert case["stage"] == "blocked"
    assert "reliable confirmation" in case["application"]["blocked"]


async def test_clerk_stops_a_repeating_form(workflow, deps):
    deps.chrome = FakeChrome(
        steps=[FIELDS, FIELDS, FIELDS, FIELDS],
        outcomes=[{"status": "advanced", "url": POSTING["url"]} for _ in range(3)],
    )

    case = await run_case(workflow)

    assert case["stage"] == "blocked"
    assert "stuck on the same step" in case["application"]["blocked"]


async def test_clerk_leaves_a_referral_blank_and_continues(workflow, deps):
    deps.chrome = FakeChrome(
        steps=[
            [
                {"id": "f0", "type": "text", "label": "Full name", "required": True},
                {"id": "f1", "type": "text", "label": "Type the email of your friend", "required": True},
            ]
        ]
    )
    deps.model.form_answers = [
        answers(("f0", "Ada Lovelace"), ("f1", "friend@example.com")),
    ]
    deps.model.form_answers[0].answers[1].grounded = False

    case = await run_case(workflow)

    assert case["stage"] == "applied"
    assert deps.chrome.filled == {"f0": "Ada Lovelace"}


async def test_clerk_retries_once_when_the_browser_closes(workflow, deps):
    deps.chrome.crashes = [RuntimeError("Page.goto: net::ERR_NETWORK_CHANGED at https://jobicy.com/jobs/1")]

    case = await run_case(workflow)

    assert case["stage"] == "applied"
    assert deps.chrome.filled["f0"] == "Ada Lovelace"


async def test_clerk_blocks_when_the_browser_closes_twice(workflow, deps):
    deps.chrome.crashes = [
        RuntimeError("Target page, context or browser has been closed"),
        RuntimeError("Target page, context or browser has been closed"),
    ]

    case = await run_case(workflow)

    assert case["stage"] == "blocked"
    assert "has been closed" in case["application"]["blocked"]


async def test_clerk_lets_go_of_a_page_that_stops_responding(workflow, deps):
    deps.chrome.crashes = [TimeoutError()]

    case = await run_case(workflow)

    assert case["stage"] == "blocked"
    assert "stopped responding" in case["application"]["blocked"]


def test_common_ats_hosts_get_a_strategy():
    assert strategy_for("https://boards.greenhouse.io/acme").name == "greenhouse"
    assert strategy_for("https://jobs.lever.co/acme").name == "lever"
    assert strategy_for("https://jobs.ashbyhq.com/acme").name == "ashby"
    assert strategy_for("https://acme.wd5.myworkdayjobs.com/jobs").name == "workday"
    assert strategy_for("https://acme.example/jobs").name == GENERIC.name

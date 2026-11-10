from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from findmeajob.agents.archivist import Proposal, Proposals
from findmeajob.agents.brief import Answered, InterviewPrep, InterviewResearch
from findmeajob.agents.chaser import Draft
from findmeajob.agents.clerk import FieldAnswer, FormAnswers, SalaryRange
from findmeajob.agents.courier import MailRead
from findmeajob.agents.critic import Debrief
from findmeajob.agents.judge import FitArea, FitNote
from findmeajob.agents.tailor import CvChange, TailoredCv
from findmeajob.memory import Story
from findmeajob.profile_from_cv import CvFacts

FIELDS = [
    {"id": "f0", "type": "text", "label": "Full name", "required": True},
    {"id": "f1", "type": "text", "label": "Expected salary", "required": True},
    {"id": "f2", "type": "file", "label": "Resume", "required": True},
]


class FakeModel:
    def __init__(self) -> None:
        self.recommendation = "apply"
        self.mail = MailRead(category="acknowledgment", summary="Received", needs_answer=False, has_feedback=False)
        self.grounded = True
        self.form_answers: list[FormAnswers] = []
        self.prompts: list[str] = []
        self.copies: list[dict[str, Any]] = []
        self.answers = {
            FitNote: lambda: FitNote(
                technical=FitArea(verdict="Strong on the stack.", covered=["Node.js"], missing=[]),
                behavioural=FitArea(verdict="No mentoring shown.", covered=["Ownership"], missing=["Mentoring"]),
                seniority="match",
                location_and_pay="ok",
                red_flags=[],
                recommendation=self.recommendation,
                reason="Covers the stack.",
            ),
            TailoredCv: lambda: TailoredCv(
                requirements=["Node.js", "Kafka"],
                cv_html="<h1>Ada</h1><script>x()</script><p onclick='x'>Node.js</p>",
                changes=[CvChange(change="Added Kafka work", requirement="Kafka", source="profile")],
                gaps=[],
            ),
            FormAnswers: lambda: FormAnswers(
                answers=[
                    FieldAnswer(field_id="f0", value="Ada Lovelace", source="profile", grounded=self.grounded),
                    FieldAnswer(field_id="f1", value="90000", source="salary_range", grounded=True),
                ]
            ),
            MailRead: lambda: self.mail,
            InterviewPrep: lambda: InterviewPrep(
                questions=[
                    Answered(question="Why us?", answer="...", why_asked="fit"),
                    Answered(question="Tell me about yourself", answer="I build Node.js systems.", why_asked="opener"),
                ],
                gaps_to_prepare=[],
                questions_to_ask_them=["What does success look like?"],
            ),
            Debrief: lambda: Debrief(
                landed=["Kafka story"],
                thin=["Testing"],
                unused_answers=[],
                could_be_better=["Give metrics"],
                lessons=["Lead with a metric"],
            ),
            Proposals: lambda: Proposals(proposals=[Proposal(kind="lesson", text="Lead with a metric")]),
            Draft: lambda: Draft(body="Thanks for your time."),
            CvFacts: lambda: CvFacts(
                name="Ada Lovelace",
                email="ada@example.com",
                titles="Backend Engineer",
                skills=["Node.js"],
                current_company="Acme",
                stories=[Story(title="Acme", text="Moved billing to Kafka.")],
            ),
        }

    def model_copy(self, update: dict[str, Any]) -> "FakeModel":
        self.copies.append(update)
        return self

    def with_structured_output(self, schema: type) -> "FakeModel._Bound":
        return FakeModel._Bound(self, schema)

    class _Bound:
        def __init__(self, model: "FakeModel", schema: type) -> None:
            self.model, self.schema = model, schema

        async def ainvoke(self, messages: list[tuple[str, str]]) -> Any:
            self.model.prompts.append(messages[-1][1])
            if self.schema is FormAnswers and self.model.form_answers:
                return self.model.form_answers.pop(0)
            return self.model.answers[self.schema]()


async def fake_research(model: Any, task: str, schema: type) -> Any:
    if schema is SalaryRange:
        return SalaryRange(
            low=80000, high=100000, currency="EUR", period="year", figure=90000, sources=["https://pay.example"]
        )
    return InterviewResearch(company=[], interview_process=[], reported_questions=[], role=[])


async def fake_fetch_page(url: str) -> dict[str, str]:
    return {"url": url, "title": "Backend Engineer", "text": "Backend Engineer at Acme. Node.js and Kafka."}


async def no_employer_board(posting: dict) -> None:
    return None


class FakeSession:
    def __init__(self, chrome: "FakeChrome") -> None:
        self.chrome = chrome

    async def fields(self) -> list[dict[str, Any]]:
        return self.chrome.steps[self.chrome.step]

    async def fill(self, fields: list[dict[str, Any]], answers: dict[str, str], cv_pdf: Path) -> None:
        self.chrome.filled.update(answers)
        self.chrome.fill_history.append(answers)

    async def advance(self) -> dict[str, Any]:
        outcome = self.chrome.outcomes.pop(0)
        if outcome["status"] == "advanced":
            self.chrome.step += 1
        return outcome


class FakeChrome:
    def __init__(
        self, steps: list[list[dict[str, Any]]] | None = None, outcomes: list[dict[str, Any]] | None = None
    ) -> None:
        self.filled: dict[str, str] = {}
        self.fill_history: list[dict[str, str]] = []
        self.crashes: list[BaseException] = []
        self.live: dict[str, Any] = {}
        self.steps = steps or [FIELDS]
        self.outcomes = outcomes or [
            {
                "status": "submitted",
                "confirmation": {
                    "url": "https://acme.example/thanks",
                    "page_text": "Thank you",
                    "confirmed": "yes",
                },
            }
        ]
        self.step = 0

    @asynccontextmanager
    async def fill_form(self, url: str, case_id: str | None = None, notify: Any = None) -> Any:
        if self.crashes:
            raise self.crashes.pop(0)
        yield FakeSession(self)

    async def render_pdf(self, html: str, path: Path) -> Path:
        return path

    async def healthcheck(self) -> None:
        return None


class FakeGmail:
    def __init__(self) -> None:
        self.sent: list[tuple[str, ...]] = []
        self.inbox: list[dict[str, Any]] = []

    async def send_mail(self, to: str, subject: str, body: str, thread_id: str, in_reply_to: str) -> str:
        self.sent.append((to, subject, body))
        return "sent-1"

    async def healthcheck(self) -> str:
        return "ada@example.com"

    async def read_mail(self, after_epoch: int) -> list[dict[str, Any]]:
        return self.inbox


def message(
    subject: str, body: str, sender: str = "Jane <jane@acme.com>", thread: str = "t1", ms: int = 1000
) -> dict[str, Any]:
    return {
        "id": f"m-{subject}",
        "thread_id": thread,
        "from": sender,
        "from_email": sender.split("<")[-1].rstrip(">"),
        "to": "ada@example.com",
        "subject": subject,
        "date": "today",
        "message_id": f"<{subject}@acme>",
        "internal_ms": ms,
        "body": body,
    }

from io import BytesIO
from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from findmeajob.agents.courier import MailRead
from findmeajob.config import Settings
from findmeajob.events import broker
from findmeajob.web.app import create_app
from tests.conftest import FILTERS, POSTING
from tests.fakes import message


def client(deps, tmp_path) -> TestClient:
    settings = Settings(
        _env_file=None, app_env="test", data_dir=tmp_path, readai_webhook_secret="s3cret", ui_dir=tmp_path / "none"
    )
    return TestClient(create_app(settings, deps))


def test_api_lists_cases_and_details(deps, tmp_path):
    with client(deps, tmp_path) as http:
        for path in ("/api/inbox", "/api/cases", "/api/agents", "/api/profile", "/api/integrations"):
            assert http.get(path).status_code == 200, path
        http.portal.call(http.app.state.workflow.start, "c1", POSTING, FILTERS)
        inbox = http.get("/api/inbox").json()
        assert [case["company"] for case in inbox["cases"]] == ["Acme"]
        assert inbox["counts"]["applied"] == 1
        detail = http.get("/api/cases/c1").json()
        fit = detail["case"]["fit"]
        assert fit["reason"] == "Covers the stack."
        assert fit["technical"]["covered"] == ["Node.js"] and fit["behavioural"]["missing"] == ["Mentoring"]
        assert fit["must_haves_covered"] == ["Node.js", "Ownership"] and fit["must_haves_missing"] == ["Mentoring"]
        assert "cv_html" not in detail["case"]["cv"] and "pdf" not in detail["case"]["cv"]
        assert detail["waiting"] is True
        assert detail["retryable"] == []
        assert http.post("/api/cases/c1/retry/tailor").status_code == 409
        assert http.get("/api/cases/c1/cv").status_code == 200
        pdf = Path(tmp_path, "cvs", "c1.pdf")
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4")
        preview = http.get("/api/cases/c1/cv.pdf")
        assert preview.status_code == 200 and "content-disposition" not in preview.headers
        download = http.get("/api/cases/c1/cv.pdf?download=true")
        assert 'attachment; filename="cv-c1.pdf"' == download.headers["content-disposition"]
        agents = {card["name"]: card for card in http.get("/api/agents").json()}
        assert agents["clerk"]["last"]["key"] == "c1"

class FakeLivePage:
    viewport_size = {"width": 1000, "height": 500}

    def __init__(self) -> None:
        self.actions: list[tuple] = []
        self.mouse = self
        self.keyboard = self

    async def screenshot(self, **_: object) -> bytes:
        return b"jpeg"

    async def click(self, x: float, y: float) -> None:
        self.actions.append(("click", x, y))

    async def type(self, text: str) -> None:
        self.actions.append(("type", text))

    async def press(self, key: str) -> None:
        self.actions.append(("key", key))

    async def wheel(self, dx: float, dy: float) -> None:
        self.actions.append(("scroll", dy))


def test_live_view_relays_a_person_on_a_captcha(deps, tmp_path):
    with client(deps, tmp_path) as http:
        http.portal.call(http.app.state.workflow.start, "c1", POSTING, FILTERS)
        assert http.get("/api/cases/c1/live.jpg").status_code == 404
        assert http.get("/api/cases/c1").json()["captcha"] is False

        page = FakeLivePage()
        deps.chrome.live["c1"] = page
        assert http.get("/api/cases/c1").json()["captcha"] is True
        assert http.get("/api/inbox").json()["cases"][0]["captcha"] is True
        assert http.get("/api/cases/c1/live.jpg").content == b"jpeg"
        for action in (
            {"kind": "click", "x": 0.5, "y": 0.2},
            {"kind": "type", "text": "ada"},
            {"kind": "key", "key": "Enter"},
            {"kind": "scroll", "dy": 300},
        ):
            assert http.post("/api/cases/c1/live", json=action).status_code == 200
        assert page.actions == [("click", 500, 100), ("type", "ada"), ("key", "Enter"), ("scroll", 300)]
        assert http.post("/api/cases/c1/live", json={"kind": "key", "key": "F12"}).status_code == 422


def test_integrations_have_working_health_checks(deps, tmp_path):
    with client(deps, tmp_path) as http:
        cards = {card["key"]: card for card in http.get("/api/integrations").json()}
        assert all(card["active"] for card in cards.values())
        for key in ("gmail", "readai", "chrome", "xai"):
            response = http.post(f"/api/integrations/{key}/test")
            assert response.status_code == 200, response.text
        refreshed = {card["key"]: card for card in http.get("/api/integrations").json()}
        assert all(card["status"]["ok"] for card in refreshed.values())


def test_gmail_connect_explains_missing_oauth_file(deps, tmp_path):
    deps.gmail = None
    with client(deps, tmp_path) as http:
        response = http.post("/api/integrations/gmail/connect")
        assert response.status_code == 409
        assert "Google OAuth client file" in response.json()["detail"]


def test_profile_saves(deps, tmp_path):
    with client(deps, tmp_path) as http:
        profile = {
            "name": "Ada",
            "skills": ["Node.js", "Kafka"],
            "stories": [{"title": "Kafka", "text": "Moved billing."}],
        }
        saved = http.put("/api/profile", json=profile).json()["profile"]
        assert saved["skills"] == ["Node.js", "Kafka"] and saved["stories"][0]["title"] == "Kafka"
        assert saved["master_cv"] == ""


def test_master_cv_upload_reads_text(deps, tmp_path):
    document = Document()
    document.add_paragraph("Ada Lovelace")
    document.add_paragraph("Backend Engineer at Acme, 2020 to 2024")
    data = BytesIO()
    document.save(data)
    with client(deps, tmp_path) as http:
        http.put("/api/profile", json={"name": "Ada", "phone": "+1", "skip_companies": ["Initech"]})
        saved = http.put("/api/profile/cv?name=cv.docx", content=data.getvalue()).json()["profile"]
        assert saved["master_cv"] == "Ada Lovelace\nBackend Engineer at Acme, 2020 to 2024"
        assert saved["master_cv_file"] == "cv.docx"
        assert saved["name"] == "Ada Lovelace" and saved["email"] == "ada@example.com"
        assert saved["titles"] == "Backend Engineer" and saved["skills"] == ["Node.js"]
        assert saved["stories"][0]["text"] == "Moved billing to Kafka."
        assert saved["phone"] == "+1" and saved["skip_companies"] == ["Initech", "Acme"]
        assert http.put("/api/profile/cv?name=cv.txt", content=b"  Plain CV  \n").json()["profile"]["master_cv"] == (
            "Plain CV"
        )
        assert http.put("/api/profile/cv?name=cv.txt", content=b"Ada\x00 Lovelace").json()["profile"]["master_cv"] == (
            "Ada Lovelace"
        )
        assert http.put("/api/profile/cv?name=cv.png", content=b"x").status_code == 422
        assert http.put("/api/profile/cv?name=cv.txt", content=b"  ").status_code == 422


def test_draft_approval_sends(deps, tmp_path):
    with client(deps, tmp_path) as http:
        workflow = http.app.state.workflow
        http.portal.call(workflow.start, "c1", POSTING, FILTERS)
        deps.model.mail = MailRead(category="recruiter_reply", summary="Asks", needs_answer=True, has_feedback=False)
        http.portal.call(workflow.resume, "c1", {"type": "mail", "message": message("Question", "Free Tuesday?")})
        assert http.get("/api/cases/c1").json()["case"]["draft"]["body"] == "Thanks for your time."
        detail = http.post("/api/cases/c1/approve", json={"body": "Tuesday works."}).json()
        assert deps.gmail.sent[-1][2] == "Tuesday works." and detail["case"]["draft"] is None
        assert http.post("/api/cases/nope/close").status_code == 409


def test_events_reach_subscribers(deps, tmp_path):
    async def collect():
        async with broker.subscribe() as queue:
            await workflow.start("c1", POSTING, FILTERS)
            return [queue.get_nowait() for _ in range(queue.qsize())]

    with client(deps, tmp_path) as http:
        workflow = http.app.state.workflow
        events = http.portal.call(collect)
    working = [e["agent"] for e in events if e["kind"] == "working"]
    assert working == ["judge", "tailor", "clerk"]
    assert any(e["kind"] == "case" and e["stage"] == "applied" for e in events)


def test_readai_webhook_requires_the_secret(deps, tmp_path):
    with client(deps, tmp_path) as http:
        assert http.post("/webhooks/readai/wrong", json={}).status_code == 404
        assert http.post("/webhooks/readai/s3cret", json={"session_id": "s1", "title": "Call"}).status_code == 200

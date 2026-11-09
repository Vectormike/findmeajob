from langgraph.store.memory import InMemoryStore

from findmeajob.agents.tailor import PAGE, RoleSkill, add_role_skills, clean_html, fit_brief, focused_posting, run
from findmeajob.memory import write_profile
from tests.conftest import POSTING

SAMPLE = """
"
<div class="head"><h1>Ada Lovelace</h1>
<div class="identity"><p>Engineer<br>London<br><a href="https://example.com" onclick="x">site</a></p>
<p class="summary">Builds things.</p></div></div>
<script>alert(1)</script>
<h2>Work Experience</h2>
<div class="role"><p class="role-line"><strong>Engineer</strong><span>Acme</span><span class="when">2020 - 2024</span></p>
<ul><li>Shipped it.</li></ul></div>
<h2>Skills</h2>
<div class="skills"><p><strong>Languages</strong><span>Go, SQL</span></p></div>
"""


def test_cv_html_keeps_the_resume_layout():
    html = clean_html(SAMPLE)
    assert "<script>" not in html and "onclick" not in html
    assert html.startswith('<div class="head">')
    for marker in ('class="identity"', 'class="summary"', 'class="role-line"', 'class="when"', 'class="skills"'):
        assert marker in html
    page = PAGE.format(body=html)
    assert "grid-template-columns: 1.25fr 1fr auto" in page
    assert "Ada Lovelace" in page


def test_role_skills_lead_the_skills_section():
    skills = [
        RoleSkill(term="Kafka", category="Backend", evidence="Bujeti"),
        RoleSkill(term="Go", category="Languages", evidence="already listed"),
        RoleSkill(term="distributed systems", category="Engineering Practices", evidence="Bujeti"),
        RoleSkill(term="RAG pipelines", category="AI", evidence="none"),
        RoleSkill(term="SQL", category="Databases", evidence="Crenet"),
        RoleSkill(term="React", category="Frontend", evidence="Hotels.ng"),
    ]
    html = add_role_skills(
        '<div class="skills"><p><strong>Languages</strong><span>Go</span></p>'
        "<p><strong>Backend</strong><span>React, Node.js</span></p>"
        "<p><strong>Databases</strong><span>MySQL, MongoDB</span></p>"
        "<p><strong>UI</strong><span>React</span></p></div>",
        skills,
        gaps=["Familiarity with RAG pipelines on Google Cloud"],
    )
    assert "<span>Kafka, Node.js</span>" in html
    assert "<span>Go</span>" in html
    assert "<span>SQL, MySQL, MongoDB</span>" in html
    assert "<strong>Frontend</strong><span>React</span>" in html
    assert "<strong>Engineering Practices</strong><span>Distributed systems</span>" in html
    assert html.count("React") == 1 and "UI" not in html
    assert "RAG" not in html


def test_fit_brief_passes_the_judges_ranking():
    brief = fit_brief({"recommendation": "apply", "must_haves_covered": ["Node.js"], "must_haves_missing": ["Kafka"]})
    assert "apply" in brief and "Node.js" in brief and "Kafka" in brief


async def test_tailor_writes_the_cv_in_one_pass(deps):
    store = InMemoryStore()
    await write_profile(store, {"name": "Ada Lovelace", "skills": ["Node.js"]})
    result = await run(
        {
            "case_id": "c1",
            "posting": POSTING,
            "fit": {"recommendation": "apply", "must_haves_covered": ["Node.js"], "must_haves_missing": ["Kafka"]},
        },
        deps,
        store,
    )
    assert len(deps.model.prompts) == 1
    assert deps.model.copies == [{"reasoning_effort": "low"}]
    assert "Covered must-haves: Node.js" in deps.model.prompts[0]
    assert result["stage"] == "tailored"
    assert "<script>" not in result["cv"]["cv_html"]


def test_myjobmag_posting_drops_page_navigation():
    posting = {
        "source": "myjobmag",
        "title": "DevOps Engineer",
        "company": "Acme",
        "description": (
            "Login Signup Employers Jobs Career Advice "
            "About the Role\nBuild cloud infrastructure.\nRequirements\nAWS and Kubernetes.\n"
            "Method of Application\nSign up for alerts and view other jobs."
        ),
    }
    text = focused_posting(posting)
    assert "About the Role" in text and "AWS and Kubernetes" in text
    assert "Login Signup" not in text and "Sign up for alerts" not in text

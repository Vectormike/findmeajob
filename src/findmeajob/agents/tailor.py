import asyncio
import re
from typing import Any, Literal

from bs4 import BeautifulSoup
from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from findmeajob.agents.deps import Deps
from findmeajob.llm import ask
from findmeajob.memory import profile_context
from findmeajob.state import CaseState, posting_text

PASS_TIMEOUT_SECONDS = 180
REASONING_EFFORT = "low"

SYSTEM = (
    "You are Tailor. You write a CV for one job so it passes the employer's ATS and reads well to a recruiter. "
    "This must be materially tailored, not the master CV with reordered skills. Judge already ranked the must-haves. "
    "Use that ranking. Do not re-analyze the posting. Make the strongest truthful evidence for the covered "
    "requirements easy to find. "
    "You may rewrite bullets for clarity and relevance, but every employer, title, date, skill, event, metric, "
    "tool, and outcome must be grounded in the master CV or profile. Never merge facts from different employers. "
    "Mirror the posting's exact terms only when the candidate's evidence genuinely supports them. "
    "You may add experience that appears in the profile (skills, stories) but is missing from the master CV, "
    "attached to the employer and dates the profile gives; mark those changes with source 'profile'. "
    "Never invent skills, employers, titles, dates, or metrics. A requirement found in neither the master CV "
    "nor the profile is a gap: list it in gaps and leave it out of the CV. "
    "Keep the candidate's real professional title; you may append a specialization after a | only when the source "
    "evidence directly supports it. Write a job-specific 45-70 word summary that leads with the "
    "top supported requirements, strongest relevant scope, and grounded metrics. Avoid generic claims. "
    "Keep every role in reverse chronology. Within each role, select 1-5 relevant bullets and order the strongest "
    "evidence first. Front-load the job's supported keywords and retain the original facts and metrics. "
    "Do not keep an irrelevant bullet merely to fill space. Ensure every supported must-have appears in the "
    "summary, skills, or a work bullet. Fill role_skills by going through every posting requirement and pulling "
    "out each concrete skill, tool, technology, or engineering practice it names, such as asynchronous service "
    "design, data processing pipelines, automated testing, or data structures and algorithms. Keep one when the "
    "master CV or profile proves it, even in different words, and write it in the posting's short exact wording. "
    "Give the category for what the skill is, not for the role: a master CV skill category when it truly fits, "
    "otherwise a standard one such as Frontend, Messaging & Streaming, or Engineering Practices. A frontend "
    "framework is never Backend. Engineering Practices are named disciplines like Distributed Systems or Automated "
    "Testing, never adjectives such as resilient or scalable, and never a restatement of a language or tool. "
    "Give the evidence too. Usually 6-12 terms. In related_skills, list up to 8 more skills the master CV or "
    "profile proves that are closely tied to those requirements, categorized the same way. Leave out skills "
    "unrelated to this job. Never list a gap in either. The Skills section is built from these two lists, so "
    "leave it out of cv_html. "
    "Use current profile contact facts when present and the master CV for any missing header facts. "
    "Aim for a focused two-page CV. Do not mention gaps, requirements, tailoring, or the target company in the CV. "
    "cv_html must use this shape and nothing else. No markdown fences, no wrapping quotes. "
    "Section order is Work Experience, then Education.\n"
    '<div class="head"><h1>Full name</h1><div class="identity">'
    "<p>Title<br>City, Country<br>link<br>link<br>email</p>"
    '<p class="summary">Summary paragraph from the master CV.</p></div></div>\n'
    "<h2>Work Experience</h2>"
    '<div class="role"><p class="role-line"><strong>Title</strong><span>Company</span>'
    '<span class="when">Mon YYYY - Mon YYYY</span></p><ul><li>bullet copied from the master CV</li></ul></div>\n'
    '<h2>Education</h2><p class="role-line"><strong>Degree</strong><span>School</span>'
    '<span class="when">dates</span></p>\n'
    "One role block per job, newest first. Title, company, and dates stay on the role-line, never in the bullets."
)

ALLOWED_TAGS = {"h1", "h2", "p", "ul", "ol", "li", "strong", "em", "a", "br", "div", "span"}
KEEP_CLASS = {"head", "identity", "summary", "role", "role-line", "when", "skills"}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
body {{ font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; font-size: 10pt; line-height: 1.35; margin: 0; }}
h1 {{ font-size: 22pt; line-height: 1.1; margin: 0 0 10pt; }}
h2 {{ font-size: 13pt; color: #2f5bd3; font-weight: 650; margin: 14pt 0 8pt; border-bottom: 1.5px solid #2f5bd3; padding-bottom: 2pt; }}
.identity {{ display: grid; grid-template-columns: 0.85fr 1.25fr; column-gap: 22pt; align-items: start; }}
.identity p {{ margin: 0; }}
.role {{ margin: 0 0 9pt; }}
.role-line {{ display: grid; grid-template-columns: 1.25fr 1fr auto; column-gap: 10pt; align-items: baseline; margin: 9pt 0 2pt; }}
.when {{ text-align: right; white-space: nowrap; }}
.skills p {{ display: grid; grid-template-columns: 150pt 1fr; column-gap: 14pt; margin: 3pt 0; }}
ul {{ margin: 2pt 0 2pt 14pt; padding: 0; }}
li {{ margin: 1pt 0; }}
a {{ color: inherit; text-decoration: none; }}
</style></head><body>{body}</body></html>"""


class CvChange(BaseModel):
    change: str
    requirement: str = Field(description="The posting requirement this change serves")
    source: Literal["master_cv", "profile"]


class RoleSkill(BaseModel):
    term: str = Field(description="The posting's exact wording for a skill, tool, technology, or practice")
    category: str = Field(description="The master CV skill category it belongs to")
    evidence: str = Field(description="Where the master CV or profile proves it")


class TailoredCv(BaseModel):
    requirements: list[str] = Field(description="Requirements pulled from the posting")
    cv_html: str
    changes: list[CvChange]
    gaps: list[str] = Field(description="Requirements found in neither the master CV nor the profile")
    role_skills: list[RoleSkill] = Field(default=[], description="Posting skills the candidate's evidence proves")
    related_skills: list[RoleSkill] = Field(default=[], description="Proven skills closely tied to the role skills")


def fit_brief(fit: dict[str, Any]) -> str:
    covered = ", ".join(fit.get("must_haves_covered") or []) or "none"
    missing = ", ".join(fit.get("must_haves_missing") or []) or "none"
    return (
        f"Judge ranking: {fit.get('recommendation', 'unknown')}. "
        f"Covered must-haves: {covered}. Missing must-haves, already gaps unless the profile shows them: {missing}."
    )


def focused_posting(posting: dict[str, Any]) -> str:
    description = posting.get("description", "")
    if posting.get("source") == "myjobmag":
        starts = [description.find(marker) for marker in ("About the Role", "Responsibilities", "Requirements")]
        starts = [position for position in starts if position >= 0]
        if starts:
            description = description[min(starts) :]
        ends = [
            description.find(marker)
            for marker in ("Method of Application", "Check how your CV matches", "View Current Vacancies")
        ]
        ends = [position for position in ends if position >= 0]
        if ends:
            description = description[: min(ends)]
    return posting_text({**posting, "description": description.strip()})


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(True):
        if tag.decomposed:
            continue
        if tag.name in {"script", "style", "iframe", "object"}:
            tag.decompose()
            continue
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        attrs: dict[str, str | list[str]] = {}
        href = tag.get("href", "")
        if tag.name == "a" and href.startswith(("http://", "https://", "mailto:")):
            attrs["href"] = href
        classes = tag.get("class", [])
        kept = [name for name in (classes if isinstance(classes, list) else classes.split()) if name in KEEP_CLASS]
        if kept:
            attrs["class"] = kept
        tag.attrs = attrs
    for text in list(soup.find_all(string=True)):
        cleaned = text.strip()
        if len(cleaned) >= 2 and cleaned[0] in "\"'`“”" and cleaned[-1] in "\"'`“”":
            text.replace_with(cleaned[1:-1])
        elif cleaned.strip("\"'`“”") == "":
            text.extract()
    root = soup.body or soup
    return "".join(str(child) for child in list(root.children) if str(child).strip())


def mentions(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE) is not None


def set_skills(html: str, role: list[RoleSkill], related: list[RoleSkill], gaps: list[str]) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for old in soup.find_all("div", class_="skills"):
        old.decompose()
    for heading in soup.find_all("h2"):
        if heading.get_text().strip().lower() == "skills":
            heading.decompose()
    groups: dict[str, tuple[str, list[str]]] = {}
    seen: set[str] = set()
    gap_text = " ".join(gaps)
    for skill in [*role, *related]:
        term = skill.term.strip()
        if not term or term.lower() in seen or mentions(gap_text, term):
            continue
        seen.add(term.lower())
        if term == term.lower():
            term = term[0].upper() + term[1:]
        category = skill.category.strip() or "Engineering Practices"
        groups.setdefault(category.lower(), (category, []))[1].append(term)
    if not groups:
        return str(soup)
    heading, block = soup.new_tag("h2"), soup.new_tag("div", attrs={"class": "skills"})
    heading.string = "Skills"
    for category, terms in groups.values():
        row, label, items = soup.new_tag("p"), soup.new_tag("strong"), soup.new_tag("span")
        label.string, items.string = category, ", ".join(terms)
        row.extend([label, items])
        block.append(row)
    education = next((h for h in soup.find_all("h2") if h.get_text().strip().lower() == "education"), None)
    if education:
        education.insert_before(heading, block)
    else:
        soup.append(heading)
        soup.append(block)
    return str(soup)


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    context = (
        f"Profile and master CV:\n{await profile_context(store)}\n\n"
        f"{fit_brief(state.get('fit') or {})}\n\n"
        f"Posting:\n{focused_posting(state['posting'])}"
    )
    cv = await asyncio.wait_for(
        ask(deps.model, TailoredCv, SYSTEM, context, REASONING_EFFORT),
        timeout=PASS_TIMEOUT_SECONDS,
    )
    html = PAGE.format(body=set_skills(clean_html(cv.cv_html), cv.role_skills, cv.related_skills, cv.gaps))
    result = {**cv.model_dump(), "cv_html": html, "pdf": ""}
    if deps.chrome:
        pdf = await deps.chrome.render_pdf(html, deps.data_dir / "cvs" / f"{state['case_id']}.pdf")
        result["pdf"] = str(pdf)
    return {"cv": result, "stage": "tailored"}

import asyncio
from typing import Any, Literal

from bs4 import BeautifulSoup
from langgraph.store.base import BaseStore
from pydantic import BaseModel, Field

from findmeajob.agents.deps import Deps
from findmeajob.llm import ask
from findmeajob.memory import profile_context
from findmeajob.state import CaseState, posting_text

PASS_TIMEOUT_SECONDS = 180

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
    "summary, skills, or a work bullet. Put job-relevant, supported skills first within their existing categories. "
    "Use current profile contact facts when present and the master CV for any missing header facts. "
    "Aim for a focused two-page CV. Do not mention gaps, requirements, tailoring, or the target company in the CV. "
    "cv_html must use this shape and nothing else. No markdown fences, no wrapping quotes. "
    "Section order is Work Experience, then Skills, then Education.\n"
    '<div class="head"><h1>Full name</h1><div class="identity">'
    "<p>Title<br>City, Country<br>link<br>link<br>email</p>"
    '<p class="summary">Summary paragraph from the master CV.</p></div></div>\n'
    "<h2>Work Experience</h2>"
    '<div class="role"><p class="role-line"><strong>Title</strong><span>Company</span>'
    '<span class="when">Mon YYYY - Mon YYYY</span></p><ul><li>bullet copied from the master CV</li></ul></div>\n'
    '<h2>Skills</h2><div class="skills"><p><strong>Category</strong><span>skill, skill</span></p></div>\n'
    '<h2>Education</h2><p class="role-line"><strong>Degree</strong><span>School</span>'
    '<span class="when">dates</span></p>\n'
    "One role block per job, newest first. Title, company, and dates stay on the role-line, never in the bullets. "
    "Keep the master CV's skill category names. One category per skills paragraph."
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


class TailoredCv(BaseModel):
    requirements: list[str] = Field(description="Requirements pulled from the posting")
    cv_html: str
    changes: list[CvChange]
    gaps: list[str] = Field(description="Requirements found in neither the master CV nor the profile")


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


async def run(state: CaseState, deps: Deps, store: BaseStore) -> dict[str, Any]:
    context = (
        f"Profile and master CV:\n{await profile_context(store)}\n\n"
        f"{fit_brief(state.get('fit') or {})}\n\n"
        f"Posting:\n{focused_posting(state['posting'])}"
    )
    cv = await asyncio.wait_for(
        ask(deps.model, TailoredCv, SYSTEM, context),
        timeout=PASS_TIMEOUT_SECONDS,
    )
    html = PAGE.format(body=clean_html(cv.cv_html))
    result = {**cv.model_dump(), "cv_html": html, "pdf": ""}
    if deps.chrome:
        pdf = await deps.chrome.render_pdf(html, deps.data_dir / "cvs" / f"{state['case_id']}.pdf")
        result["pdf"] = str(pdf)
    return {"cv": result, "stage": "tailored"}

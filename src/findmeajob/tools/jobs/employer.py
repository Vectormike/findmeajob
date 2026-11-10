import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "findmeajob/0.1 (personal job search)"}
AGGREGATORS = {"myjobmag"}
BOARDS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", "jobs", "title", ("absolute_url",)),
    ("https://api.ashbyhq.com/posting-api/job-board/{slug}", "jobs", "title", ("applyUrl", "jobUrl")),
    ("https://api.lever.co/v0/postings/{slug}?mode=json", "", "text", ("applyUrl", "hostedUrl")),
)


def _words(title: str) -> str:
    return " ".join(title.lower().split())


def _without_place(title: str) -> str:
    return _words(re.sub(r"\s*\([^)]*\)\s*$", "", title))


def _match(jobs: list[dict[str, Any]], title_key: str, title: str) -> dict[str, Any] | None:
    exact = [job for job in jobs if _words(job.get(title_key, "")) == _words(title)]
    close = exact or [job for job in jobs if _without_place(job.get(title_key, "")) == _without_place(title)]
    return close[0] if len(close) == 1 else None


async def _myjobmag_apply_url(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        page = (await client.get(url)).text
    except httpx.HTTPError:
        return None
    link = BeautifulSoup(page, "html.parser").select_one("a[href*='/apply-now/']")
    return urljoin(url, link["href"]) if link else None


async def employer_apply_url(posting: dict[str, Any]) -> str | None:
    company, title = posting.get("company", ""), posting.get("title", "")
    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
        if posting.get("source") in AGGREGATORS:
            return await _myjobmag_apply_url(client, posting["url"])
        if not slug or not title.strip():
            return None
        for url, jobs_key, title_key, link_keys in BOARDS:
            try:
                response = await client.get(url.format(slug=slug))
                if response.status_code != 200:
                    continue
                data = response.json()
            except (httpx.HTTPError, ValueError):
                continue
            jobs = data.get(jobs_key, []) if jobs_key else data
            job = _match(jobs if isinstance(jobs, list) else [], title_key, title)
            if job:
                return next((job[key] for key in link_keys if job.get(key)), None)
    return None

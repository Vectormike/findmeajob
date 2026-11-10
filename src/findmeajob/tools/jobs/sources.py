import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from findmeajob.tools.jobs.listing import Listing, html_to_text
from findmeajob.tools.jobs.logos import usable_logo

MAX_PAGES = 5
Fetch = Callable[[httpx.AsyncClient, str], Awaitable[list[Listing]]]


@dataclass(frozen=True)
class Source:
    name: str
    region: str | None
    fetch: Fetch


async def _arbeitnow_page(client: httpx.AsyncClient, page: int) -> list[Listing]:
    data = (await client.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page})).json()
    return [
        Listing(
            source="arbeitnow",
            title=job["title"],
            company=job["company_name"],
            url=job["url"],
            location=job["location"],
            description=html_to_text(job["description"]),
            remote=job["remote"],
            tags=job["tags"] + job["job_types"],
            posted_at=datetime.fromtimestamp(job["created_at"], UTC).date().isoformat(),
        )
        for job in data.get("data", [])
    ]


async def arbeitnow(client: httpx.AsyncClient, skill: str) -> list[Listing]:
    pages = await asyncio.gather(*(_arbeitnow_page(client, page) for page in range(1, MAX_PAGES + 1)))
    return [listing for page in pages for listing in page]


async def remotive(client: httpx.AsyncClient, skill: str) -> list[Listing]:
    data = (await client.get("https://remotive.com/api/remote-jobs", params={"search": skill})).json()
    return [
        Listing(
            source="remotive",
            title=job["title"],
            company=job["company_name"],
            url=job["url"],
            location=job["candidate_required_location"],
            description=html_to_text(job["description"]),
            remote=True,
            tags=job["tags"],
            salary=job["salary"],
            posted_at=job["publication_date"][:10],
            logo=job.get("company_logo") or "",
        )
        for job in data["jobs"]
    ]


async def remoteok(client: httpx.AsyncClient, skill: str) -> list[Listing]:
    data = (await client.get("https://remoteok.com/api")).json()
    return [
        Listing(
            source="remoteok",
            title=job["position"],
            company=job["company"],
            url=job["url"],
            apply_url=job.get("apply_url", ""),
            location=job.get("location", ""),
            description=html_to_text(job.get("description", "")),
            remote=True,
            tags=job.get("tags", []),
            salary=f"{job['salary_min']}-{job['salary_max']}" if job.get("salary_min") else "",
            posted_at=job.get("date", "")[:10],
            logo=job.get("company_logo") or job.get("logo") or "",
        )
        for job in data
        if "position" in job
    ]


async def jobicy(client: httpx.AsyncClient, skill: str) -> list[Listing]:
    tag = skill.lower().replace(".", "").replace(" ", "-")
    data = (await client.get("https://jobicy.com/api/v2/remote-jobs", params={"count": 100, "tag": tag})).json()
    return [
        Listing(
            source="jobicy",
            title=job["jobTitle"],
            company=job["companyName"],
            url=job["url"],
            location=job.get("jobGeo", ""),
            description=html_to_text(job.get("jobDescription", "")),
            remote=True,
            tags=[*job.get("jobIndustry", []), *job.get("jobType", [])],
            posted_at=job.get("pubDate", "")[:10],
            logo=job.get("companyLogo") or "",
        )
        for job in data.get("jobs", [])
    ]


async def _the_muse_page(client: httpx.AsyncClient, api_key: str, page: int) -> list[Listing]:
    data = (
        await client.get(
            "https://www.themuse.com/api/public/jobs",
            params={"api_key": api_key, "page": page},
        )
    ).json()
    listings = []
    for job in data.get("results", []):
        locations = [item["name"] for item in job.get("locations", []) if item.get("name")]
        location = ", ".join(locations)
        listings.append(
            Listing(
                source="themuse",
                title=job["name"],
                company=job.get("company", {}).get("name", ""),
                url=job.get("refs", {}).get("landing_page", ""),
                location=location,
                description=html_to_text(job.get("contents", "")),
                remote=any(word in location.lower() for word in ("remote", "flexible")),
                tags=[
                    *(item["name"] for item in job.get("categories", []) if item.get("name")),
                    *(item["name"] for item in job.get("levels", []) if item.get("name")),
                ],
                posted_at=job.get("publication_date", "")[:10],
            )
        )
    return listings


async def the_muse(client: httpx.AsyncClient, skill: str, api_key: str) -> list[Listing]:
    pages = await asyncio.gather(*(_the_muse_page(client, api_key, page) for page in range(MAX_PAGES)))
    return [listing for page in pages for listing in page]


async def _myjobmag_page(client: httpx.AsyncClient, skill: str, page: int) -> list[Listing]:
    url = f"https://www.myjobmag.com/search/jobs?q={quote_plus(skill)}&currentpage={page}"
    soup = BeautifulSoup((await client.get(url)).text, "html.parser")
    listings = []
    for row in soup.select("li.job-list-li"):
        link = row.select_one("li.mag-b h2 a")
        if not link:
            continue
        title, _, company = link.get_text(strip=True).rpartition(" at ")
        desc = row.select_one("li.job-desc")
        logo = row.select_one("li.job-logo img")
        listings.append(
            Listing(
                source="myjobmag",
                title=title or link.get_text(strip=True),
                company=company,
                url=urljoin("https://www.myjobmag.com", link["href"]),
                location="Nigeria",
                description=desc.get_text(" ", strip=True) if desc else "",
                logo=usable_logo(logo.get("src"), "https://www.myjobmag.com") if logo else "",
            )
        )
    return listings


async def myjobmag(client: httpx.AsyncClient, skill: str) -> list[Listing]:
    pages = await asyncio.gather(*(_myjobmag_page(client, skill, page) for page in range(1, MAX_PAGES + 1)))
    return [listing for page in pages for listing in page]


SOURCES = (
    Source("arbeitnow", "germany", arbeitnow),
    Source("myjobmag", "nigeria", myjobmag),
    Source("remotive", None, remotive),
    Source("remoteok", None, remoteok),
    Source("jobicy", None, jobicy),
)

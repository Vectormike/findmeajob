import asyncio
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from findmeajob.tools.web import HEADERS, search_hits

COMPANY_PAGES = "a[href*='/company/'], a[href^='/jobs-at/'], a[href*='/companies/']"
DEAD_LOGOS = ("logo.clearbit.com", "default-company-logo")
COMPANY_SUFFIXES = r"\b(global|limited|ltd|inc|llc|gmbh|technologies|technology|company|group|operations)\b\.?"
FAVICON = "https://www.google.com/s2/favicons?domain={host}&sz=128"


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _organizations(soup: BeautifulSoup) -> list[dict[str, Any]]:
    found = []
    for script in soup.select("script[type='application/ld+json']"):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(item, dict):
                found += [org for org in (item.get("hiringOrganization"), item) if isinstance(org, dict)]
    return found


def usable_logo(src: Any, base: str) -> str:
    return urljoin(base, src) if isinstance(src, str) and src and not any(d in src for d in DEAD_LOGOS) else ""


def _read(soup: BeautifulSoup, base: str, company: str) -> tuple[str, str]:
    """Return the company's logo and website named on a board page, when present."""
    name = _squash(company)
    logo = website = ""
    for org in _organizations(soup):
        if _squash(str(org.get("name", ""))) != name:
            continue
        logo = logo or usable_logo(org.get("logo"), base)
        links = [org.get("url"), *(org.get("sameAs") if isinstance(org.get("sameAs"), list) else [org.get("sameAs")])]
        website = website or next((u for u in links if isinstance(u, str) and u and _host(u) != _host(base)), "")
    for image in soup.find_all("img"):
        label = _squash(f"{image.get('alt', '')}{image.get('title', '')}")
        src = image.get("data-src") or image.get("src")
        if "company_logo" in str(src) or (name and label in (name, f"{name}logo")):
            logo = logo or usable_logo(src, base)
    return logo, website


def _favicon(website: str) -> str:
    return FAVICON.format(host=_host(website)) if website else ""


def _domain_name(url: str) -> str:
    labels = _host(url).split(".")
    if len(labels) > 2 and labels[-2] in ("co", "com", "org", "net"):
        return _squash(labels[-3])
    return _squash(labels[-2]) if len(labels) > 1 else ""


async def _website_from_search(company: str) -> str:
    name = _squash(re.sub(COMPANY_SUFFIXES, "", company, flags=re.I))
    if len(name) < 3:
        return ""
    for query in (f"{company} company official website", f"{company} careers"):
        try:
            hits = await asyncio.to_thread(search_hits, query, 8)
        except Exception:
            continue
        found = next((hit["url"] for hit in hits if _domain_name(hit["url"]) == name), "")
        if found:
            return found
    return ""


async def company_logo(posting: dict[str, Any]) -> str:
    url, company = posting.get("url", ""), posting.get("company", "")
    if posting.get("logo"):
        return posting["logo"]
    async with httpx.AsyncClient(headers=HEADERS, timeout=20, follow_redirects=True) as client:
        try:
            page = BeautifulSoup((await client.get(url)).text, "html.parser")
            logo, website = _read(page, url, company)
            link = page.select_one(COMPANY_PAGES)
            if not logo and link:
                company_page = urljoin(url, str(link["href"]))
                found, site = _read(BeautifulSoup((await client.get(company_page)).text, "html.parser"), url, company)
                logo, website = found, website or site
        except httpx.HTTPError:
            logo = website = ""
    return logo or _favicon(website) or _favicon(await _website_from_search(company))

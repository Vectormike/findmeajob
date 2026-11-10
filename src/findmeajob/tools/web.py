import asyncio
from typing import Any

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain_core.tools import tool

PAGE_LIMIT = 15000
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; findmeajob personal job search)"}


async def fetch_page(url: str) -> dict[str, str]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript", "svg"]):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else url
    text = "\n".join(line for line in soup.get_text("\n").splitlines() if line.strip())
    return {"url": str(response.url), "title": title, "text": text[:PAGE_LIMIT]}


def search_hits(query: str, max_results: int) -> list[dict[str, Any]]:
    return [
        {"title": hit.get("title", ""), "url": hit.get("href", ""), "snippet": hit.get("body", "")}
        for hit in DDGS().text(query, max_results=max_results)
    ]


@tool
async def search_web(query: str) -> list[dict[str, Any]]:
    """Search the public web and return titles, URLs, and snippets.

    Use site:reddit.com or site:glassdoor.com in the query to target a source."""
    return await asyncio.to_thread(search_hits, query, 8)


@tool
async def read_page(url: str) -> dict[str, str]:
    """Read a public web page and return its URL, title, and text. Pages behind a login are not read."""
    try:
        return await fetch_page(url)
    except httpx.HTTPError as error:
        return {"url": url, "title": "", "text": f"Could not read page: {error}"}

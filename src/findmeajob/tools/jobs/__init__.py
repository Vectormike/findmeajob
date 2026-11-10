import asyncio
import logging
from collections.abc import AsyncIterator
from functools import partial

import httpx

from findmeajob.tools.jobs.employer import HEADERS
from findmeajob.tools.jobs.listing import ARRANGEMENTS, Listing, matches, normalize_region, place_terms
from findmeajob.tools.jobs.sources import SOURCES, Source, the_muse

log = logging.getLogger(__name__)


def sources_for(region: str, arrangement: str, extras: tuple[Source, ...] = ()) -> list[Source]:
    covered = place_terms(region)
    available = (*SOURCES, *extras)
    regional = [source for source in available if source.region in covered]
    global_sources = [source for source in available if source.region == "global"]
    remote = [source for source in available if source.region is None]
    return regional + global_sources + remote if arrangement in ("remote", "any", "relocation") else regional + global_sources


async def search_job_batches(
    region: str,
    skill: str,
    arrangement: str,
    the_muse_api_key: str | None = None,
    title_only: bool = False,
) -> AsyncIterator[list[Listing]]:
    region = normalize_region(region)
    if arrangement not in ARRANGEMENTS:
        raise ValueError(f"arrangement must be one of {ARRANGEMENTS}")
    extras = (Source("themuse", "global", partial(the_muse, api_key=the_muse_api_key)),) if the_muse_api_key else ()
    sources = sources_for(region, arrangement, extras)
    async with httpx.AsyncClient(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        async def fetch(source: Source) -> tuple[Source, list[Listing] | Exception]:
            try:
                return source, await source.fetch(client, skill)
            except Exception as error:
                return source, error

        tasks = [asyncio.create_task(fetch(source)) for source in sources]
        for finished in asyncio.as_completed(tasks):
            source, result = await finished
            if isinstance(result, Exception):
                log.warning("source %s failed: %s", source.name, result)
                continue
            yield [
                listing
                for listing in result
                if matches(listing, region, skill, arrangement, source.region, title_only)
            ]


async def search_jobs(
    region: str,
    skill: str,
    arrangement: str,
    the_muse_api_key: str | None = None,
    title_only: bool = False,
) -> list[Listing]:
    batches = search_job_batches(region, skill, arrangement, the_muse_api_key, title_only)
    return [listing async for batch in batches for listing in batch]


__all__ = ["ARRANGEMENTS", "Listing", "search_job_batches", "search_jobs"]

import asyncio

from bs4 import BeautifulSoup

import findmeajob.tools.jobs as jobs
from findmeajob.tools.jobs import search_job_batches, sources_for
from findmeajob.tools.jobs.listing import Listing, matches, normalize_region
from findmeajob.tools.jobs.logos import _domain_name, _read
from findmeajob.tools.jobs.sources import Source, the_muse


def listing(**fields):
    return Listing(source="test", title="Backend Engineer", company="Acme", url="https://x", **fields)


def test_region_names_normalize():
    assert normalize_region("Nigerian") == "nigeria"
    assert normalize_region(" Germany ") == "germany"


def test_skill_must_appear():
    assert matches(listing(description="We use Node.js"), "germany", "Node.js", "any", "germany")
    assert matches(listing(description="We use NodeJS"), "germany", "Node.js", "any", "germany")
    assert not matches(listing(description="We use Go"), "germany", "Node.js", "any", "germany")


def test_career_filter_must_appear_in_the_job_title():
    backend = listing(description="You will work closely with our DevOps engineers.")
    devops = backend.model_copy(update={"title": "Senior Platform / DevOps Engineer"})
    assert not matches(backend, "germany", "DevOps Engineer", "any", "germany", title_only=True)
    assert matches(devops, "germany", "DevOps Engineer", "any", "germany", title_only=True)


def test_modern_role_aliases_match_real_job_titles():
    applied_ai = listing(description="", location="Berlin").model_copy(update={"title": "Senior AI Applied Engineer"})
    forward_deployed = listing(description="", location="Berlin").model_copy(
        update={"title": "Forward Deployed Software Engineer"}
    )
    assert matches(applied_ai, "germany", "Applied AI Engineer", "any", "germany", title_only=True)
    assert matches(forward_deployed, "germany", "Forward Deployed Engineer", "any", "germany", title_only=True)


def test_regional_board_still_checks_location():
    assert matches(listing(description="Node.js", location="Berlin, Germany"), "germany", "Node.js", "any", "germany")
    assert matches(listing(description="Node.js", location="Munich"), "germany", "Node.js", "any", "germany")
    assert matches(listing(description="Node.js", location="Homeoffice"), "germany", "Node.js", "remote", "germany")
    assert matches(listing(description="Node.js"), "germany", "Node.js", "any", "germany")
    assert matches(listing(description="Node.js", location="London, UK"), "uk", "Node.js", "any", None)
    assert not matches(listing(description="Node.js", location="Switzerland"), "germany", "Node.js", "any", "germany")


def test_remote_listing_counts_for_region_zone():
    remote_emea = listing(description="Node.js", remote=True, location="EMEA")
    assert matches(remote_emea, "nigeria", "Node.js", "remote", None)
    assert not matches(
        listing(description="Node.js", remote=True, location="USA only"), "nigeria", "Node.js", "remote", None
    )


def test_continent_covers_its_countries():
    berlin = listing(description="Node.js", location="Berlin, Germany")
    lagos = listing(description="Node.js", location="Lagos, Nigeria")
    assert matches(berlin, "europe", "Node.js", "any", None)
    assert not matches(lagos, "europe", "Node.js", "any", None)
    assert matches(lagos, "africa", "Node.js", "any", None)
    assert matches(listing(description="Node.js", location="Austin, USA"), "united states", "Node.js", "any", None)


def test_arrangement_filters():
    hybrid = listing(description="Node.js, hybrid in Berlin", location="Berlin, Germany")
    relocation = listing(description="Node.js, we offer relocation and visa sponsorship", location="Berlin, Germany")
    assert matches(hybrid, "germany", "Node.js", "hybrid", "germany")
    assert not matches(hybrid, "germany", "Node.js", "remote", "germany")
    assert matches(relocation, "germany", "Node.js", "relocation", "germany")
    assert matches(relocation, "germany", "Node.js", "onsite", "germany")


async def test_job_boards_stream_as_each_one_finishes(monkeypatch):
    async def slow(client, skill):
        await asyncio.sleep(0.05)
        return [listing(description=skill, location="Berlin", remote=True)]

    async def fast(client, skill):
        found = listing(description=skill, location="Berlin", remote=True)
        return [found.model_copy(update={"company": "Fast"})]

    monkeypatch.setattr(jobs, "SOURCES", (Source("slow", None, slow), Source("fast", None, fast)))
    batches = search_job_batches("germany", "Node.js", "remote")

    first = await anext(batches)
    assert [job.company for job in first] == ["Fast"]
    await batches.aclose()


async def test_the_muse_maps_its_official_job_shape():
    payload = {
        "results": [
            {
                "name": "Backend Engineer",
                "company": {"name": "Muse Co"},
                "refs": {"landing_page": "https://example.com/job"},
                "locations": [{"name": "Flexible / Remote"}],
                "contents": "<p>Build Node.js services.</p>",
                "categories": [{"name": "Engineering"}],
                "levels": [{"name": "Senior Level"}],
                "publication_date": "2026-11-08T12:00:00Z",
            }
        ]
    }

    class Response:
        def json(self):
            return payload

    class Client:
        calls = []

        async def get(self, url, params):
            self.calls.append((url, params))
            return Response()

    client = Client()
    found = await the_muse(client, "Backend Engineer", "secret")
    assert len(found) == 5
    assert found[0].company == "Muse Co"
    assert found[0].remote and found[0].tags == ["Engineering", "Senior Level"]
    assert client.calls[0][1] == {"api_key": "secret", "page": 0}


def test_the_muse_is_only_enabled_with_a_key():
    muse = Source("themuse", "global", lambda client, skill: None)
    assert muse not in sources_for("nigeria", "any")
    assert muse in sources_for("nigeria", "any", (muse,))



def test_logo_comes_from_the_hiring_company_structured_data():
    page = BeautifulSoup(
        '<script type="application/ld+json">{"hiringOrganization": {"name": "Monzo", "url": "https://monzo.com/",'
        ' "logo": "https://board.example/monzo.png"}}</script><img src="/images/logo.png" alt="Board logo">',
        "html.parser",
    )

    assert _read(page, "https://board.example/jobs/1", "Monzo") == ("https://board.example/monzo.png", "https://monzo.com/")


def test_logo_skips_placeholders_and_dead_services_but_keeps_the_website():
    page = BeautifulSoup(
        '<script type="application/ld+json">{"@type": "Organization", "name": "DuckDuckGo",'
        ' "url": "https://duckduckgo.com", "logo": "https://logo.clearbit.com/duckduckgo.com"}</script>'
        '<img src="/company_logo/86/default-company-logo.png">',
        "html.parser",
    )

    assert _read(page, "https://board.example/jobs/1", "DuckDuckGo") == ("", "https://duckduckgo.com")


def test_logo_matches_board_images_by_company_name():
    page = BeautifulSoup('<img src="/a.png" alt="Other logo"><img data-src="/acme.png" alt="Acme logo">', "html.parser")

    assert _read(page, "https://board.example/jobs/1", "Acme")[0] == "https://board.example/acme.png"


def test_search_websites_must_carry_the_company_name():
    assert _domain_name("https://www.nimble-byte.com/") == "nimblebyte"
    assert _domain_name("http://raincompany.co.kr/") == "raincompany"
    assert _domain_name("https://camel.dev-aemwork.net/") == "devaemwork"

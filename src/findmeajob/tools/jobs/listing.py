import re

from bs4 import BeautifulSoup
from pydantic import BaseModel

from findmeajob.tools.jobs.regions import ALIASES, CONTINENT_ZONES, REGIONS, continent_of

DEMONYMS = {"nigerian": "nigeria", "german": "germany", "british": "united kingdom", "uk": "united kingdom"}
ZONES = {
    "nigeria": ("africa", "emea"),
    "germany": ("europe", "emea", "eu", "deutschland"),
    "united kingdom": ("europe", "emea"),
}
PLACES = {
    "germany": (
        "deutschland",
        "berlin",
        "munich",
        "münchen",
        "hamburg",
        "frankfurt",
        "cologne",
        "köln",
        "düsseldorf",
        "stuttgart",
        "heidelberg",
        "leipzig",
        "dresden",
        "hannover",
        "nuremberg",
        "nürnberg",
        "bremen",
        "essen",
        "dortmund",
        "karlsruhe",
        "mannheim",
        "bonn",
        "potsdam",
        "baden-württemberg",
        "bavaria",
        "bayern",
        "north rhine-westphalia",
        "nordrhein-westfalen",
        "hessen",
    ),
    "nigeria": ("lagos", "abuja", "port harcourt", "ibadan", "kano", "enugu", "benin city", "kaduna"),
    "united kingdom": ("uk", "england", "scotland", "wales", "london", "manchester", "birmingham", "edinburgh"),
}
ANYWHERE = ("worldwide", "anywhere", "global")
REMOTE_WORDS = ("remote", "homeoffice", "home office")
ARRANGEMENTS = ("any", "remote", "hybrid", "onsite", "relocation")
TITLE_ALIASES = {
    "applied ai engineer": ("applied ai engineer", "ai applied engineer"),
    "forward deployed engineer": ("forward deployed engineer", "forward deployed software engineer"),
    "site reliability engineer": ("site reliability engineer", "sre"),
    "qa engineer": ("qa engineer", "quality assurance engineer", "test automation engineer"),
}


class Listing(BaseModel):
    source: str
    title: str
    company: str
    url: str
    location: str = ""
    apply_url: str = ""
    description: str = ""
    remote: bool = False
    tags: list[str] = []
    salary: str = ""
    posted_at: str = ""

    def searchable(self) -> str:
        return " ".join([self.title, " ".join(self.tags), self.description])


def html_to_text(html: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", BeautifulSoup(html or "", "html.parser").get_text("\n")).strip()


def normalize_region(region: str) -> str:
    key = region.strip().lower()
    return DEMONYMS.get(key, key)


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9+#]", "", text.lower())


def mentions(skill: str, text: str) -> bool:
    return _squash(skill) in _squash(text)


def title_mentions(role: str, title: str) -> bool:
    aliases = TITLE_ALIASES.get(role.strip().lower(), (role,))
    return any(mentions(alias, title) for alias in aliases)


def arrangement_of(listing: Listing) -> set[str]:
    text = f"{listing.location} {listing.searchable()}".lower()
    found = set()
    if listing.remote or any(word in listing.location.lower() for word in REMOTE_WORDS):
        found.add("remote")
    if "hybrid" in text:
        found.add("hybrid")
    if re.search(r"relocat|visa sponsor", text):
        found.add("relocation")
    if not found - {"relocation"}:
        found.add("onsite")
    return found


def _mentioned(location: str, places: tuple[str, ...]) -> bool:
    words = set(re.findall(r"[\w-]+", location))
    return any(place in location if " " in place else place in words for place in places)


def place_terms(region: str) -> tuple[str, ...]:
    key = normalize_region(region)
    if key in CONTINENT_ZONES:
        countries = tuple(name.lower() for name in REGIONS[key.title()])
    else:
        countries = (key,)
    found = [key]
    for country in countries:
        found.extend((country, *PLACES.get(country, ()), *ALIASES.get(country, ())))
    return tuple(dict.fromkeys(found))


def zone_terms(region: str) -> tuple[str, ...]:
    key = normalize_region(region)
    continent = key if key in CONTINENT_ZONES else continent_of(key)
    return CONTINENT_ZONES.get(continent or "", ZONES.get(key, ()))


def in_region(listing: Listing, region: str, board_region: str | None) -> bool:
    region = normalize_region(region)
    location = listing.location.lower()
    if board_region == region and (not location or location.strip() in REMOTE_WORDS):
        return True
    if _mentioned(location, place_terms(region)):
        return True
    if not listing.remote:
        return False
    return not location or any(word in location for word in (*ANYWHERE, *zone_terms(region)))


def matches(
    listing: Listing,
    region: str,
    skill: str,
    arrangement: str,
    board_region: str | None,
    title_only: bool = False,
) -> bool:
    found = title_mentions(skill, listing.title) if title_only else mentions(skill, listing.searchable())
    if not found:
        return False
    if not in_region(listing, region, board_region):
        return False
    return arrangement == "any" or arrangement in arrangement_of(listing)

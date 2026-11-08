REGIONS: dict[str, tuple[str, ...]] = {
    "Africa": (
        "Egypt",
        "Ethiopia",
        "Ghana",
        "Kenya",
        "Morocco",
        "Nigeria",
        "Rwanda",
        "South Africa",
        "Tanzania",
        "Uganda",
    ),
    "Asia": (
        "Bangladesh",
        "China",
        "Hong Kong",
        "India",
        "Indonesia",
        "Israel",
        "Japan",
        "Malaysia",
        "Pakistan",
        "Philippines",
        "Singapore",
        "South Korea",
        "Taiwan",
        "Thailand",
        "United Arab Emirates",
        "Vietnam",
    ),
    "Europe": (
        "Austria",
        "Belgium",
        "Czechia",
        "Denmark",
        "Finland",
        "France",
        "Germany",
        "Greece",
        "Ireland",
        "Italy",
        "Netherlands",
        "Norway",
        "Poland",
        "Portugal",
        "Romania",
        "Spain",
        "Sweden",
        "Switzerland",
        "Ukraine",
        "United Kingdom",
    ),
    "North America": ("Canada", "Mexico", "United States"),
    "South America": ("Argentina", "Brazil", "Chile", "Colombia", "Peru"),
    "Oceania": ("Australia", "New Zealand"),
}

CONTINENT_ZONES: dict[str, tuple[str, ...]] = {
    "africa": ("africa", "emea"),
    "asia": ("asia", "apac"),
    "europe": ("europe", "emea", "eu"),
    "north america": ("north america", "americas"),
    "south america": ("south america", "latam", "americas"),
    "oceania": ("oceania", "apac", "anz"),
}

ALIASES: dict[str, tuple[str, ...]] = {
    "united states": ("usa", "us"),
    "united kingdom": ("uk", "britain"),
    "united arab emirates": ("uae", "dubai"),
    "czechia": ("czech republic",),
    "south korea": ("korea",),
}


def groups() -> list[dict[str, list[str]]]:
    return [{"name": name, "countries": sorted(countries)} for name, countries in REGIONS.items()]


def continent_of(country: str) -> str | None:
    for name, countries in REGIONS.items():
        if country in {item.lower() for item in countries}:
            return name.lower()
    return None

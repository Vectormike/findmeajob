from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class AtsStrategy:
    name: str
    hosts: tuple[str, ...] = ()
    next_selectors: tuple[str, ...] = ()
    submit_selectors: tuple[str, ...] = ()
    success_selectors: tuple[str, ...] = ()


GENERIC = AtsStrategy("generic")

STRATEGIES = (
    AtsStrategy(
        "greenhouse",
        ("greenhouse.io", "greenhouse.com"),
        submit_selectors=("#submit_app", 'button[type="submit"]'),
        success_selectors=("#application_confirmation", ".application-confirmation"),
    ),
    AtsStrategy(
        "lever",
        ("lever.co",),
        next_selectors=('[data-qa="next-button"]',),
        submit_selectors=('[data-qa="submit-button"]', ".template-btn-submit"),
        success_selectors=(".application-confirmation", '[data-qa="application-success"]'),
    ),
    AtsStrategy(
        "ashby",
        ("ashbyhq.com",),
        next_selectors=('button[data-testid*="next"]',),
        submit_selectors=('button[data-testid*="submit"]', 'button[type="submit"]'),
        success_selectors=('[data-testid*="success"]', ".ashby-application-form-success-container"),
    ),
    AtsStrategy(
        "workday",
        ("myworkdayjobs.com", "workday.com"),
        next_selectors=('[data-automation-id="bottom-navigation-next-button"]',),
        submit_selectors=('[data-automation-id="bottom-navigation-submit-button"]',),
        success_selectors=(
            '[data-automation-id="congratulationsPage"]',
            '[data-automation-id="applicationConfirmation"]',
        ),
    ),
)


def strategy_for(url: str) -> AtsStrategy:
    host = (urlparse(url).hostname or "").lower()
    return next(
        (
            strategy
            for strategy in STRATEGIES
            if any(host == item or host.endswith(f".{item}") for item in strategy.hosts)
        ),
        GENERIC,
    )

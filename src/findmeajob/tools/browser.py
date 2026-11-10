import asyncio
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from findmeajob.tools.browser_ats import AtsStrategy, strategy_for
from findmeajob.tools.browser_js import CAPTCHA_OPEN, READ_ERRORS, READ_FIELDS, SUCCESS_WORDS

Handoff = Callable[[Any, bool], Awaitable[None]]
CAPTCHA_WAIT_SECONDS = 300

APPLY = re.compile(r"apply", re.I)
SUBMIT = re.compile(r"submit|send application|apply", re.I)
NEXT = re.compile(r"next|continue|review|save and continue", re.I)
APPLICATION = re.compile(r"\b(e-?mail|phone|mobile|resume|cv|full name|first name|last name)\b", re.I)
GOOGLE_SIGN_IN = re.compile(r"^https://accounts\.google\.com/", re.I)
SIGN_IN = re.compile(r"accounts\.google\.com|login\.microsoftonline\.com|/(sign-?in|log-?in)\b", re.I)
CODE = re.compile(r"security code|verification code|confirmation code|one-time code", re.I)
CONTROLS = "a, button, [role='button'], input[type='submit'], input[type='button'], .button"
YES = {"yes", "true", "y", "1", "checked"}
MAX_OPTIONS = 60
OPTION_EXAMPLES = 6
OPTION_WAIT_MS = 4000
DISABLED_WAIT_MS = 2000
SETTLE_MS = 5000


class Blocked(Exception):
    pass


class FormSession:
    def __init__(self, page: Any, handoff: Handoff | None = None) -> None:
        self.page = page
        self.handoff = handoff
        self.strategy: AtsStrategy = strategy_for(page.url)
        self.started = False

    async def _guard(self) -> None:
        with suppress(PlaywrightTimeoutError):
            await self.page.wait_for_load_state("networkidle", timeout=SETTLE_MS)
        found = strategy_for(self.page.url)
        if found.name != "generic":
            self.strategy = found
        if await self._captcha_open():
            await self._wait_for_person(
                self._captcha_open,
                "the page has a bot check. we're not doing captchas.",
                "the captcha wasn't finished in time. retry Clerk to fill the form again.",
            )
        if await self._google_sign_in():
            await self._wait_for_person(
                self._google_sign_in,
                "this form needs a Google sign-in. retry Clerk and sign in once in the live view.",
                "the Google sign-in wasn't finished in time. retry Clerk to sign in.",
            )
        if SIGN_IN.search(self.page.url) or await self.page.locator("input[type=password]:visible").count():
            raise Blocked("this page wants a login. that's a no from us.")

    async def _google_sign_in(self) -> bool:
        return bool(GOOGLE_SIGN_IN.search(self.page.url))

    async def _captcha_open(self) -> bool:
        return bool(await self.page.evaluate(CAPTCHA_OPEN))

    async def _code_needed(self) -> bool:
        text = (await self.page.locator("body").inner_text()).lower()
        return bool(CODE.search(text)) and not any(word in text for word in SUCCESS_WORDS)

    async def _wait_for_person(self, waiting: Callable[[], Awaitable[bool]], alone: str, late: str) -> None:
        if not self.handoff:
            raise Blocked(alone)
        await self.handoff(self.page, True)
        try:
            for _ in range(CAPTCHA_WAIT_SECONDS):
                await asyncio.sleep(1)
                with suppress(PlaywrightError):
                    if not await waiting():
                        break
            else:
                raise Blocked(late)
        finally:
            await self.handoff(self.page, False)
        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(1500)

    def _application(self, fields: list[dict[str, Any]]) -> bool:
        return any(field["type"] == "file" or APPLICATION.search(field.get("label") or "") for field in fields)

    async def _text(self, item: Any) -> str:
        text = " ".join((await item.inner_text()).split())
        return text or " ".join(((await item.get_attribute("value")) or "").split())

    async def _control(self, pattern: re.Pattern[str]) -> Any | None:
        for role in ("button", "link"):
            candidate = self.page.get_by_role(role, name=pattern).first
            if await candidate.count() and await candidate.is_visible() and await self._wanted(candidate, pattern):
                return candidate
        for item in await self.page.locator(CONTROLS).all():
            if await item.is_visible() and await self._wanted(item, pattern):
                return item
        return None

    async def _wanted(self, item: Any, pattern: re.Pattern[str]) -> bool:
        text = await self._text(item)
        if pattern is NEXT and re.search(r"\bjob\b", text, re.I):
            return False
        return bool(pattern.search(text))

    async def _pick(self, entry: Any, value: str) -> None:
        options = self.page.locator("[role='option']:visible")
        with suppress(PlaywrightTimeoutError):
            await options.first.wait_for(timeout=OPTION_WAIT_MS)
        labels = [" ".join(label.split()).lower() for label in await options.all_inner_texts()]
        wanted = " ".join(value.split()).lower()
        for matches in (str.__eq__, str.startswith, str.__contains__):
            index = next((i for i, label in enumerate(labels) if matches(label, wanted)), None)
            if index is not None:
                await options.nth(index).click()
                return
        await entry.press("Enter")

    async def _read(self) -> list[dict[str, Any]]:
        fields = await self.page.evaluate(READ_FIELDS)
        for field in fields:
            if field["type"] != "combobox" or field.get("options"):
                continue
            try:
                await self.page.locator(f'[data-fmaj="{field["id"]}"]').click(timeout=2000)
                await self.page.wait_for_timeout(300)
                labels = await self.page.locator("[role='option']:visible").all_inner_texts()
                if len(labels) <= MAX_OPTIONS:
                    field["options"] = [{"id": label.strip(), "label": label.strip()} for label in labels]
                else:
                    field["examples"] = [label.strip() for label in labels[:OPTION_EXAMPLES]]
            except PlaywrightError:
                pass
            await self.page.keyboard.press("Escape")
        return fields

    async def fields(self) -> list[dict[str, Any]]:
        await self._guard()
        fields = await self._read()
        if self.started or self._application(fields):
            self.started = True
            return fields
        control = await self._control(APPLY)
        if control is None:
            if fields:
                self.started = True
                return fields
            raise Blocked("no apply button, no form. the posting is playing hide and seek.")
        before = len(self.page.context.pages)
        await control.click()
        await self.page.wait_for_load_state("domcontentloaded")
        if len(self.page.context.pages) > before:
            self.page = self.page.context.pages[-1]
            await self.page.wait_for_load_state("domcontentloaded")
        await self._guard()
        fields = await self._read()
        if not self._application(fields):
            raise Blocked("clicked apply but no application form showed up. the board may want a sign-in first.")
        self.started = True
        return fields

    async def errors(self) -> list[str]:
        return await self.page.evaluate(READ_ERRORS)

    async def fill(self, fields: list[dict[str, Any]], answers: dict[str, str], cv_pdf: Path) -> None:
        file_inputs = [field for field in fields if field["type"] == "file"]
        for field in fields:
            value = answers.get(field["id"], "")
            target = self.page.locator(f'[data-fmaj="{field["id"]}"]')
            if field["type"] == "file":
                if len(file_inputs) == 1 or re.search(r"resume|cv", field["label"], re.I):
                    await target.set_input_files(str(cv_pdf))
            elif not value:
                continue
            elif field["type"] == "radio":
                option = next((o for o in field["options"] if o["label"].lower() == value.lower()), None)
                if option:
                    choice = self.page.locator(f'[data-fmaj="{option["id"]}"]')
                    if await choice.get_attribute("role") == "radio":
                        await choice.click()
                    else:
                        await choice.check()
            elif field["type"] == "checkbox":
                if value.lower() in YES:
                    if await target.get_attribute("role") == "checkbox":
                        if await target.get_attribute("aria-checked") != "true":
                            await target.click()
                    else:
                        await target.check()
            elif field["type"] == "select":
                option = next((o for o in field["options"] if o["label"].lower() == value.lower()), None)
                await target.select_option(option["id"] if option else value)
            elif field["type"] == "combobox":
                entry = target.locator("input").first
                if await entry.count():
                    await entry.fill(value)
                elif await target.get_attribute("contenteditable") == "true":
                    entry = target
                    await entry.fill(value)
                else:
                    entry = target
                    await entry.click()
                    await self.page.keyboard.type(value)
                await self._pick(entry, value)
            elif field["type"] == "contenteditable":
                await target.fill(value)
            else:
                await target.fill(value)

    async def _visible(self, selectors: tuple[str, ...]) -> Any | None:
        for selector in selectors:
            candidate = self.page.locator(selector).first
            if await candidate.count() and await candidate.is_visible():
                return candidate
        return None

    async def _confirmation(self) -> dict[str, str]:
        text = (await self.page.inner_text("body"))[:3000]
        selector_hit = bool(await self._visible(self.strategy.success_selectors))
        confirmed = selector_hit or any(word in text.lower() for word in SUCCESS_WORDS)
        return {"url": self.page.url, "page_text": text, "confirmed": "yes" if confirmed else "no"}

    async def advance(self) -> dict[str, Any]:
        await self._guard()
        before = [(field["type"], field["label"]) for field in await self.page.evaluate(READ_FIELDS)]
        next_button = await self._visible(self.strategy.next_selectors) or await self._control(NEXT)
        kind = "next"
        button = next_button
        if not button:
            kind = "submit"
            button = await self._visible(self.strategy.submit_selectors)
            button = button or await self._visible(('button[type="submit"]', 'input[type="submit"]'))
            button = button or await self._control(SUBMIT)
        if not button:
            raise Blocked("no next or submit button showed up.")
        if await button.is_disabled():
            await self.page.wait_for_timeout(DISABLED_WAIT_MS)
        if await button.is_disabled():
            stuck = "the submit button is still disabled, so a required field is empty or invalid."
            return {"status": "validation", "errors": await self.errors() or [stuck]}

        pages = set(self.page.context.pages)
        await button.click()
        await self.page.wait_for_timeout(500)
        opened = [page for page in self.page.context.pages if page not in pages]
        if opened:
            self.page = opened[-1]
            await self.page.wait_for_load_state("domcontentloaded")
            self.strategy = strategy_for(self.page.url)
        self.started = True
        await self._guard()
        if kind == "submit":
            with suppress(PlaywrightTimeoutError):
                await self.page.wait_for_load_state("networkidle", timeout=SETTLE_MS)
            if await self._code_needed():
                await self._wait_for_person(
                    self._code_needed,
                    "the site emailed a security code to finish the application. retry Clerk to enter it live.",
                    "the security code wasn't entered in time. retry Clerk to fill the form again.",
                )
        errors = await self.errors()
        after = [(field["type"], field["label"]) for field in await self.page.evaluate(READ_FIELDS)]
        if kind == "next" and after != before:
            return {"status": "advanced", "url": self.page.url}
        if errors:
            return {"status": "validation", "errors": errors}
        if kind == "next":
            return {"status": "advanced", "url": self.page.url}
        confirmation = await self._confirmation()
        if confirmation["confirmed"] == "yes":
            return {"status": "submitted", "confirmation": confirmation}
        if await self._control(SUBMIT):
            reason = "the site left the form open, so the application was not accepted."
            return {"status": "validation", "errors": await self.errors() or [reason]}
        return {"status": "unconfirmed", "confirmation": confirmation}


import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from findmeajob.tools.browser_ats import AtsStrategy, strategy_for
from findmeajob.tools.browser_js import READ_ERRORS, READ_FIELDS, SUCCESS_WORDS

APPLY = re.compile(r"apply", re.I)
SUBMIT = re.compile(r"submit|send application|apply", re.I)
NEXT = re.compile(r"next|continue|review|save and continue", re.I)
BOT_CHECK = re.compile(r"recaptcha|hcaptcha|turnstile|captcha", re.I)
YES = {"yes", "true", "y", "1", "checked"}


class Blocked(Exception):
    pass


class FormSession:
    def __init__(self, page: Any) -> None:
        self.page = page
        self.strategy: AtsStrategy = strategy_for(page.url)
        self.started = False

    async def _guard(self) -> None:
        if any(BOT_CHECK.search(frame.url) for frame in self.page.frames):
            raise Blocked("the page has a bot check. we're not doing captchas.")
        if await self.page.locator(
            'iframe[src*="captcha"], [class*="captcha"], [id*="captcha"], [data-sitekey]'
        ).count():
            raise Blocked("the page has a bot check. we're not doing captchas.")
        if await self.page.locator("input[type=password]:visible").count():
            raise Blocked("this page wants a login. that's a no from us.")

    async def fields(self) -> list[dict[str, Any]]:
        await self._guard()
        fields = await self.page.evaluate(READ_FIELDS)
        if self.started or len([field for field in fields if field["type"] != "file"]) >= 2:
            self.started = True
            return fields
        before = len(self.page.context.pages)
        link = self.page.get_by_role("link", name=APPLY).or_(self.page.get_by_role("button", name=APPLY)).first
        if not await link.count():
            raise Blocked("no apply button, no form. the posting is playing hide and seek.")
        await link.click()
        await self.page.wait_for_load_state("domcontentloaded")
        if len(self.page.context.pages) > before:
            self.page = self.page.context.pages[-1]
            await self.page.wait_for_load_state("domcontentloaded")
        await self._guard()
        fields = await self.page.evaluate(READ_FIELDS)
        if not [field for field in fields if field["type"] != "file"]:
            raise Blocked("clicked apply and the page had zero fields. rude.")
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
                option = self.page.get_by_role("option", name=value, exact=True).first
                try:
                    await option.wait_for(state="visible", timeout=1500)
                    await option.click()
                except PlaywrightTimeoutError:
                    await entry.press("Enter")
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

    async def _role_button(self, name: re.Pattern[str]) -> Any | None:
        candidate = self.page.get_by_role("button", name=name).first
        return candidate if await candidate.count() and await candidate.is_visible() else None

    async def _confirmation(self) -> dict[str, str]:
        text = (await self.page.inner_text("body"))[:3000]
        selector_hit = bool(await self._visible(self.strategy.success_selectors))
        confirmed = selector_hit or any(word in text.lower() for word in SUCCESS_WORDS)
        return {"url": self.page.url, "page_text": text, "confirmed": "yes" if confirmed else "no"}

    async def advance(self) -> dict[str, Any]:
        await self._guard()
        before = [(field["type"], field["label"]) for field in await self.page.evaluate(READ_FIELDS)]
        next_button = await self._visible(self.strategy.next_selectors) or await self._role_button(NEXT)
        kind = "next"
        button = next_button
        if not button:
            kind = "submit"
            button = await self._visible(self.strategy.submit_selectors)
            button = button or await self._visible(('button[type="submit"]', 'input[type="submit"]'))
            button = button or await self._role_button(SUBMIT)
        if not button:
            raise Blocked("no next or submit button showed up.")

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
        errors = await self.errors()
        after = [(field["type"], field["label"]) for field in await self.page.evaluate(READ_FIELDS)]
        if kind == "next" and after != before:
            return {"status": "advanced", "url": self.page.url}
        if errors:
            return {"status": "validation", "errors": errors}
        if kind == "next":
            return {"status": "advanced", "url": self.page.url}
        confirmation = await self._confirmation()
        return {
            "status": "submitted" if confirmation["confirmed"] == "yes" else "unconfirmed",
            "confirmation": confirmation,
        }


class Chrome:
    def __init__(self, profile_dir: Path, headless: bool) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self._playwright: Any = None
        self._context: Any = None
        self._pdf_browser: Any = None

    async def _start(self) -> None:
        if not self._playwright:
            self._playwright = await async_playwright().start()
        if not self._context:
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(self.profile_dir), channel="chrome", headless=self.headless
            )

    async def _start_pdf(self) -> None:
        if not self._playwright:
            self._playwright = await async_playwright().start()
        if not self._pdf_browser:
            self._pdf_browser = await self._playwright.chromium.launch(channel="chrome", headless=True)

    @asynccontextmanager
    async def fill_form(self, url: str) -> AsyncIterator[FormSession]:
        await self._start()
        existing = set(self._context.pages)
        page = await self._context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            yield FormSession(page)
        finally:
            for open_page in self._context.pages:
                if open_page not in existing:
                    await open_page.close()

    async def render_pdf(self, html: str, path: Path) -> Path:
        await self._start_pdf()
        path.parent.mkdir(parents=True, exist_ok=True)
        page = await self._pdf_browser.new_page()
        await page.set_content(html, wait_until="load")
        await page.pdf(
            path=str(path), format="A4", margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"}
        )
        await page.close()
        return path

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._pdf_browser:
            await self._pdf_browser.close()
            self._pdf_browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

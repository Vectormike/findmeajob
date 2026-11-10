import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from findmeajob.tools.browser import FormSession

FILL_TIMEOUT_SECONDS = 600
NETWORK_HICCUPS = (
    "ERR_ABORTED",
    "ERR_NETWORK_CHANGED",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_CLOSED",
    "ERR_INTERNET_DISCONNECTED",
    "ERR_TIMED_OUT",
)
NETWORK_RETRY_SECONDS = 2


class Chrome:
    def __init__(self, profile_dir: Path, headless: bool) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self._playwright: Any = None
        self._context: Any = None
        self._pdf_browser: Any = None
        self._fill_lock = asyncio.Lock()
        self.live: dict[str, Any] = {}

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
    async def fill_form(
        self, url: str, case_id: str | None = None, notify: Callable[[bool], None] | None = None
    ) -> AsyncIterator[FormSession]:
        async def handoff(page: Any, waiting: bool) -> None:
            if waiting:
                self.live[case_id] = page
            else:
                self.live.pop(case_id, None)
            if notify:
                notify(waiting)

        async with self._fill_lock, asyncio.timeout(FILL_TIMEOUT_SECONDS):
            await self._start()
            existing = set(self._context.pages)
            page = await self._context.new_page()
            try:
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                except Exception as error:
                    if not any(hiccup in str(error) for hiccup in NETWORK_HICCUPS):
                        raise
                    await asyncio.sleep(NETWORK_RETRY_SECONDS)
                    await page.goto(url, wait_until="domcontentloaded")
                yield FormSession(page, handoff if case_id else None)
            finally:
                self.live.pop(case_id, None)
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

    async def healthcheck(self) -> None:
        await self._start()
        page = await self._context.new_page()
        await page.set_content("<title>Clerk ready</title>")
        await page.close()

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

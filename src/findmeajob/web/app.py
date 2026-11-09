import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from findmeajob.agents.deps import Deps
from findmeajob.agents.inbox import poll_forever
from findmeajob.config import Settings, get_settings
from findmeajob.llm import get_model
from findmeajob.memory import open_memory, set_status
from findmeajob.tools.browser import Chrome
from findmeajob.tools.gmail import Gmail
from findmeajob.web import api_cases, api_pages
from findmeajob.workflow import Workflow


class SinglePageApp(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def create_app(settings: Settings | None = None, deps: Deps | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with open_memory(settings) as (checkpointer, store):
            run_deps = deps or Deps(
                model=get_model(settings),
                data_dir=settings.data_dir,
                chrome=Chrome(settings.chrome_profile_dir, settings.chrome_headless),
            )
            ready = run_deps.model is not None
            await set_status(
                store, "xai", ready, settings.xai_model if ready else "no key. the agents can't think without it."
            )
            await set_status(store, "chrome", run_deps.chrome is not None, "headless Clerk browser ready")
            if not deps and settings.gmail_token_file.exists():
                try:
                    run_deps.gmail = Gmail(settings.gmail_token_file)
                    await set_status(store, "gmail", True, "Gmail connected")
                except Exception as error:
                    await set_status(store, "gmail", False, f"gmail said no: {error}"[:300])
            workflow = Workflow(run_deps, checkpointer, store)
            poller = None
            if run_deps.gmail and not deps:
                poller = asyncio.create_task(poll_forever(workflow, settings.courier_poll_seconds))
            app.state.settings = settings
            app.state.workflow = workflow
            app.state.tasks = set()
            app.state.gmail_poller = poller
            yield
            if app.state.gmail_poller:
                app.state.gmail_poller.cancel()
                with suppress(asyncio.CancelledError):
                    await app.state.gmail_poller
            if run_deps.chrome and not deps:
                await run_deps.chrome.close()

    app = FastAPI(title="findmeajob", lifespan=lifespan)
    app.include_router(api_cases.router)
    app.include_router(api_pages.router)
    if settings.ui_dir.is_dir():
        app.mount("/", SinglePageApp(directory=settings.ui_dir, html=True), name="ui")
    return app

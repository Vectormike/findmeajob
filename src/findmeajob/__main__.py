import argparse
import asyncio
import logging

import uvicorn

from findmeajob.agents import scout
from findmeajob.agents.deps import Deps
from findmeajob.config import get_settings
from findmeajob.llm import get_model
from findmeajob.memory import open_memory
from findmeajob.tools.browser import Chrome
from findmeajob.tools.gmail import authorize
from findmeajob.tools.jobs.listing import ARRANGEMENTS
from findmeajob.workflow import Workflow


async def sweep(region: str, skill: str, arrangement: str) -> None:
    settings = get_settings()
    chrome = Chrome(settings.chrome_profile_dir, settings.chrome_headless)
    async with open_memory(settings) as (checkpointer, store):
        deps = Deps(model=get_model(settings), data_dir=settings.data_dir, chrome=chrome)
        try:
            opened = await scout.run(
                Workflow(deps, checkpointer, store),
                region,
                skill,
                arrangement,
                settings.scout_max_cases,
                settings.the_muse_api_key,
            )
        finally:
            await chrome.close()
    print(f"Opened {opened} new cases.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="findmeajob")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the dashboard and the Courier")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    run = commands.add_parser("scout", help="Sweep job boards once and run the new cases")
    run.add_argument("region")
    run.add_argument("skill")
    run.add_argument("--arrangement", choices=ARRANGEMENTS, default="any")
    commands.add_parser("gmail-auth", help="Connect Gmail (read and send only)")
    args = parser.parse_args()

    settings = get_settings()
    if args.command == "serve":
        uvicorn.run("findmeajob.web.app:create_app", factory=True, host=args.host, port=args.port)
    elif args.command == "scout":
        asyncio.run(sweep(args.region, args.skill, args.arrangement))
    else:
        authorize(settings.gmail_credentials_file, settings.gmail_token_file)
        print(f"Gmail connected. Token saved to {settings.gmail_token_file}.")


if __name__ == "__main__":
    main()

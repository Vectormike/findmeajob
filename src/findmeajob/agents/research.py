from typing import Any

from langchain.agents import create_agent
from pydantic import BaseModel

from findmeajob.llm import NO_KEY
from findmeajob.tools.web import read_page, search_web

RESEARCH_PROMPT = (
    "You research public sources for a job seeker. Use search_web to find pages, then read_page to read them. "
    "Use only public pages; skip anything behind a login. Every claim you return must carry the URL it came from. "
    "If a source says nothing useful, leave it out rather than guessing."
)


async def research[T: BaseModel](model: Any, task: str, schema: type[T]) -> T:
    if model is None:
        raise RuntimeError(NO_KEY)
    agent = create_agent(model, tools=[search_web, read_page], system_prompt=RESEARCH_PROMPT, response_format=schema)
    result = await agent.ainvoke({"messages": [("human", task)]}, {"recursion_limit": 40})
    return result["structured_response"]

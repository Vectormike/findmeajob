from typing import Any

from langchain_xai import ChatXAI
from pydantic import BaseModel

from findmeajob.config import Settings

NO_KEY = "no xai key, so the agents are just standing there. drop XAI_API_KEY in .env and they'll lock in."


def get_model(settings: Settings) -> ChatXAI | None:
    if not settings.xai_api_key:
        return None
    return ChatXAI(model=settings.xai_model, api_key=settings.xai_api_key, temperature=0.2)


async def ask[T: BaseModel](
    model: Any, schema: type[T], system: str, user: str, reasoning_effort: str | None = None
) -> T:
    if model is None:
        raise RuntimeError(NO_KEY)
    if reasoning_effort:
        model = model.model_copy(update={"reasoning_effort": reasoning_effort})
    return await model.with_structured_output(schema).ainvoke([("system", system), ("human", user)])

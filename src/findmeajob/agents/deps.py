from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from findmeajob.agents.research import research
from findmeajob.tools.web import fetch_page


@dataclass
class Deps:
    model: Any
    data_dir: Path
    chrome: Any = None
    gmail: Any = None
    research: Callable[..., Awaitable[Any]] = research
    fetch_page: Callable[[str], Awaitable[dict[str, str]]] = fetch_page

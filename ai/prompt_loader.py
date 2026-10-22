"""ai/prompt_loader.py

Loads prompt text files from /prompts and fills {{placeholders}}
with the user's own chart data.
"""
import re
from functools import lru_cache
from pathlib import Path

from core.exceptions import PromptError

# <project root>/prompts   (this file lives in <project root>/ai/)
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@lru_cache(maxsize=None)
def _read(relative_path: str) -> str:
    path = PROMPTS_DIR / relative_path
    if not path.is_file():
        raise PromptError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def load_prompt(relative_path: str, **values) -> str:
    """load_prompt("past_life/fifth_lord_karma.txt", fifth_lord="Venus", ...)"""
    template = _read(relative_path)

    missing = set(_PLACEHOLDER.findall(template)) - set(values)
    if missing:
        raise PromptError(f"Missing values for {relative_path}: {sorted(missing)}")

    return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)
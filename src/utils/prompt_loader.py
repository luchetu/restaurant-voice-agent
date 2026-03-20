from functools import lru_cache
from pathlib import Path

import yaml

from src.config.menu import get_menu_summary


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache()
def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    instructions = data.get("instructions", "")
    instructions = instructions.replace("{menu}", get_menu_summary())
    return instructions
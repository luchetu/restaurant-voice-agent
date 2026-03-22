from functools import lru_cache
from pathlib import Path
from datetime import datetime
from typing import Optional

import yaml

from src.config.menu import get_menu_summary

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@lru_cache()
def load_prompt(name: str) -> str:
    """Load a prompt by exact name and inject menu."""
    path = PROMPTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    instructions = data.get("instructions", "")
    instructions = instructions.replace("{menu}", get_menu_summary())
    return instructions


def load_prompt_variant(
    name: str,
    customer_name: Optional[str] = None,
) -> str:
    """
    Load the most specific prompt variant available
    based on time of day and whether the caller is returning.

    Priority order:
    1. Returning customer variant  (if customer name is known)
    2. Time-of-day variant         (lunch / dinner)
    3. Base prompt                 (always available as fallback)
    """
    hour = datetime.now().hour

    # Signal 1 — returning customer takes highest priority
    if customer_name:
        try:
            return load_prompt(f"{name}_returning")
        except FileNotFoundError:
            pass

    # Signal 2 — time of day
    if 11 <= hour < 15:
        time_variant = f"{name}_lunch"
    elif 18 <= hour < 22:
        time_variant = f"{name}_dinner"
    else:
        time_variant = None

    if time_variant:
        try:
            return load_prompt(time_variant)
        except FileNotFoundError:
            pass

    # Signal 3 — fall back to base prompt
    return load_prompt(name)


def get_active_variant_name(
    name: str,
    customer_name: Optional[str] = None,
) -> str:
    """
    Returns which variant was selected — useful for logging.
    """
    hour = datetime.now().hour

    if customer_name and (PROMPTS_DIR / f"{name}_returning.yaml").exists():
        return f"{name}_returning"

    if 11 <= hour < 15 and (PROMPTS_DIR / f"{name}_lunch.yaml").exists():
        return f"{name}_lunch"

    if 18 <= hour < 22 and (PROMPTS_DIR / f"{name}_dinner.yaml").exists():
        return f"{name}_dinner"

    return name
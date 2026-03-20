import json
from pathlib import Path
from functools import lru_cache

@lru_cache()
def get_menu() -> dict:
    path = Path(__file__).parent.parent.parent / "data" / "menu.json"
    with open(path) as f:
        return json.load(f)



def get_menu_summary() -> str:
    """Plain-text menu summary injected into agent prompts."""
    menu = get_menu()
    lines = []
    for category in menu["categories"]:
        lines.append(f"{category['name']:}")
        for item in category["items"]:
            lines.append(f"  - {item['name']}: ${item['price']:.2f}")
    return "\n".join(lines)

def get_all_item_names() -> list[str]:
        """Used by order validation to check items actually exist."""
        menu = get_menu()
        return [
        item["name"]
        for category in menu["categories"]
        for item in category["items"]
    ]



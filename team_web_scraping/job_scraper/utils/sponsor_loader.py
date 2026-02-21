import json
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
H1B_LIST_PATH = CONFIG_DIR / "h1b_keys.json"
EVERIFY_LIST_PATH = CONFIG_DIR / "everify_keys.json"

def load_sponsor_lists() -> Tuple[List[str], List[str]]:
    """
    Loads h1b and everify company list.
    """
    with open(H1B_LIST_PATH, "r", encoding="utf-8") as f:
        h1b_list = json.load(f)

    with open(EVERIFY_LIST_PATH, "r", encoding="utf-8") as f:
        everify_list = json.load(f)
    
    return h1b_list, everify_list

if __name__ == "__main__":
    h1b_list, everify_list = load_sponsor_lists()
    print(len(h1b_list))
    print(h1b_list[:10])
    print(len(everify_list))
    print(everify_list[:10])


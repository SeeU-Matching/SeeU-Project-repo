import json
from pathlib import Path
from typing import Dict, List

from job_scraper.models.enums import JobCategory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_PATH = CONFIG_DIR / "job_keywords.json"

def load_job_keywords() -> Dict[JobCategory, List[str]]:
    """
    Loads job keywords and validates them against JobCategory enum.
    Returns:
        Dict[JobCategory, List[str]]
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    keywords: Dict[JobCategory, List[str]] = {}
    categories = set(item.value for item in JobCategory)
    missing = []

    for key, values in raw.items():
        try:
            category = JobCategory(key)
        except ValueError as exc:
            raise ValueError(f"Unknown job category in config: '{key}'") from exc

        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise TypeError(f"Keywords for '{key}' must be a list of strings")

        keywords[category] = [v.lower() for v in values]
        if keywords[category] == []:
            missing.append(key)
        categories.remove(key)

    missing.extend(categories)
    if len(missing) > 0:
        print(f"Warning: No keywords found for categories: {', '.join(missing)}")
    return keywords

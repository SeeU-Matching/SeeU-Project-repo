import json
import pandas as pd
from pathlib import Path
from .normalize import normalize_company_name

def load_and_process(csv_path: Path, col: str) -> list[str]:
    """Load a CSV, extract company name"""
    df = pd.read_csv(csv_path, usecols=[col], dtype=str, encoding="utf-16", sep="\t")
    names = df[col].map(normalize_company_name)
    names = names[names.str.len() > 0]
    names = names.drop_duplicates()

    return names.tolist()


def save_json(keys: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(keys, f, indent=2)
    print(f"  Saved → {path}")

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parent

# Processed key lists (output of sponsor_prep.py)
H1B_KEYS_JSON      = BASE_DIR / "h1b_keys.json"
EVERIFY_KEYS_JSON  = BASE_DIR / "everify_keys.json"

# ── Raw CSV column names ──────────────────────────────────────────────────────
H1B_COMPANY_COL     = "Employer (Petitioner) Name"       # USCIS H1B disclosure data
EVERIFY_COMPANY_COL = "Employer"   # E-Verify employer search export

# ── Fuzzy matching thresholds ─────────────────────────────────────────────────
THRESHOLD_TOKEN_SORT = 90   # Layer 2: same words, different order
THRESHOLD_TOKEN_SET  = 88   # Layer 3: one name is subset of the other
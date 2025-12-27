# InfoMatching_Team4/qwen_evaluator.py
import json
import os
from openai import OpenAregion.)
DEFAULT_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
DEFAULT_MODEL = os.getenv("QWEN_MODEL", "q]{index=1}

def _load_qwen_ktching_Team4/
    key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
    if key and key.strip():
        return key.strip()

    key_path = os.path.join(os.path.dirname(__file__), "qwen_key.txt")
    if os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as f:
            k = f.read().strip()
            if k:
                return k

    raise RuntimeError(
        "No Qwen API key found. Set DASHSCOPE_API_KEY (recommended) or create InfoMatching_Team4/qwen_key.txt."
    )

def _client() -> OpenAI:
    return OpenAI(api_key=_load_qwen_key(), base_url=DEFAULT_BASE_URL)

SYSTEM_PROMPT = """You are an evaluator for a resume-job matching system.
Given a candidate resume (structured text) and a job posting (structured text), rate match quality into:
- HIGH: strong alignment on core requirements + skills + experience; clear fit
- MEDIUM: partial alignment; some key gaps; still plausible with training/adjacent experience
- LOW: weak alignment; major requirement gaps; unlikely fit

Return STRICT JSON ONLY with keys:
{
  "rating": "LOW"|"MEDIUM"|"HIGH",
  "confidence": 0.0-1.0,
  "reasons": ["...","...","..."],
  "key_gaps": ["...","..."]
}
Keep reasons concise and grounded in provided text. No extra keys.
"""

def rate_match(resume_text: str, job_text: str, *, temperature: float = 0.2) -> dict:
    resp = _client().chat.completions.create(
        model=DEFAULT_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"RESU}\n"},
        ],
        # Encourage JSON-only output
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    tcontent)
    except Exception:
        # last-resort fallback
        data = {"rating": "MEDIUM", "confidence": 0.3, "reasons": ["Failed to parse model output"], "key_gaps": []}

    # Normalize
    rating = str(data.get("rating", "MEDIUM")).upper().strip()
    if rating not in {"LOW", "MEDIUM", "HIGH"}:
        rating = "MEDIUM"
    data["rating"] = rating

    try:
        conf = float(data.get("confidence", 0.5))
    except Exception:
        conf = 0.5
    data["confidence"] = max(0.0, min(1.0, conf))

    if not isinstance(data.get("reasons", []), list):
        data["reasons"] = [str(data.get("reasons"))]
    if not isinstance(data.get("key_gaps", []), list):
        data["key_gaps"] = [str(data.get("key_gaps"))]

    return data

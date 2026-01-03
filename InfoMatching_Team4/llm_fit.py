# InfoMatching_Team4/llm_fit.py
import os, json, re, hashlib
from typing import Dict, Any, Optional
from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # cheap + good :contentReference[oaicite:3]{index=3}
KEY_FILE = "openai_key.txt"


def _load_openai_key() -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))  # repo root
    key_path = os.path.join(base_dir, KEY_FILE)
    if not os.path.exists(key_path):
        raise FileNotFoundError("openai_key.txt not found in project root")
    with open(key_path, "r", encoding="utf-8") as f:
        key = f.read().strip().replace("\ufeff", "")
    if not key:
        raise ValueError("openai_key.txt is empty")
    return key


def _client() -> OpenAI:
    return OpenAI(api_key=_load_openai_key())


def _h(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\{.*\})", text, flags=re.DOTALL)
    if m:
        return json.loads(m.group(1))
    return json.loads(text)


def rate_fit(
    resume_text: str,
    jd_text: str,
    cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    resume_text = (resume_text or "")[:12000]
    jd_text = (jd_text or "")[:12000]

    key = f"{_h(resume_text)}::{_h(jd_text)}"
    if cache is not None and key in cache:
        return cache[key]

    system_prompt = (
        "You are a strict job-resume matching evaluator. "
        "Return ONLY valid JSON with keys: rating, reasons, confidence. "
        "rating must be exactly one of: High, Medium, Low."
    )

    user_payload = {
        "resume": resume_text,
        "job_description": jd_text,
        "rubric": {
            "High": "Strong alignment on responsibilities, skills, and experience evidence",
            "Medium": "Partial alignment; missing key requirements or weak evidence",
            "Low": "Weak alignment; wrong domain/level or insufficient experience"
        },
        "output": {"rating": "High|Medium|Low", "reasons": ["1-3 short reasons"], "confidence": "0-1"}
    }

    resp = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        temperature=0.0,
    )

    out = _extract_json(resp.choices[0].message.content)

    rating = str(out.get("rating", "Medium")).strip().title()
    if rating not in {"High", "Medium", "Low"}:
        rating = "Medium"

    reasons = out.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    reasons = [str(r).strip() for r in reasons if str(r).strip()][:3]

    conf = out.get("confidence", 0.5)
    try:
        conf = float(conf)
    except Exception:
        conf = 0.5
    conf = max(0.0, min(1.0, conf))

    result = {"rating": rating, "reasons": reasons, "confidence": conf}
    if cache is not None:
        cache[key] = result
    return result

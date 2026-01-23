import os
import json
import hashlib
from typing import Dict, Any, Optional
from openai import OpenAI

# Qwen models via Alibaba Model Studio (OpenAI-compatible)
MODEL = "qwen-plus"
# MODEL = "qwen-turbo"
# MODEL = "qwen-max"

# International OpenAI-compatible endpoint for Model Studio / Qwen
BASE_URL = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        # Use a separate key file for Model Studio (sk-...) to avoid mixing with OpenAI keys
        key_path = os.path.join(os.path.dirname(__file__), "qwen_key.txt")
        with open(key_path, "r", encoding="utf-8") as f:
            api_key = f.read().strip()

        _client = OpenAI(api_key=api_key, base_url=BASE_URL)
    return _client


def _cache_key(resume_text: str, jd_text: str) -> str:
    h = hashlib.sha256()
    h.update(resume_text.encode("utf-8", errors="ignore"))
    h.update(b"\n---\n")
    h.update(jd_text.encode("utf-8", errors="ignore"))
    return h.hexdigest()


SYSTEM_PROMPT = """

You are a strict job-resume matching evaluator.

You MUST evaluate match quality using ONLY the student's EXPERIENCE text (internships + projects) versus the JD text.
Do NOT use education/degree/major/GPA.
Do NOT invent any information.

Return ONLY valid JSON with exactly:
{
"score": integer, // 0..100
"rating_raw": string // "Low" | "Medium" | "High"
}

CORE PRINCIPLE:
This evaluation is based on BOTH internship/work experience AND project experience.
If the student lacks relevant internship/work experience, strong and directly relevant projects can still justify Medium or High.
Use semantic similarity between what the student did and the JD responsibilities (not keyword matching).

STEP 1) Identify the BEST MATCHING EXPERIENCE BLOCK:

From the student's EXPERIENCE text, find the single most relevant block, which can be either:
(A) an internship/work experience, OR
(B) a project experience.

Prefer internship/work if both are equally relevant, but projects can substitute when internships are not relevant.

STEP 2) Title/Role Similarity Score (0..40):

Compare the JD job title to the student's role titles (internship titles OR project titles).

title_score =
40 if there exists a role title highly similar to the JD title (same role family).
25 if adjacent/related role family.
10 if weakly related.
0 if unrelated.
NOTE: If the best matching block is a PROJECT, its title may be informal; infer role similarity from what the project is about.

STEP 3) Task Semantic Match (compute match_ratio first):

Extract ONLY 4 to 6 actionable responsibilities from the JD (exclude soft traits and education).

Choose the responsibilities that are the MOST central to the role (not generic filler).

For each responsibility, check if the BEST MATCHING EXPERIENCE BLOCK shows concrete evidence of doing similar work.

Generic words like "analysis" without context do NOT count.

Let K = number of responsibilities, X = number matched.

match_ratio = X / K (0..1).

STEP 4) Base Task Score (0..60):

task_score = round(60 * match_ratio).

STEP 5) Domain Compatibility Gate:

Determine whether the student's EXPERIENCE domain and the JD domain are compatible.

If domains are clearly incompatible (e.g., student's experience is CS/Data only while JD is Arts/Psychology only),
then rating_raw MUST be Low and score MUST be <= 45.

STEP 6) Base Score:

base_score = clamp(title_score + task_score, 0, 100).

STEP 7) Rating + Score Calibration (IMPORTANT):

Decide rating_raw using the rules below, then calibrate score so High is not stuck at 75–80.

RATING RULES:

High if domain is compatible AND one of the following holds:
(A) BEST MATCH is internship/work AND title_score >= 25 AND match_ratio >= 0.60
(B) BEST MATCH is project AND match_ratio >= 0.75 (projects must be very close to justify High)

Medium if domain is compatible AND (match_ratio >= 0.35) AND base_score >= 50

Low otherwise.

SCORE CALIBRATION (MUST APPLY):

If rating_raw == "High":
score = max(base_score, 85 + round(15 * (match_ratio - 0.60) / 0.40))
Then clamp score to 85..100.

If rating_raw == "Medium":
score = clamp(base_score, 55, 84)

If rating_raw == "Low":
score = clamp(base_score, 0, 54)

Output JSON only. No markdown. No extra keys.

"""


def rate_fit(
    resume_experience_text: str,
    jd_text: str,
    cache: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ck = _cache_key(resume_experience_text, jd_text)
    if cache is not None and ck in cache:
        return cache[ck]

    resume_experience_text = (resume_experience_text or "").strip()[:3500]
    jd_text = (jd_text or "").strip()[:3500]

    payload = {"resume_experience": resume_experience_text, "job_description": jd_text}

    resp = _get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content or "{}"
    try:
        obj = json.loads(raw)
    except Exception:
        obj = {}

    score = obj.get("score", 0)
    try:
        score = float(score)
    except Exception:
        score = 0.0
    score = max(0.0, min(100.0, score))

    rating = obj.get("rating_raw", "Low")
    if rating not in ("Low", "Medium", "High"):
        rating = "Low"

    out = {"score": round(score, 2), "rating_raw": rating}

    if cache is not None:
        cache[ck] = out
    return out



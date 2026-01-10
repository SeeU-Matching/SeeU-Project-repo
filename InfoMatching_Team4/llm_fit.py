import os
import json
import hashlib
from typing import Dict, Any, Optional
from openai import OpenAI

MODEL = "gpt-4o-mini"
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key_path = os.path.join(os.path.dirname(__file__), "gpt_key.txt")
        with open(key_path, "r", encoding="utf-8") as f:
            api_key = f.read().strip()
        _client = OpenAI(api_key=api_key)
    return _client


def _cache_key(resume_text: str, jd_text: str) -> str:
    h = hashlib.sha256()
    h.update(resume_text.encode("utf-8", errors="ignore"))
    h.update(b"\n---\n")
    h.update(jd_text.encode("utf-8", errors="ignore"))
    return h.hexdigest()


SYSTEM_PROMPT = """

You are a strict job-resume matching evaluator.

Evaluate match quality using ONLY the student's EXPERIENCE text (internships + projects) versus the JD text.
Do NOT use education/degree/major/GPA.
Do NOT reward generic soft traits (self-motivated, communication, curiosity, integrity, etc.).
Do NOT invent any skills/tools not explicitly present in EXPERIENCE.

Return ONLY valid JSON with exactly:
{
  "score": integer,        // 0..100
  "rating_raw": string     // "Low" | "Medium" | "High"
}

CRITICAL OUTPUT RULE:
- score MUST NOT be a multiple of 10 (e.g., 30, 40, 50, 60...).
- Do NOT output only boundary values.

SCORING OVERVIEW (STRICT):
Final score = clamp(task_score + skills_score - penalty, 0, 100)
- task_score: 0..60 (semantic match to JD core tasks)
- skills_score: 0..40 (required tools/skills evidence)
- penalty: 0..30 (missing critical capabilities / domain mismatch)

STEP 1) Extract JD DOMAIN (choose ONE):
Finance/Accounting/Treasury | Marketing/Growth | Healthcare/Clinical | Tech/Software | Operations/SupplyChain | General Business/Analytics

Use JD content (e.g., forecast vs actual, accounting teams, hedging, cash management => Finance/Accounting/Treasury).

STEP 2) Extract JD CORE TASKS (3 to 7 items):
- Only include actionable responsibilities producing outputs.
- Exclude soft traits and education requirements.
Let K = number of core tasks.

STEP 3) Task Semantic Match Score (0..60):
- For each core task, check if EXPERIENCE has concrete evidence of doing similar work (semantic match).
- Generic words like "analysis" without context do NOT count.
Let X = matched task count (0..K).
task_score = round(60 * X / K)

STEP 4) Extract JD REQUIRED HARD SKILLS/TOOLS (max 12):
- Include concrete hard skills/tools required to do the job.
- Exclude Word/PowerPoint/Zoom/Teams/Slack by default.
- Include Excel ONLY if JD explicitly emphasizes it for analysis.
Let T = number of required skills/tools.

STEP 5) Skills/Tools Evidence Score (0..40):
- Let M = number of required skills/tools explicitly evidenced in EXPERIENCE.
- IMPORTANT: If a skill/tool is only listed without showing it was used to do work, count as HALF-match.
Compute effective_matched = M_full + 0.5*M_half
If T == 0: skills_score = 10
Else: skills_score = round(40 * effective_matched / T)

STEP 6) CRITICAL CAPABILITY CHECK (for penalty and strictness):
Identify up to 5 CRITICAL CAPABILITIES from the JD that are truly essential (not soft traits).
Examples:
- Finance/Accounting/Treasury: forecast vs actual / variance analysis, financial statements, accounting workflows,
  treasury topics (hedging, cash management, capital planning), budgeting, reconciliation, financial reporting.
- Marketing/Growth: campaign KPIs, attribution, web analytics tagging tools, funnel metrics.
- Healthcare/Clinical: HCP engagement, patient/clinical domain data, compliance.
- Tech/Software: coding, systems, APIs, deployment.

For each critical capability, check if EXPERIENCE has evidence.
Let C = number of critical capabilities, Y = number matched.

STEP 7) Penalty (0..30) — MUST APPLY WHEN KEY GAPS EXIST:
A) Missing critical capability penalty:
- If Y/C < 0.50: penalty += 15 to 25 (strong), depending on how central the missing items are.
- If 0.50 <= Y/C < 0.80: penalty += 5 to 12 (moderate).
- If Y/C >= 0.80: penalty += 0 to 4 (minimal).

B) Domain mismatch penalty (to prevent cross-domain inflation):
- If JD domain is Finance/Accounting/Treasury, then to avoid inflated scores you MUST require at least ONE of:
  (i) financial statements analysis (P&L/BS/CF), OR
  (ii) forecast/variance/budgeting analysis, OR
  (iii) treasury-specific work (hedging/cash/capital planning), OR
  (iv) accounting/finance operations reporting.
  If NONE exist in EXPERIENCE: penalty += 15 AND cap final score at 59 (cannot be Medium/High).
- If JD domain is Marketing/Growth and NONE of campaign/web/email/social analytics exist: penalty += 15 AND cap at 59.

STEP 8) Final Score:
score_raw = task_score + skills_score - penalty
score = clamp(score_raw, 0, 100)

If a domain cap rule triggered, score = min(score, 59).

STEP 9) Rating:
High if score >= 85 (rare; requires strong task match + skills evidence + minimal penalty)
Medium if 60..84
Low if < 60

Output JSON only. No markdown.

"""


def rate_fit(resume_experience_text: str, jd_text: str, cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ck = _cache_key(resume_experience_text, jd_text)
    if cache is not None and ck in cache:
        return cache[ck]

    # Truncate to keep runtime reasonable
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
    )

    raw = resp.choices[0].message.content or "{}"
    try:
        obj = json.loads(raw)
    except Exception:
        obj = {}

    # minimal hardening
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


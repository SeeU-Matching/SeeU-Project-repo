import json
import os
import re

import pandas as pd

# Use local Qwen2-3B (transformers) when True; otherwise use OpenAI.
USE_LOCAL_LLM = True

if not USE_LOCAL_LLM:
    from openai import OpenAI
    key_file_path = os.path.join(os.path.dirname(__file__), "key.txt")
    with open(key_file_path, "r") as file:
        key = file.read()
    client = OpenAI(api_key=key)


# Numeric codes for faster model output; we convert back to text for DB/matching.
DEGREE_CODE = {0: "Not specified", 1: "Bachelor", 2: "Master", 3: "PhD"}
DOMAIN_CODE = [
    "Computer Science", "Business", "Engineering", "Arts", "Science", "Healthcare",
    "Education", "Law", "Media / Communications", "Social Sciences", "Agriculture",
    "Hospitality / Tourism", "Architecture", "Finance",
]


def extract_job_data(jd):
    result = {}
    prompt = """Extract 2 fields as JSON with numbers only (shorter = faster):

1) minimum_academic_qualification: one number 0-3. 0=Not specified, 1=Bachelor, 2=Master, 3=PhD. If multiple degrees, output minimum number.
2) experience_domain: list of numbers 1-14. 1=Computer Science, 2=Business, 3=Engineering, 4=Arts, 5=Science, 6=Healthcare, 7=Education, 8=Law, 9=Media/Comm, 10=Social Sciences, 11=Agriculture, 12=Hospitality, 13=Architecture, 14=Finance. One or more that match.

Example: {"minimum_academic_qualification":1,"experience_domain":[1,3]}
Plain JSON only. Job: """ + str(jd)
    try:
        if USE_LOCAL_LLM:
            from local_qwen import generate as local_generate
            raw = local_generate(prompt, max_new_tokens=128)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```\w*\n?", "", raw)
                raw = re.sub(r"\n?```\s*$", "", raw)
        else:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.choices[0].message.content
        try:
            result = json.loads(raw)
            # Convert numbers back to text for DB and matching
            if "minimum_academic_qualification" in result and result.get("error") is None:
                q = result["minimum_academic_qualification"]
                if isinstance(q, int) and 0 <= q <= 3:
                    result["minimum_academic_qualification"] = DEGREE_CODE[q]
            if "experience_domain" in result and result.get("error") is None:
                d = result["experience_domain"]
                if isinstance(d, list):
                    out = [DOMAIN_CODE[x - 1] for x in d if isinstance(x, int) and 1 <= x <= 14]
                    if out:
                        result["experience_domain"] = out
                elif isinstance(d, int) and 1 <= d <= 14:
                    result["experience_domain"] = [DOMAIN_CODE[d - 1]]
        except Exception as e:
            return {"error": f"Failed to parse JD JSON: {e}", "raw": raw}
    except Exception as e:
        return {"error": f"Failed to process JD: {e}"}
    return result

# file_path = './CS.xlsx'
# df = pd.read_excel(file_path)
# jd1 = df['岗位要求'][20]
# result = extract_job_data(jd1)
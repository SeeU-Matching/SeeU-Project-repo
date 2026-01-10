# resume_interface.py (UPDATED: experience-focused option added)

import os
import json
import PyPDF2
import argparse
from enum import Enum
from openai import OpenAI
from pydantic import BaseModel

# -----------------------------
# Client selection (GPT ONLY — DeepSeek disabled)
# -----------------------------
key_file_path = os.path.join(os.path.dirname(__file__), "gpt_key.txt")
with open(key_file_path, "r", encoding="utf-8") as file:
    key = file.read().strip()

client = OpenAI(api_key=key)
model_name = "gpt-4o-mini"
print("Using GPT-4o-mini.")

# -----------------------------
# Output types
# -----------------------------
class ExperienceType(Enum):
    DETAIL = 1
    SUMMARY = 2
    SENTENCE = 3
    EXPERIENCE_ONLY = 4  # NEW: only name + experiences


class DatailedExperience(BaseModel):
    job_title: str
    organization: str
    start_date: str
    end_date: str
    description: str


class SummaryExperience(BaseModel):
    job_title: str
    organization: str
    business_task: str
    result: str
    skill_stack: str
    duration: str


class DetailResume(BaseModel):
    name: str
    school: list[str]
    gpa: list[str]
    major: list[str]
    graduation_time: str
    tech_skills: list[str]
    business_domain: list[str]
    experiences: list[DatailedExperience]


class SummaryResume(BaseModel):
    name: str
    school: list[str]
    gpa: list[str]
    major: list[str]
    graduation_time: str
    tech_skills: list[str]
    business_domain: list[str]
    experiences: list[SummaryExperience]


class BriefResume(BaseModel):
    name: str
    phone: str
    email: str
    address: str
    links: list[str]
    school: list[str]
    gpa: list[str]
    major: list[str]
    degree: list[str]
    graduation_time: str
    tech_skills: list[str]
    business_domain: list[str]
    experiences: list[str]

class ExperienceItem(BaseModel):
    title_line: str          
    bullets: list[str] 


class ExperienceOnlyResume(BaseModel):
    name: str
    experiences: list[ExperienceItem]


# -----------------------------
# Public API
# -----------------------------
def read_resume(file_path=None, file_object=None, detailed_level=ExperienceType.SENTENCE):
    error_message = ""

    if file_path:
        if os.path.exists(file_path) and file_path.endswith(".pdf"):
            with open(file_path, "rb") as file:
                return extract_student_info(file, detailed_level)
        if not os.path.exists(file_path):
            error_message = "File does not exist at " + file_path + ","
        elif not file_path.endswith(".pdf"):
            error_message = "File path does not end with .pdf,"
        else:
            error_message = "Invalid file path,"

    if file_object:
        if not hasattr(file_object, "read") or not hasattr(file_object, "name"):
            error_message += " and no valid file object provided."
            raise Exception(error_message)

        if file_object.name.endswith(".pdf"):
            return extract_student_info(file_object, detailed_level)

        error_message += " and invalid file object format. Please upload a PDF file."
        raise Exception(error_message)

    error_message += "No file path or file object provided."
    raise Exception(error_message)


def extract_student_info(file, detailed_level=ExperienceType.SENTENCE):
    text = extract_text_from_pdf(file)
    llm_response = llm_parse(text, detailed_level)
    return json.loads(llm_response)


def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ""
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text += page.extract_text() or ""
    return text


# -----------------------------
# LLM parse (UPDATED)
# -----------------------------
def llm_parse(text, detailed_experience=ExperienceType.SENTENCE):
    # Choose schema/prompt based on desired output level
    if detailed_experience == ExperienceType.EXPERIENCE_ONLY:
        experiment_prompt = (
            "Extract ALL experiences from the resume, exhaustively.\n"
            "Experiences MUST include BOTH:\n"
            "1) Professional / internship / work experience\n"
            "2) Projects (individual or team)\n\n"
            "CRITICAL RULES:\n"
            "- Do NOT merge different roles into one item.\n"
            "- Do NOT drop any role or project that appears in the resume.\n"
            "- Output one bullet per role/project.\n"
            "- If the resume has N roles/projects, output N items.\n"
            "- Each item must be 1-2 sentences and include (if present): task + tools/skills + impact.\n"
            "- If a tool/skill is not explicitly in the resume text, do NOT invent it.\n"
            "- Include organization/company/school-lab name for each item.\n"
        )
        resume_schema = ExperienceOnlyResume.model_json_schema()
    elif detailed_experience == ExperienceType.DETAIL:
        experiment_prompt = (
            "detailed experiences (include work, intern, project, and others) "
            "with job title, organization, start and end date (YYYY-MM or present), "
            "and description from the student resume."
        )
        resume_schema = DetailResume.model_json_schema()
    elif detailed_experience == ExperienceType.SUMMARY:
        experiment_prompt = (
            "summarized experiences (include work, intern, project, and others) "
            "with job title, organization, business_task (about 20 words), result, "
            "skill_stack, and duration in month (e.g. 3 months) from the student resume."
        )
        resume_schema = SummaryResume.model_json_schema()
    else:
        experiment_prompt = "summarized experiences, each in one or two sentences."
        resume_schema = BriefResume.model_json_schema()

    # response_format differs by provider
    if model_name == "deepseek-chat":
        response_format = {"type": "json_object"}
    else:
        response_format = {"type": "json_schema", "json_schema": {"name": "resume", "schema": resume_schema}}

    # System prompt: keep old fields instruction for backward compatibility,
    # but EXPERIENCE_ONLY mode will be schema-limited to {name, experiences}.
    system_prompt = (
        "You are a recruiter looking to extract information from a student resume.\n"
        "Always output plain JSON without any markdown or formatting, only the raw JSON object.\n"
        "Please respond in English.\n\n"
        "Extract the name (should have white space between first name and last name), phone, email, address, links, "
        "school(s), gpa(s) (e.g. 3.85/4.00), major(s) (without degree), degree(s), graduation_time (YYYY-MM), "
        "tech_skills (e.g., Python, SQL), business_domain(s) and "
        + experiment_prompt
        + "\n\n"
        'CRITICAL: For "degree" field, output a list with ONLY "Bachelor", "Master", or "PhD".\n'
        'CRITICAL: For "business_domain" field, output a list with ONLY these 14 domains: '
        '"Computer Science", "Business", "Engineering", "Arts", "Science", "Healthcare", "Education", "Law", '
        '"Media / Communications", "Social Sciences", "Agriculture", "Hospitality / Tourism", "Architecture", "Finance".\n'
    )

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Resume\n" + text},
        ],
        response_format=response_format,
        temperature=0.00,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume Reader")
    parser.add_argument("--file_path", type=str, help="Path to the resume PDF file")
    parser.add_argument(
        "--detailed_level",
        type=str,
        default="SENTENCE",
        choices=["DETAIL", "SUMMARY", "SENTENCE", "EXPERIENCE_ONLY"],
        required=False,
        help="Level of detail to extract from the resume",
    )
    parser.add_argument("--output", type=str, help="Output file path", required=False)
    args = parser.parse_args()

    result = read_resume(args.file_path, detailed_level=ExperienceType[args.detailed_level])

    if isinstance(result, dict) and "error" in result:
        print(result["error"])
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        print("Resume data extracted successfully and saved to", args.output)
    else:
        print(json.dumps(result, indent=4, ensure_ascii=False))



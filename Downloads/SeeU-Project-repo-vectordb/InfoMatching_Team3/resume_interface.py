import os
import json
import PyPDF2
import argparse
from enum import Enum
from openai import OpenAI
from pydantic import BaseModel

try:
    key_file_path = os.path.join(os.path.dirname(__file__), 'ds_key.txt')
    with open(key_file_path, 'r') as file:
        key = file.read().strip()
    if not key:
        raise ValueError("DeepSeek API key is empty")
    client = OpenAI(
        api_key=key, 
        base_url="https://api.deepseek.com/v1",
    )
    model_name = "deepseek-chat"
    test_response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "user", "content": "Hi"},
        ],
    )
    print('Using DeekSeek.')
except Exception as e:
    try:
        key_file_path = os.path.join(os.path.dirname(__file__), 'gpt_key.txt')
        with open(key_file_path, 'r') as file:
            key = file.read().strip()
        if not key:
            raise ValueError("OpenAI API key is empty")
        print("API key loaded (length:", len(key), ")")
        client = OpenAI(
            api_key=key,
        )
        model_name = "gpt-4o-mini"
        test_response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": "Hi"},
            ],
        )
        print('Using GPT-4o-mini.')
        print("Not using DeepSeek because: ", e)
    except Exception as e2:
        print('No valid API key found. Please provide a valid API key in a text file named "gpt_key.txt" or "ds_key.txt" in the same directory as the script.')
        print("Not using DeepSeek because: ", e)
        print("Not using GPT-4o-mini because: ", e2)

class ExperienceType(Enum):
    DETAIL = 1
    SUMMARY = 2
    SENTENCE = 3

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

def read_resume(file_path=None, file_object=None, detailed_level=ExperienceType.SENTENCE):
    error_message = ''

    # Handle file path input
    if file_path:
        if os.path.exists(file_path) and file_path.endswith('.pdf'):
            with open(file_path, 'rb') as file:
                return extract_student_info(file, detailed_level)
        if not os.path.exists(file_path):
            error_message = "File does not exist at " + file_path + ","
        elif not file_path.endswith('.pdf'):
            error_message = "File path does not end with .pdf," 
        else:
            error_message = "Invalid file path," 

    # Handle file object input
    if file_object:
        if not hasattr(file_object, 'read') or not hasattr(file_object, 'name'):
            error_message += " and no valid file object provided."
            raise Exception(error_message)

        if file_object.name.endswith('.pdf'):
            return extract_student_info(file_object, detailed_level)

        error_message += " and invalid file object format. Please upload a PDF file."
        raise Exception(error_message)

    # If no valid inputs provided
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
        text += page.extract_text()
    return text

def llm_parse(text, detailed_experience=False):
    if model_name == "deepseek-chat":
        experiment_prompt = "summarized experiences, each in one or two sentences."
        format = {'type': 'json_object'}
    else:
        if detailed_experience == ExperienceType.DETAIL:
            experiment_prompt = "detailed experiences (include work, intern, project, and others) with job title, organization, start and end date (YYYY-MM or present), and description from the student resume."
            resume_schema = DetailResume.model_json_schema()
        elif detailed_experience == ExperienceType.SUMMARY:
            experiment_prompt = "summarized experiences (include work, intern, project, and others) with job title, organization, business_task (for about 20 words), result, skill_stack, and duration in month (e.g. 3 months) from the student resume."
            resume_schema = SummaryResume.model_json_schema()
        else:
            experiment_prompt = "summarized experiences, each in one or two sentences."
            resume_schema = BriefResume.model_json_schema()
        format = {'type': 'json_schema', 'json_schema': {'name': 'resume', 'schema': resume_schema}}
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {'role': 'system', 'content': """You are a recruiter looking to extract information from a student resume. 
Extract the name (should have white space between first name and last name), phone, email, address, links, school(s), gpa(s) (e.g. 3.85/4.00), major(s) (without degree, e.g. Master of Science in Information should be Information Science), degree(s) (e.g. Master of Science in Information), graduation_time (YYYY-MM), tech_skills (e.g., Python, SQL), business_domain(s) (or industry of company despite schools, at least two, e.g., finance, supply chain) and """ + experiment_prompt + """ 
Always output plain JSON without any markdown or formatting, only the raw JSON object. Please respond in English.
JSON SCHEMA: {"name": str, "phone": str, "email": str, "address": str, "links": list[str], "school": list[str], "gpa": list[str], "major": list[str], "degree": list[str], "graduation_time": str, "tech_skills": list[str], "business_domain": list[str], "experiences": list[str]}"""},
                {"role": "user", "content": """Resume
    """ + text},
            ],
            response_format=format,
            temperature=0.00,
            timeout=60.0,
        )
        return response.choices[0].message.content
    except Exception as e:
        # 获取详细的错误信息
        error_type = type(e).__name__
        error_msg = str(e)
        
        # 获取底层异常（如果有）
        underlying_error = None
        if hasattr(e, '__cause__') and e.__cause__:
            underlying_error = str(e.__cause__)
        elif hasattr(e, '__context__') and e.__context__:
            underlying_error = str(e.__context__)
        
        # 构建详细的错误信息
        detailed_error = f"错误类型: {error_type}\n错误信息: {error_msg}"
        if underlying_error:
            detailed_error += f"\n底层错误: {underlying_error}"
        
        # 检查是否是连接错误
        if "Connection" in error_type or "Connection" in error_msg:
            if underlying_error:
                if "timeout" in underlying_error.lower() or "timed out" in underlying_error.lower():
                    raise RuntimeError(f"API 连接超时。请检查网络连接或增加超时时间。\n\n{detailed_error}")
                elif "refused" in underlying_error.lower() or "拒绝" in underlying_error:
                    raise RuntimeError(f"API 服务器拒绝连接。可能是防火墙或代理问题。\n\n{detailed_error}")
                elif "resolve" in underlying_error.lower() or "DNS" in underlying_error:
                    raise RuntimeError(f"无法解析 API 服务器地址。请检查 DNS 设置。\n\n{detailed_error}")
                else:
                    raise RuntimeError(f"无法连接到 {model_name} API 服务器。\n\n{detailed_error}")
            else:
                raise RuntimeError(f"无法连接到 {model_name} API 服务器。请检查网络连接。\n\n{detailed_error}")
        elif "Insufficient" in error_msg or "quota" in error_msg.lower():
            raise RuntimeError(f"{model_name} API 账户余额不足或配额已用完。\n\n{detailed_error}")
        else:
            raise RuntimeError(f"API 调用失败: {detailed_error}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Resume Reader')
    parser.add_argument('--file_path', type=str, help='Path to the resume PDF file')
    parser.add_argument('--detailed_level', type=str, default='SENTENCE', 
                        help='Level of detail to extract from the resume',
                        choices=['DETAIL', 'SUMMARY', 'SENTENCE'], required=False)
    parser.add_argument('--output', type=str, help='Output file path', required=False)
    args = parser.parse_args()
    result = read_resume(args.file_path, detailed_level=ExperienceType[args.detailed_level])
    if 'error' in result:
        print(result['error'])
    elif args.output:
        with open(args.output, 'w') as file:
            json.dump(result, file)
        print("Resume data extracted successfully and saved to", args.output)
    else:
        print(json.dumps(result, indent=4))


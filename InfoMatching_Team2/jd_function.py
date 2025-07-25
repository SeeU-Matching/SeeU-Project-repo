import json

import pandas as pd
from openai import OpenAI
import os
key_file_path = os.path.join(os.path.dirname(__file__), 'key.txt')
with open(key_file_path, 'r') as file:
    key = file.read()
client = OpenAI(api_key=key)

def extract_job_data(jd):
    result = []
    prompt = """extract detailed information from job description, including only the following fields: Company Industry Field(Search it), Major, Tech skills, graduation time(return not specified if not mentioned), minimum academic qualification and Experience domain. 
                Always output plain JSON without any markdown or formatting. \n
                Job description is:""" + jd
    try:
        # Call the LLM
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        result = response.choices[0].message.content
        result = json.loads(result)
    except Exception as e:
        result.append({"error": f"Failed to process JD: {e}"})
    return result

# file_path = './CS.xlsx'
# df = pd.read_excel(file_path)
# jd1 = df['岗位要求'][20]
# result = extract_job_data(jd1)
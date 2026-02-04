
import re

def test_regex():
    urls = [
        "https://www.linkedin.com/jobs/view/3990818259",
        "https://www.linkedin.com/jobs/view/marketing-manager-2026-program-12345678",
        "https://www.linkedin.com/jobs/view/software-engineer-2-987654321",
        "https://www.linkedin.com/jobs/view/lead-dev-1-2-3-456789",
        "https://www.linkedin.com/jobs/view/no-numbers-here",
    ]

    # This is the regex we put into the Code
    regex = r"(\d+)/?$"
    
    print(f"Testing regex: {regex}")
    for url in urls:
        clean_url = url.split("?")[0]
        match = re.search(regex, clean_url)
        job_id = match.group(1) if match else "NO_MATCH"
        print(f"URL: {clean_url} -> ID: {job_id}")

    print("-" * 20)
    print("Verification:")
    expected = {
        "3990818259": "3990818259",
        "marketing-manager-2026-program-12345678": "12345678",
        "software-engineer-2-987654321": "987654321",
        "lead-dev-1-2-3-456789": "456789",
        "no-numbers-here": "NO_MATCH"
    }
    
    for url in urls:
        clean_url = url.split("?")[0]
        match = re.search(regex, clean_url)
        got = match.group(1) if match else "NO_MATCH"
        
        path_part = clean_url.split("/")[-1]
        exp = expected.get(path_part)
        
        status = "PASS" if got == exp else "FAIL"
        print(f"[{status}] {path_part}: expected {exp}, got {got}")

if __name__ == "__main__":
    test_regex()

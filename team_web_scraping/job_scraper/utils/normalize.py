import re

# These are safe to strip anywhere (unambiguous legal suffixes)
_MID_SUFFIXES = r'\b(llc|corp|ltd|plc|pllc|inc|dba)\b\.?'

# These are risky — only strip at the end of the string
_END_SUFFIXES = r'\b(lp|lc|co|pc|na|the|and|&)\b\.?$'

def normalize_company_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = name.lower().strip()
    name = re.sub(_MID_SUFFIXES, '', name)   # safe to remove anywhere
    name = re.sub(_END_SUFFIXES, '', name)   # only remove at end
    name = re.sub(r'[^a-z0-9 ]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()

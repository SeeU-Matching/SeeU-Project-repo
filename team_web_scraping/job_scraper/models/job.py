from typing import Optional
from pydantic import BaseModel, Field


class JobSearchRequest(BaseModel):
    job_title: str = Field(...)
    location: str   = Field(...)
    pages: int = Field(1, ge=1, le=5, example=2,
                       description="How many result pages")
    use_selenium: bool = Field(False, description="If true, call external Selenium detail service")

class JobResult(BaseModel):
    title: str
    company: str
    location: str
    description: str
    job_url: str
    apply_url: str
    industry: Optional[str]

class JobDetail(BaseModel):
    description: str = ""
    apply_url: str = ""
    industry: Optional[str] = None
    title: str = ""
    company: str = ""

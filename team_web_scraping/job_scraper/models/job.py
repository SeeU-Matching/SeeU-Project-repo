from typing import Optional
from pydantic import BaseModel, Field


class JobSearchRequest(BaseModel):
    job_title: str = Field(...)
    location: str   = Field(...)
    pages: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        example=2,
        description="How many result pages. If None, fetches all available pages (max 5)."
    )
    use_selenium: bool = Field(False, description="If true, call external Selenium detail service")

class JobResult(BaseModel):
    title: str
    company: str
    location: str
    description: str
    job_url: str
    apply_url: str
    industry: Optional[str]
    search_title: Optional[str] = None
    search_location: Optional[str] = None
    experience_level: Optional[str] = None

class JobDetail(BaseModel):
    description: str = ""
    apply_url: str = ""
    industry: Optional[str] = None
    title: str = ""
    company: str = ""

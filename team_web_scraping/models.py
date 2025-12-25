from pydantic import BaseModel, Field
from typing import Optional, List

class JobSearchRequest(BaseModel):
    job_title: str = Field(...)
    location: str   = Field(...)
    pages: int = Field(1, ge=1, le=5, example=2,
                       description="How many result pages")

class JobResult(BaseModel):
    title: str
    company: str
    location: str
    description: str
    apply_url: str
    industry: Optional[str]

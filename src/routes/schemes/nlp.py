from pydantic import BaseModel
from typing import Optional
from controllers import NLPController
class PushRequest(BaseModel):
    do_reset:Optional[int]=0
class searchRequest(BaseModel):
    text:str
    limit:Optional[int]=5
class TranslationRequest(BaseModel):
    page_number: Optional[int] = 1
    page_size: Optional[int] = 10
    target_language: Optional[str] = "Arabic"
    source_language: Optional[str] = None
    temperature: Optional[float] = 0.5
    max_retries: Optional[int] = 3
    retry_delay_seconds: Optional[float] = 5.0

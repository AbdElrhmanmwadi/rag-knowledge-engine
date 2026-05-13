from typing import Optional

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    format: Optional[str] = Field(default="wav", description="Currently only 'wav' is supported")


class VoiceChatRequest(BaseModel):
    limit: int = Field(default=30, ge=1, le=200)
    return_audio_base64: bool = True

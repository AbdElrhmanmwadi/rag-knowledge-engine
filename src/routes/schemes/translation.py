from typing import Optional

from pydantic import BaseModel, field_validator


class TranslationFileRequest(BaseModel):
    project_id: int
    file_id: str
    source_lang: Optional[str] = "auto"
    target_lang: Optional[str] = None

    @field_validator("source_lang", "target_lang")
    @classmethod
    def validate_language_value(cls, value: Optional[str]):
        if value is None:
            return value

        normalized = str(value).strip().lower()
        if normalized in {"string", "null", "none", "undefined"}:
            raise ValueError("Language must be a valid code like 'en' or 'ar'")

        return value

from typing import Optional

from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    question: str
    answer: str
    rating: int                 # 1 = 👍 helpful, -1 = 👎 not helpful
    session_id: Optional[int] = None
    comment: Optional[str] = None

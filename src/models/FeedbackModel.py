from sqlalchemy import case, func, select

from models.db_schemes.minirag.scheme.feedback import AnswerFeedback

from .BaseDataModle import BaseDataModel


class FeedbackModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client):
        return cls(db_client)

    async def add_feedback(
        self,
        project_id: int,
        user_id: int,
        question: str,
        answer: str,
        rating: int,
        session_id: int | None = None,
        comment: str | None = None,
    ) -> AnswerFeedback:
        async with self.db_client() as session:
            feedback = AnswerFeedback(
                project_id=project_id,
                user_id=user_id,
                session_id=session_id,
                question=question,
                answer=answer,
                rating=rating,
                comment=comment,
            )
            session.add(feedback)
            await session.commit()
            await session.refresh(feedback)
            return feedback

    async def get_analytics(self, project_id: int, top_n: int = 10) -> dict:
        """Aggregate ratings for a project: totals, CSAT, and top disliked questions."""
        async with self.db_client() as session:
            totals = await session.execute(
                select(
                    func.count().label("total"),
                    func.coalesce(func.sum(case((AnswerFeedback.rating == 1, 1), else_=0)), 0).label("positive"),
                    func.coalesce(func.sum(case((AnswerFeedback.rating == -1, 1), else_=0)), 0).label("negative"),
                ).where(AnswerFeedback.project_id == project_id)
            )
            row = totals.one()
            total = int(row.total or 0)
            positive = int(row.positive or 0)
            negative = int(row.negative or 0)
            # CSAT = share of positive ratings; None when there is no feedback yet.
            csat = round(positive / total, 3) if total else None

            top_negative = await session.execute(
                select(AnswerFeedback.question, func.count().label("count"))
                .where(AnswerFeedback.project_id == project_id, AnswerFeedback.rating == -1)
                .group_by(AnswerFeedback.question)
                .order_by(func.count().desc())
                .limit(top_n)
            )
            top_disliked = [{"question": q, "count": int(c)} for q, c in top_negative.all()]

            return {
                "total": total,
                "positive": positive,
                "negative": negative,
                "csat": csat,
                "top_disliked_questions": top_disliked,
            }

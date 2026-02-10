"""
Database service for managing sessions, records, and user data.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session as DBSession
from app.models.database import (
    get_db_session,
    User, Session, StepRecord, Mistake, GeneratedQuestion
)
from app.models.schemas import SessionState


class DatabaseService:
    """Handle all database operations for the dialogue manager."""
    
    def get_or_create_user(self, username: str = "anonymous") -> User:
        """Get or create a user by username."""
        db = get_db_session()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(username=username)
                db.add(user)
                db.commit()
                db.refresh(user)
            return user
        finally:
            db.close()
    
    def create_session(self, session_state: SessionState, user_id: Optional[int] = None) -> Session:
        """Create a new session in the database."""
        db = get_db_session()
        try:
            db_session = Session(
                id=session_state.session_id,
                user_id=user_id,
                question_id=session_state.question_id,
                status=session_state.status,
                current_step_id=session_state.current_step_id,
                correct_count=session_state.correct_count,
                retry_count=session_state.retry_count
            )
            db.add(db_session)
            db.commit()
            return db_session
        finally:
            db.close()
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session from the database."""
        db = get_db_session()
        try:
            return db.query(Session).filter(Session.id == session_id).first()
        finally:
            db.close()
    
    def update_session(self, session_state: SessionState) -> None:
        """Update an existing session in the database."""
        db = get_db_session()
        try:
            db_session = db.query(Session).filter(Session.id == session_state.session_id).first()
            if db_session:
                db_session.status = session_state.status
                db_session.current_step_id = session_state.current_step_id
                db_session.correct_count = session_state.correct_count
                db_session.retry_count = session_state.retry_count
                if session_state.status == "completed":
                    db_session.completed_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    
    def create_step_record(
        self,
        session_id: str,
        step_id: int,
        student_choice: str,
        is_correct: bool,
        response_time_ms: int
    ) -> StepRecord:
        """Create a step record in the database."""
        db = get_db_session()
        try:
            record = StepRecord(
                session_id=session_id,
                step_id=step_id,
                student_choice=student_choice,
                is_correct=is_correct,
                response_time_ms=response_time_ms
            )
            db.add(record)
            db.commit()
            return record
        finally:
            db.close()
    
    def create_mistake(
        self,
        user_id: Optional[int],
        question_id: str,
        step_id: int,
        wrong_choice: str,
        correct_choice: str
    ) -> Mistake:
        """Add a mistake to the mistake book."""
        db = get_db_session()
        try:
            mistake = Mistake(
                user_id=user_id,
                question_id=question_id,
                step_id=step_id,
                wrong_choice=wrong_choice,
                correct_choice=correct_choice
            )
            db.add(mistake)
            db.commit()
            return mistake
        finally:
            db.close()
    
    def get_user_mistakes(self, user_id: int) -> List[Mistake]:
        """Get all mistakes for a user."""
        db = get_db_session()
        try:
            return db.query(Mistake).filter(Mistake.user_id == user_id).all()
        finally:
            db.close()
    
    def save_generated_question(self, question_id: str, source_question_id: str, content: str) -> GeneratedQuestion:
        """Save an AI-generated question to the database."""
        db = get_db_session()
        try:
            gen_question = GeneratedQuestion(
                id=question_id,
                source_question_id=source_question_id,
                content=content
            )
            db.add(gen_question)
            db.commit()
            return gen_question
        finally:
            db.close()
    
    def get_generated_question(self, question_id: str) -> Optional[GeneratedQuestion]:
        """Get a generated question from the database."""
        db = get_db_session()
        try:
            return db.query(GeneratedQuestion).filter(GeneratedQuestion.id == question_id).first()
        finally:
            db.close()


# Global database service instance
db_service = DatabaseService()

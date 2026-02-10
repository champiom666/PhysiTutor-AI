"""
PhysiTutor-AI Dialogue Manager
Controls the step-by-step guided dialogue flow.
"""
import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.models.schemas import (
    SessionState,
    Question,
    QuestionStep,
    CurrentStepResponse,
    FeedbackResponse,
    DialogueLog,
    SessionSummary,
    ReasoningSubmit,
    ReasoningFeedbackResponse,
)
from app.services.logger import dialogue_logger
from app.services.llm_service import llm_service
from app.services.db_service import db_service
from config.settings import settings


class DialogueManager:
    """
    Manages the step-by-step dialogue flow for physics tutoring.
    
    Key responsibilities:
    1. Maintain session state
    2. Load and serve question steps
    3. Validate student choices
    4. Enforce "must choose" rule
    5. Track progress and trigger transfer mode
    """
    
    def __init__(self):
        """Initialize the dialogue manager."""
        self.sessions: Dict[str, SessionState] = {}
        self.questions: Dict[str, Question] = {}
        self._load_questions()
    
    def _load_questions(self) -> None:
        """Load all questions from the data directory."""
        questions_dir = settings.questions_dir
        
        # Also check practice directory for existing questions
        practice_dir = Path(settings.PROJECT_ROOT) / "practice"
        
        for directory in [questions_dir, practice_dir]:
            if not directory.exists():
                continue
            
            for file_path in directory.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        question = Question(**data)
                        self.questions[question.id] = question
                except Exception as e:
                    print(f"Error loading question from {file_path}: {e}")
    
    def get_available_questions(self) -> list:
        """Get list of available question IDs."""
        return list(self.questions.keys())
    
    def get_available_questions_with_info(self) -> list:
        """Get list of available questions with detailed information."""
        result = []
        # Sort by question ID to ensure consistent ordering
        for question_id in sorted(self.questions.keys()):
            question = self.questions[question_id]
            result.append({
                "id": question.id,
                "topic": question.topic,
                "difficulty": question.difficulty
            })
        return result

    def register_question(self, question: Question) -> None:
        """注册一道题目到内存（如 AI 生成的类似题）。"""
        self.questions[question.id] = question

    def create_session(
        self,
        question_id: str,
        student_id: Optional[str] = None
    ) -> SessionState:
        """
        Create a new tutoring session.
        
        Args:
            question_id: ID of the question to use
            student_id: Optional student identifier
            
        Returns:
            The created session state
            
        Raises:
            ValueError: If question_id is not found
        """
        if question_id not in self.questions:
            raise ValueError(f"Question '{question_id}' not found")
        
        question = self.questions[question_id]
        
        session = SessionState(
            question_id=question_id,
            student_id=student_id,
            total_steps=len(question.guided_steps)
        )
        
        # Save to both memory and database
        self.sessions[session.session_id] = session
        
        # Persist to database  # Get or create anonymous user if needed
        user = None
        if student_id:
            user = db_service.get_or_create_user(student_id)
        db_service.create_session(session, user.id if user else None)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def get_current_step(self, session_id: str) -> CurrentStepResponse:
        """
        Get the current step for a session.
        
        This implements the "must choose" rule - students cannot skip steps.
        
        Args:
            session_id: The session ID
            
        Returns:
            The current step information
            
        Raises:
            ValueError: If session not found or already completed
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found")
        
        if session.status == "completed":
            raise ValueError("Session already completed")
        
        question = self.questions[session.question_id]
        
        # Find current step
        current_step = None
        for step in question.guided_steps:
            if step.step_id == session.current_step_id:
                current_step = step
                break
        
        if not current_step:
            raise ValueError(f"Step {session.current_step_id} not found")
        
        # Always include context and image so frontend can display it
        context = question.question_context.description
        image = question.image
        
        # Original logic was:
        # if session.current_step_id == 1:
        #     context = question.question_context.description
        #     image = question.image
        
        return CurrentStepResponse(
            session_id=session_id,
            question_id=session.question_id,
            step_id=current_step.step_id,
            step_type=current_step.type,
            prompt=current_step.prompt,
            options=current_step.options,
            image=image,
            context=context,
            total_steps=session.total_steps,
            is_transfer_mode=session.status == "transfer_mode",
            is_reasoning_mode=session.status == "reasoning"
        )
    
    def submit_choice(
        self,
        session_id: str,
        choice: str
    ) -> FeedbackResponse:
        """
        Process a student's choice submission.
        
        Args:
            session_id: The session ID
            choice: The student's choice (e.g., 'A', 'B', 'C', 'D')
            
        Returns:
            Feedback response with correctness and guidance
            
        Raises:
            ValueError: If session not found or invalid choice
        """
        start_time = time.time()
        
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found")
        
        if session.status == "completed":
            raise ValueError("Session already completed")
        
        question = self.questions[session.question_id]
        
        # Find current step
        current_step = None
        for step in question.guided_steps:
            if step.step_id == session.current_step_id:
                current_step = step
                break
        
        if not current_step:
            raise ValueError(f"Step {session.current_step_id} not found")
        
        # Validate choice format
        choice = choice.upper().strip()
        valid_choices = [opt[0] for opt in current_step.options]  # Extract A, B, C, D
        if choice not in valid_choices:
            raise ValueError(f"Invalid choice '{choice}'. Must be one of {valid_choices}")
        
        # Check correctness
        is_correct = choice == current_step.correct
        
        # Get appropriate feedback
        if is_correct:
            feedback = current_step.feedback.correct
            session.correct_count += 1
        else:
            feedback = current_step.feedback.incorrect
            session.retry_count += 1
        
        # Optionally enhance feedback with AI (for MVP, mostly use predefined)
        ai_feedback = None
        if not is_correct and session.retry_count >= 2:
            # Use AI for additional guidance after multiple retries
            ai_feedback = llm_service.generate_feedback(
                step_prompt=current_step.prompt,
                student_choice=choice,
                is_correct=is_correct,
                base_feedback=feedback
            )
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Save step record to database
        db_service.create_step_record(
            session_id=session_id,
            step_id=session.current_step_id,
            student_choice=choice,
            is_correct=is_correct,
            response_time_ms=response_time_ms
        )
        
        # If incorrect, add to mistake book
        if not is_correct:
            # Get user_id from session if available
            db_session = db_service.get_session(session_id)
            if db_session and db_session.user_id:
                db_service.create_mistake(
                    user_id=db_session.user_id,
                    question_id=session.question_id,
                    step_id=session.current_step_id,
                    wrong_choice=choice,
                    correct_choice=current_step.correct
                )
        
        # Log the interaction
        log_entry = DialogueLog(
            session_id=session_id,
            question_id=session.question_id,
            step_id=session.current_step_id,
            granularity=current_step.type,
            student_choice=choice,
            expected_choice=current_step.correct,
            ai_feedback=ai_feedback or feedback,
            is_correct=is_correct,
            prompt_version=settings.prompt_version,
            response_time_ms=response_time_ms,
            retry_attempt=session.retry_count if not is_correct else 0
        )
        dialogue_logger.log_interaction(log_entry)
        
        # Determine next state
        next_step_available = False
        is_completed = False
        enter_transfer_mode = False
        
        if is_correct:
            # Move to next step
            if session.current_step_id < session.total_steps:
                session.current_step_id += 1
                session.retry_count = 0
                next_step_available = True
            else:
                # All steps completed -> Enter Reasoning Mode
                session.status = "reasoning"
                # We don't log summary yet, wait until reasoning/transfer is done
        
        # Update session in database
        db_service.update_session(session)
        
        return FeedbackResponse(
            session_id=session_id,
            step_id=current_step.step_id,
            is_correct=is_correct,
            feedback=feedback,
            ai_enhanced_feedback=ai_feedback,
            next_step_available=next_step_available,
            is_completed=is_completed,
            enter_transfer_mode=enter_transfer_mode,
            enter_reasoning_mode=session.status == "reasoning"
        )
    
    def _log_session_summary(self, session: SessionState) -> None:
        """Log session summary when completed."""
        accuracy = session.correct_count / session.total_steps if session.total_steps > 0 else 0
        
        summary = SessionSummary(
            session_id=session.session_id,
            question_id=session.question_id,
            total_steps=session.total_steps,
            correct_count=session.correct_count,
            accuracy=accuracy,
            total_retries=session.retry_count
        )
        dialogue_logger.log_session_summary(summary)
    
    def start_transfer_question(self, session_id: str) -> Optional[str]:
        """
        Start the transfer question for a session in transfer mode.
        
        Args:
            session_id: The session ID
            
        Returns:
            The transfer question ID if available
        """
        session = self.sessions.get(session_id)
        if not session or session.status != "transfer_mode":
            return None
        
        question = self.questions[session.question_id]
        next_question_id = question.next_similar_question_id
        
        if next_question_id and next_question_id in self.questions:
            # Create new session for transfer question
            # (In a full implementation, this would link to the original session)
            return next_question_id
        
        return None

    def start_transfer_question_with_ai(self, session_id: str) -> Optional[str]:
        """
        用 Gemini 根据原题图片和题目信息生成一道思路类似的新题，并创建新会话。
        要求会话处于 transfer_mode 或 completed。
        
        Returns:
            新题目的 question_id，失败返回 None。
        """
        session = self.sessions.get(session_id)
        if not session or session.status not in ("transfer_mode", "completed"):
            return None

        question = self.questions.get(session.question_id)
        if not question:
            return None

        image_base64 = ""
        mime_type = "image/png"
        if question.image:
            image_path = Path(settings.PROJECT_ROOT) / question.image.lstrip("/")
            if image_path.exists():
                try:
                    with open(image_path, "rb") as f:
                        image_base64 = base64.b64encode(f.read()).decode()
                    mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
                except Exception as e:
                    print(f"Error reading question image: {e}")

        data = llm_service.generate_similar_question(
            question=question,
            image_base64=image_base64,
            mime_type=mime_type,
        )
        if not data:
            return None

        new_id = f"transfer_{session_id}"
        data["id"] = new_id
        new_question = Question(**data)
        self.register_question(new_question)
        # 不在此处 create_session，由前端 startSession(next_question_id) 时创建
        return new_id

    def submit_reasoning(
        self,
        session_id: str,
        reasoning: ReasoningSubmit
    ) -> ReasoningFeedbackResponse:
        """
        Process student's reasoning submission.
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found")
        
        question = self.questions[session.question_id]
        
        # Call LLM
        result = llm_service.analyze_reasoning(
            question=question,
            student_reasoning=reasoning.text,
            student_image=reasoning.image
        )
        
        # Determine next state
        is_transfer_ready = True
        if session.status == "reasoning":
            if question.next_similar_question_id:
                session.status = "transfer_mode"
            else:
                session.status = "completed"
                self._log_session_summary(session)
        
        # Update session in database
        db_service.update_session(session)
             
        return ReasoningFeedbackResponse(
            session_id=session_id,
            ai_evaluation=result.get("evaluation", ""),
            standard_solution=result.get("standard_solution", ""),
            is_transfer_ready=is_transfer_ready
        )

    def end_session(self, session_id: str) -> Optional[SessionState]:
        """
        End a session and clean up.
        
        Args:
            session_id: The session ID
            
        Returns:
            The final session state
        """
        session = self.sessions.get(session_id)
        if session:
            if session.status == "active":
                session.status = "completed"
                self._log_session_summary(session)
            
            # Update final state in database
            db_service.update_session(session)
            
            del self.sessions[session_id]
        return session
    
    def get_session_history(self, session_id: str) -> list:
        """Get all dialogue logs for a session."""
        return dialogue_logger.get_session_logs(session_id)


# Global dialogue manager instance
dialogue_manager = DialogueManager()
# Reload data

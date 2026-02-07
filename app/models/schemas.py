"""
PhysiTutor-AI Data Models (Pydantic Schemas)
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
import uuid


# ============ Session Models ============

class SessionCreate(BaseModel):
    """Request model for creating a new session."""
    question_id: str = Field(..., description="ID of the question to start with")
    student_id: Optional[str] = Field(default=None, description="Optional student identifier")


class SessionResponse(BaseModel):
    """Response model for session information."""
    session_id: str
    question_id: str
    current_step_id: int
    status: Literal["active", "reasoning", "completed", "transfer_mode"]
    created_at: datetime
    

class SessionState(BaseModel):
    """Internal session state model."""
    session_id: str = Field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:8]}")
    question_id: str
    current_step_id: int = 1
    # Status reasoning means waiting for student reasoning or handling reasoning interaction
    status: Literal["active", "reasoning", "completed", "transfer_mode"] = "active"
    created_at: datetime = Field(default_factory=datetime.now)
    student_id: Optional[str] = None
    retry_count: int = 0  # Track retries for current step
    correct_count: int = 0  # Track correct answers
    total_steps: int = 0


# ============ Question Models ============

class FeedbackConfig(BaseModel):
    """Feedback configuration for a step."""
    correct: str
    incorrect: str


class QuestionStep(BaseModel):
    """A single guided step in a question."""
    step_id: int
    type: str  # e.g., "concept_judgement", "direction_judgement"
    prompt: str
    options: List[str]
    correct: str
    feedback: FeedbackConfig
    
class QuestionContext(BaseModel):
    """Context information for a question."""
    description: str
    ask: List[str]


class Question(BaseModel):
    """Full question model."""
    id: str
    topic: str
    difficulty: str
    image: Optional[str] = None
    question_context: QuestionContext
    guided_steps: List[QuestionStep]
    next_similar_question_id: Optional[str] = None


# ============ Dialogue Models ============

class CurrentStepResponse(BaseModel):
    """Response for current step endpoint."""
    session_id: str
    question_id: str
    step_id: int
    step_type: str
    prompt: str
    options: List[str]
    image: Optional[str] = None
    context: Optional[str] = None  # Question context
    is_transfer_mode: bool = False
    is_reasoning_mode: bool = False  # New flag for reasoning phase


class ChoiceSubmit(BaseModel):
    """Request model for submitting a choice."""
    choice: str = Field(..., description="Student's choice (e.g., 'A', 'B', 'C', 'D')")


class FeedbackResponse(BaseModel):
    """Response after submitting a choice."""
    session_id: str
    step_id: int
    is_correct: bool
    feedback: str
    next_step_available: bool
    ai_enhanced_feedback: Optional[str] = None  # AI-generated additional guidance
    is_completed: bool = False
    enter_transfer_mode: bool = False
    enter_reasoning_mode: bool = False  # New flag for reasoning phase


class ReasoningSubmit(BaseModel):
    """Request model for submitting student reasoning."""
    text: str = Field(..., description="Student's reasoning or thoughts")
    image: Optional[str] = Field(None, description="Optional base64 image or URL")


class ReasoningFeedbackResponse(BaseModel):
    """Response after submitting reasoning."""
    session_id: str
    ai_evaluation: str
    standard_solution: str
    is_transfer_ready: bool = True  # Default to allowing transfer


# ============ Logging Models ============

class DialogueLog(BaseModel):
    """Log entry for each dialogue interaction."""
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: str
    question_id: str
    step_id: int
    granularity: str  # Step type (e.g., "concept_judgement")
    student_choice: str
    expected_choice: str
    ai_feedback: str
    is_correct: bool
    prompt_version: str
    response_time_ms: Optional[int] = None
    retry_attempt: int = 0


class SessionSummary(BaseModel):
    """Summary of a completed session."""
    session_id: str
    question_id: str
    total_steps: int
    correct_count: int
    accuracy: float
    total_retries: int
    duration_seconds: Optional[float] = None
    completed_at: datetime = Field(default_factory=datetime.now)

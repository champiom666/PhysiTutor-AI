"""
PhysiTutor-AI Dialogue Routes
Handles the step-by-step guided dialogue interactions.
"""
from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    CurrentStepResponse,
    ChoiceSubmit,
    FeedbackResponse,
    ReasoningSubmit,
    ReasoningFeedbackResponse
)
from app.services.dialogue_manager import dialogue_manager

router = APIRouter(prefix="/dialogue", tags=["Dialogue"])


@router.get("/{session_id}/current", response_model=CurrentStepResponse)
async def get_current_step(session_id: str):
    """
    Get the current step for a session.
    
    This endpoint returns the current step's prompt and options.
    The student MUST respond with a choice before the next step is revealed.
    
    - **session_id**: The session ID
    
    Returns:
    - **prompt**: The question/judgment for this step
    - **options**: Available choices (A, B, C, D, etc.)
    - **context**: Question context (only provided for first step)
    """
    try:
        return dialogue_manager.get_current_step(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{session_id}/submit", response_model=FeedbackResponse)
async def submit_choice(session_id: str, request: ChoiceSubmit):
    """
    Submit a choice for the current step.
    
    The student must submit a valid choice (e.g., 'A', 'B', 'C', 'D').
    The AI will provide feedback on whether the judgment is correct.
    
    - **session_id**: The session ID
    - **choice**: The student's choice (e.g., 'A')
    
    Returns:
    - **is_correct**: Whether the choice was correct
    - **feedback**: Guidance based on the choice
    - **next_step_available**: Whether there's a next step
    - **is_completed**: Whether all steps are completed
    - **enter_transfer_mode**: Whether entering transfer verification mode
    """
    try:
        return dialogue_manager.submit_choice(session_id, request.choice)
    except ValueError as e:
        # Determine appropriate status code
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        elif "invalid choice" in error_msg.lower():
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)


@router.get("/{session_id}/history")
async def get_dialogue_history(session_id: str):
    """
    Get the complete dialogue history for a session.
    
    - **session_id**: The session ID
    
    Returns all interactions (steps, choices, and feedback) for analysis.
    """
    session = dialogue_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    logs = dialogue_manager.get_session_history(session_id)
    
    return {
        "session_id": session_id,
        "question_id": session.question_id,
        "current_step": session.current_step_id,
        "status": session.status,
        "history": [
            {
                "step_id": log.step_id,
                "choice": log.student_choice,
                "expected": log.expected_choice,
                "is_correct": log.is_correct,
                "feedback": log.ai_feedback,
                "timestamp": log.timestamp.isoformat()
            }
            for log in logs
        ]
    }


@router.post("/{session_id}/transfer")
async def start_transfer(session_id: str):
    """
    Start the transfer verification question.
    
    After completing all guided steps, the student can move to a
    similar question with reduced guidance to verify learning.
    
    - **session_id**: The session ID (must be in transfer_mode)
    
    Returns the ID of the transfer question if available.
    """
    next_question = dialogue_manager.start_transfer_question(session_id)
    
    if not next_question:
        raise HTTPException(
            status_code=400,
            detail="Transfer question not available. Session must be in transfer_mode."
        )
    
    return {
        "message": "Transfer question ready",
        "next_question_id": next_question,
        "hint": f"Start new session with question_id='{next_question}' for transfer verification"
    }


@router.post("/{session_id}/reasoning", response_model=ReasoningFeedbackResponse)
async def submit_reasoning(session_id: str, request: ReasoningSubmit):
    """
    Submit student's reasoning for evaluation.
    
    After completing guided steps, the student explains their thought process.
    The AI evaluates this reasoning and provides a standard solution.
    
    - **session_id**: The session ID
    - **text**: Student's reasoning
    
    Returns AI evaluation and standard solution.
    """
    try:
        return dialogue_manager.submit_reasoning(session_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

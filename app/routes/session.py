"""
PhysiTutor-AI Session Routes
Handles session lifecycle management.
"""
from fastapi import APIRouter, HTTPException

from app.models.schemas import SessionCreate, SessionResponse
from app.services.dialogue_manager import dialogue_manager

router = APIRouter(prefix="/session", tags=["Session"])


@router.post("/start", response_model=SessionResponse)
async def start_session(request: SessionCreate):
    """
    Start a new tutoring session.
    
    - **question_id**: ID of the question to start with (required)
    - **student_id**: Optional student identifier for tracking
    
    Returns the created session information including session_id.
    """
    try:
        session = dialogue_manager.create_session(
            question_id=request.question_id,
            student_id=request.student_id
        )
        
        return SessionResponse(
            session_id=session.session_id,
            question_id=session.question_id,
            current_step_id=session.current_step_id,
            status=session.status,
            created_at=session.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """
    Get the current state of a session.
    
    - **session_id**: The session ID to query
    """
    session = dialogue_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    return SessionResponse(
        session_id=session.session_id,
        question_id=session.question_id,
        current_step_id=session.current_step_id,
        status=session.status,
        created_at=session.created_at
    )


@router.post("/{session_id}/end")
async def end_session(session_id: str):
    """
    End a session and clean up resources.
    
    - **session_id**: The session ID to end
    
    Returns summary of the session.
    """
    session = dialogue_manager.end_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    
    accuracy = session.correct_count / session.total_steps if session.total_steps > 0 else 0
    
    return {
        "message": "Session ended",
        "session_id": session.session_id,
        "total_steps": session.total_steps,
        "correct_count": session.correct_count,
        "accuracy": f"{accuracy:.1%}"
    }


@router.get("/")
async def list_questions():
    """
    List all available questions.
    
    Returns a list of questions with detailed information (id, topic, difficulty).
    """
    questions = dialogue_manager.get_available_questions_with_info()
    return {
        "available_questions": questions,
        "count": len(questions)
    }

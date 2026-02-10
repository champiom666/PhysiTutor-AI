"""
PhysiTutor-AI Session Routes
Handles session lifecycle management.
"""
from fastapi import APIRouter, HTTPException

from app.models.schemas import SessionCreate, SessionResponse
from app.models.schemas import SessionCreate, SessionResponse
from app.services.dialogue_manager import dialogue_manager
import shutil
import uuid
import os
import base64
import json
from pathlib import Path
from fastapi import UploadFile, File
from app.services.llm_service import llm_service
from app.services.db_service import db_service
from app.models.schemas import Question
from config.settings import settings

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


@router.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    """
    Receive an image, analyze it using AI, and generate a new Question.
    Returns the new question_id.
    """
    # Ensure upload directory exists
    upload_dir = settings.PROJECT_ROOT / "static" / "uploads"
    if not upload_dir.exists():
        upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_ext = Path(file.filename).suffix
    if not file_ext:
        file_ext = ".png"
    unique_filename = f"upload_{uuid.uuid4().hex}{file_ext}"
    file_path = upload_dir / unique_filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # Read file for AI analysis
    try:
        with open(file_path, "rb") as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode("utf-8")
            
        mime_type = "image/png"
        if file_ext.lower() in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
            
        # Call LLM service
        question_data = llm_service.analyze_physics_image(image_base64, mime_type)
        
        if not question_data:
            raise HTTPException(status_code=400, detail="Failed to analyze image. Please try again with a clearer image.")
            
        # Assign ID and Image Path
        new_id = f"photo_{uuid.uuid4().hex[:8]}"
        # Ensure ID is unique
        if new_id in dialogue_manager.questions:
             new_id = f"photo_{uuid.uuid4().hex[:8]}"

        question_data["id"] = new_id
        # Frontend path (relative to static mount)
        question_data["image"] = f"static/uploads/{unique_filename}"
        
        # Create Question object
        # Ensure all required fields are present
        if "topic" not in question_data:
            question_data["topic"] = "Photo Question"
        if "difficulty" not in question_data:
            question_data["difficulty"] = "Unknown"
            
        question = Question(**question_data)
        
        # Register to Memory
        dialogue_manager.register_question(question)
        
        # Persist to Database
        json_content = json.dumps(question_data, ensure_ascii=False)
        db_service.save_generated_question(
            question_id=new_id,
            source_question_id="user_upload",
            content=json_content
        )
        
        return {"question_id": new_id}

    except Exception as e:
        print(f"Error processing image upload: {e}")
        # If file was saved but processing failed, maybe delete it?
        # But keeping it might be good for debugging.
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

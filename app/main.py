"""
PhysiTutor-AI - AI-native Physics Tutoring MVP
FastAPI Application Entry Point
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from app.routes import session_router, dialogue_router
from app.services.logger import dialogue_logger
from config.settings import settings

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Create FastAPI app
app = FastAPI(
    title="PhysiTutor-AI",
    description="""
    AI-native 引导型物理导师 MVP
    
    验证假设：通过 API + Prompt，将大模型设定为「引导型物理导师」，
    能否有效提升初中生的物理解题思路。
    
    核心机制：
    - 把物理题拆成若干关键判断步骤
    - 每一步强制学生做选择
    - AI 只对"判断是否合理"做反馈
    - 逐步引导学生形成解题路径
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for frontend testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For MVP testing, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = PROJECT_ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Register routers
app.include_router(session_router)
app.include_router(dialogue_router)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """避免浏览器请求 /favicon.ico 时返回 404。"""
    favicon_path = PROJECT_ROOT / "static" / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/x-icon")
    return Response(status_code=204)


@app.get("/robots.txt", include_in_schema=False)
async def robots():
    """避免爬虫/浏览器请求 /robots.txt 时返回 404。"""
    robots_path = PROJECT_ROOT / "static" / "robots.txt"
    if robots_path.exists():
        return FileResponse(robots_path, media_type="text/plain")
    return Response(status_code=204)


@app.get("/")
async def root():
    """Serve the student-friendly frontend."""
    index_file = PROJECT_ROOT / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "name": "PhysiTutor-AI",
        "version": "0.1.0",
        "description": "AI-native 引导型物理导师 MVP",
        "frontend": "访问 /static/index.html 使用学生界面",
        "docs": "/docs"
    }


@app.get("/api")
async def api_info():
    """API information endpoint."""
    return {
        "name": "PhysiTutor-AI API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "session": {
                "list_questions": "GET /session/",
                "start": "POST /session/start",
                "get": "GET /session/{session_id}",
                "end": "POST /session/{session_id}/end"
            },
            "dialogue": {
                "current_step": "GET /dialogue/{session_id}/current",
                "submit_choice": "POST /dialogue/{session_id}/submit",
                "history": "GET /dialogue/{session_id}/history",
                "transfer": "POST /dialogue/{session_id}/transfer"
            }
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "env": settings.app_env,
        "gemini_configured": bool(settings.gemini_api_key),
        "prompt_version": settings.prompt_version
    }


@app.get("/logs/recent")
async def get_recent_logs(limit: int = 20):
    """
    Get recent dialogue logs for debugging.
    
    - **limit**: Maximum number of logs to return (default: 20)
    """
    logs = dialogue_logger.get_recent_logs(limit=limit)
    return {
        "count": len(logs),
        "logs": logs
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    from app.models.database import init_db
    
    print("=" * 50)
    print("PhysiTutor-AI MVP Starting...")
    print(f"Environment: {settings.app_env}")
    print(f"Prompt Version: {settings.prompt_version}")
    print(f"Gemini API: {'Configured' if settings.gemini_api_key else 'Not Configured'}")
    
    # Initialize database
    print("Initializing database...")
    init_db()
    print("✓ Database initialized")
    
    print(f"Frontend: http://localhost:8000/")
    print(f"API Docs: http://localhost:8000/docs")
    print("=" * 50)

# Force reload
# Question list updated

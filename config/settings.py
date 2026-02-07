"""
PhysiTutor-AI Configuration Settings
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Project root
    PROJECT_ROOT: Path = PROJECT_ROOT
    
    # Gemini API
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-2.0-flash"
    
    # Application
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Prompt versioning
    prompt_version: str = os.getenv("PROMPT_VERSION", "v1.0")
    
    # Paths
    prompts_dir: Path = PROJECT_ROOT / "config" / "prompts"
    questions_dir: Path = PROJECT_ROOT / "data" / "questions"
    logs_dir: Path = PROJECT_ROOT / "data" / "logs"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


# Global settings instance
settings = Settings()


def get_system_prompt() -> str:
    """Load the tutor system prompt from file."""
    prompt_file = settings.prompts_dir / "tutor_system.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return ""

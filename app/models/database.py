"""
Database models for PhysiTutor-AI
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config.settings import settings

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sessions = relationship("Session", back_populates="user")
    mistakes = relationship("Mistake", back_populates="user")


class Session(Base):
    """会话表"""
    __tablename__ = 'sessions'
    
    id = Column(String(36), primary_key=True)  # session_id
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # 允许匿名用户
    question_id = Column(String(100), nullable=False)
    status = Column(String(20), default='active')  # active, completed, abandoned
    current_step_id = Column(Integer, default=1)
    correct_count = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    step_records = relationship("StepRecord", back_populates="session", cascade="all, delete-orphan")


class StepRecord(Base):
    """步骤记录表"""
    __tablename__ = 'step_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey('sessions.id'), nullable=False)
    step_id = Column(Integer, nullable=False)
    student_choice = Column(String(10), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("Session", back_populates="step_records")


class Mistake(Base):
    """错题本表"""
    __tablename__ = 'mistakes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    question_id = Column(String(100), nullable=False)
    step_id = Column(Integer, nullable=False)
    wrong_choice = Column(String(10), nullable=False)
    correct_choice = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="mistakes")


class GeneratedQuestion(Base):
    """AI生成题目表（用于"举一反三"）"""
    __tablename__ = 'generated_questions'
    
    id = Column(String(100), primary_key=True)
    source_question_id = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)  # JSON 格式存储
    created_at = Column(DateTime, default=datetime.utcnow)


# Database initialization
def get_engine():
    """Get database engine"""
    database_url = f"sqlite:///{settings.PROJECT_ROOT}/physitutor.db"
    engine = create_engine(database_url, echo=False)
    return engine


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_db_session():
    """Get database session"""
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

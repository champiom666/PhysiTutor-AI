"""
PhysiTutor-AI Logging Module
Records all dialogue interactions for analysis.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from app.models.schemas import DialogueLog, SessionSummary
from config.settings import settings


class DialogueLogger:
    """Logger for recording dialogue interactions to JSONL files."""
    
    def __init__(self):
        """Initialize the logger and ensure log directory exists."""
        self.logs_dir = settings.logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Main log file (JSONL format for easy streaming analysis)
        self.log_file = self.logs_dir / "dialogue_logs.jsonl"
        self.summary_file = self.logs_dir / "session_summaries.jsonl"
    
    def log_interaction(self, log_entry: DialogueLog) -> None:
        """
        Record a single dialogue interaction.
        
        Args:
            log_entry: The dialogue log entry to record
        """
        log_dict = log_entry.model_dump()
        # Convert datetime to ISO format string
        log_dict["timestamp"] = log_dict["timestamp"].isoformat()
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_dict, ensure_ascii=False) + "\n")
    
    def log_session_summary(self, summary: SessionSummary) -> None:
        """
        Record a session summary when session completes.
        
        Args:
            summary: The session summary to record
        """
        summary_dict = summary.model_dump()
        summary_dict["completed_at"] = summary_dict["completed_at"].isoformat()
        
        with open(self.summary_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(summary_dict, ensure_ascii=False) + "\n")
    
    def get_session_logs(self, session_id: str) -> List[DialogueLog]:
        """
        Retrieve all logs for a specific session.
        
        Args:
            session_id: The session ID to filter by
            
        Returns:
            List of DialogueLog entries for the session
        """
        logs = []
        if not self.log_file.exists():
            return logs
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    log_dict = json.loads(line)
                    if log_dict.get("session_id") == session_id:
                        log_dict["timestamp"] = datetime.fromisoformat(log_dict["timestamp"])
                        logs.append(DialogueLog(**log_dict))
        
        return logs
    
    def get_recent_logs(self, limit: int = 100) -> List[dict]:
        """
        Get the most recent log entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of recent log entries as dictionaries
        """
        logs = []
        if not self.log_file.exists():
            return logs
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
        
        return logs[-limit:]
    
    def get_question_stats(self, question_id: str) -> dict:
        """
        Get statistics for a specific question.
        
        Args:
            question_id: The question ID to analyze
            
        Returns:
            Dictionary with question statistics
        """
        if not self.log_file.exists():
            return {"question_id": question_id, "total_attempts": 0}
        
        step_stats = {}
        total_correct = 0
        total_attempts = 0
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    log = json.loads(line)
                    if log.get("question_id") == question_id:
                        step_id = log.get("step_id")
                        is_correct = log.get("is_correct", False)
                        
                        if step_id not in step_stats:
                            step_stats[step_id] = {"correct": 0, "total": 0}
                        
                        step_stats[step_id]["total"] += 1
                        total_attempts += 1
                        
                        if is_correct:
                            step_stats[step_id]["correct"] += 1
                            total_correct += 1
        
        return {
            "question_id": question_id,
            "total_attempts": total_attempts,
            "overall_accuracy": total_correct / total_attempts if total_attempts > 0 else 0,
            "step_stats": step_stats
        }


# Global logger instance
dialogue_logger = DialogueLogger()

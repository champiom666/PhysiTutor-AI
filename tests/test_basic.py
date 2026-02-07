"""
Basic tests for PhysiTutor-AI
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestRootEndpoints:
    """Test root and health endpoints."""
    
    def test_root(self):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "PhysiTutor-AI"
        assert "endpoints" in data
    
    def test_health(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestSessionEndpoints:
    """Test session management endpoints."""
    
    def test_list_questions(self):
        """Test listing available questions."""
        response = client.get("/session/")
        assert response.status_code == 200
        data = response.json()
        assert "available_questions" in data
        assert "count" in data
    
    def test_start_session_invalid_question(self):
        """Test starting session with invalid question ID."""
        response = client.post(
            "/session/start",
            json={"question_id": "nonexistent_question"}
        )
        assert response.status_code == 404
    
    def test_start_session_valid(self):
        """Test starting a valid session."""
        # First get available questions
        questions_response = client.get("/session/")
        questions = questions_response.json()["available_questions"]
        
        if questions:
            response = client.post(
                "/session/start",
                json={"question_id": questions[0]}
            )
            assert response.status_code == 200
            data = response.json()
            assert "session_id" in data
            assert data["status"] == "active"
            
            # Clean up
            client.post(f"/session/{data['session_id']}/end")


class TestDialogueEndpoints:
    """Test dialogue interaction endpoints."""
    
    def test_get_current_step_invalid_session(self):
        """Test getting current step with invalid session."""
        response = client.get("/dialogue/invalid_session/current")
        assert response.status_code == 404
    
    def test_submit_choice_invalid_session(self):
        """Test submitting choice with invalid session."""
        response = client.post(
            "/dialogue/invalid_session/submit",
            json={"choice": "A"}
        )
        assert response.status_code == 404
    
    def test_full_dialogue_flow(self):
        """Test a complete dialogue flow."""
        # Get available questions
        questions_response = client.get("/session/")
        questions = questions_response.json()["available_questions"]
        
        if not questions:
            pytest.skip("No questions available for testing")
        
        # Start session
        start_response = client.post(
            "/session/start",
            json={"question_id": questions[0]}
        )
        session_id = start_response.json()["session_id"]
        
        try:
            # Get current step
            step_response = client.get(f"/dialogue/{session_id}/current")
            assert step_response.status_code == 200
            step_data = step_response.json()
            assert "prompt" in step_data
            assert "options" in step_data
            
            # Submit a choice
            submit_response = client.post(
                f"/dialogue/{session_id}/submit",
                json={"choice": "A"}
            )
            assert submit_response.status_code == 200
            feedback_data = submit_response.json()
            assert "is_correct" in feedback_data
            assert "feedback" in feedback_data
            
            # Check history
            history_response = client.get(f"/dialogue/{session_id}/history")
            assert history_response.status_code == 200
            history_data = history_response.json()
            assert len(history_data["history"]) > 0
            
        finally:
            # Clean up
            client.post(f"/session/{session_id}/end")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

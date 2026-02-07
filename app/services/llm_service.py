"""
PhysiTutor-AI Gemini API Service
Simple wrapper for Gemini API calls.
"""
import google.generativeai as genai
from typing import Optional, List, Dict

from config.settings import settings, get_system_prompt


class LLMService:
    """Service for interacting with Gemini API."""
    
    def __init__(self):
        """Initialize the Gemini client."""
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.system_prompt = get_system_prompt()
        
        # Configure the API
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None
    
    def is_configured(self) -> bool:
        """Check if the API is properly configured."""
        return self.model is not None and bool(self.api_key)
    
    def generate_feedback(
        self,
        step_prompt: str,
        student_choice: str,
        is_correct: bool,
        base_feedback: str,
        context: Optional[str] = None
    ) -> str:
        """
        Generate enhanced AI feedback for a student's choice.
        
        This can be used to provide more personalized feedback beyond
        the pre-defined feedback in the question data.
        
        Args:
            step_prompt: The current step's prompt
            student_choice: The choice the student made
            is_correct: Whether the choice was correct
            base_feedback: The pre-defined feedback from question data
            context: Optional additional context
            
        Returns:
            Enhanced feedback string
        """
        if not self.is_configured():
            # Return base feedback if API not configured
            return base_feedback
        
        # For MVP, we primarily use pre-defined feedback
        # AI is used for edge cases or when more guidance is needed
        try:
            prompt = self._build_feedback_prompt(
                step_prompt, student_choice, is_correct, base_feedback, context
            )
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            # Fallback to base feedback on error
            print(f"LLM API error: {e}")
            return base_feedback
    
    def _build_feedback_prompt(
        self,
        step_prompt: str,
        student_choice: str,
        is_correct: bool,
        base_feedback: str,
        context: Optional[str] = None
    ) -> str:
        """Build the prompt for feedback generation."""
        status = "正确" if is_correct else "错误"
        
        prompt = f"""{self.system_prompt}

---
当前情境：
题目步骤：{step_prompt}
学生选择：{student_choice}
判断结果：{status}
预设反馈：{base_feedback}

请基于预设反馈，生成一条简洁的引导性回复（不超过2句话）。
- 如果正确：确认判断，简述为什么这是关键决策
- 如果错误：指出逻辑问题，但不要透露正确答案

回复："""
        
        return prompt
    
    def generate_transfer_prompt(
        self,
        original_question: Dict,
        student_performance: Dict
    ) -> str:
        """
        Generate a transfer question with reduced guidance.
        
        Args:
            original_question: The original question data
            student_performance: Student's performance on original question
            
        Returns:
            A new question prompt with same structure but less guidance
        """
        if not self.is_configured():
            return "（迁移题目生成需要配置 API）"
        
        try:
            prompt = f"""{self.system_prompt}

---
原题信息：
主题：{original_question.get('topic', '')}
难度：{original_question.get('difficulty', '')}
描述：{original_question.get('question_context', {}).get('description', '')}

学生表现：
正确率：{student_performance.get('accuracy', 0):.1%}
完成步骤：{student_performance.get('completed_steps', 0)}

请生成一道同结构但数值/情境不同的迁移题，用于验证学生是否真正掌握了解题思路。
- 保持相同的物理概念和解题逻辑
- 改变具体数值或场景
- 减少引导，让学生更独立思考

迁移题目："""
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"LLM API error: {e}")
            return "（迁移题目生成失败，请检查 API 配置）"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> str:
        """
        General chat interface for more flexible interactions.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Response temperature (0.0-1.0)
            
        Returns:
            AI response text
        """
        if not self.is_configured():
            return "（API 未配置，请设置 GEMINI_API_KEY）"
        
        try:
            # Build chat history
            chat_model = self.model.start_chat(history=[])
            
            # Add system prompt as first message
            if self.system_prompt:
                chat_model.send_message(f"[System Instructions]\n{self.system_prompt}")
            
            response = None
            # Process messages
            for msg in messages:
                if msg["role"] == "user":
                    response = chat_model.send_message(msg["content"])
            
            if response:
                return response.text.strip()
            return ""
        except Exception as e:
            print(f"LLM API error (chat): {e}")
            return f"（API 调用失败：{str(e)}）"

    def analyze_reasoning(
        self,
        question: "Question",
        student_reasoning: str,
        student_image: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Analyze student's reasoning and provide feedback + standard solution.
        
        Returns:
            Dict containing 'evaluation' and 'standard_solution'
        """
        if not self.is_configured():
            return {
                "evaluation": "（API 未配置，无法评价）",
                "standard_solution": "（API 未配置，无法生成解析）"
            }
            
        try:
            prompt = f"""
请作为物理导师，评价学生关于这道题的解题思路，并提供标准解析。

题目信息：
描述：{question.question_context.description}
问题：{question.question_context.ask}

学生的解题思路：
"{student_reasoning}"

请按以下 JSON 格式返回（不要使用 markdown code block，直接返回 JSON）：
{{
    "evaluation": "对学生思路的点评（指出亮点和不足，语气鼓励）",
    "standard_solution": "清晰的标准解题步骤和解析"
}}
"""
            # If image is provided, we would handle it here (Gemini supports verification).
            # For MVP simplicity, we might just pass text.
            # But the tool supports image inputs if we use the right method.
            # Assuming text-only for now unless `student_image` handles base64/url
            
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            # Simple cleanup for json
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "")
            elif text.startswith("```"):
                text = text.replace("```", "")
            
            import json
            try:
                result = json.loads(text)
                return result
            except json.JSONDecodeError:
                # Fallback if json parsing fails
                return {
                    "evaluation": text,
                    "standard_solution": "（解析生成格式异常，请参考评价内容）"
                }
                
        except Exception as e:
            print(f"LLM API error (analyze): {e}")
            return {
                "evaluation": "（评价生成失败，请稍后重试）",
                "standard_solution": "（解析生成失败）"
            }


# Global LLM service instance
llm_service = LLMService()

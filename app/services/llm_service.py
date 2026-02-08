"""
PhysiTutor-AI Gemini API Service
调用方式与 scripts/test_gemini.py 一致：REST API（requests），超时 120s。
"""
import json
import requests
from requests.adapters import HTTPAdapter
from typing import Optional, List, Dict
from urllib3.util.retry import Retry

from config.settings import settings, get_system_prompt

# 与 test_gemini.py 一致的超时时间
GEMINI_TIMEOUT = 120


def _call_gemini_rest(api_key: str, model: str, prompt: str, timeout: int = GEMINI_TIMEOUT) -> str:
    """
    与 scripts/test_gemini.py 同方式：REST API 调用 Gemini generateContent。
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))

    resp = session.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    return result["candidates"][0]["content"]["parts"][0]["text"].strip()


class LLMService:
    """Service for interacting with Gemini API (REST, same as test_gemini.py)."""

    def __init__(self):
        """Initialize with API key and model name from settings."""
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        self.system_prompt = get_system_prompt()
        self.timeout = GEMINI_TIMEOUT

    def is_configured(self) -> bool:
        """Check if the API is properly configured."""
        return bool(self.api_key and self.api_key.strip())

    def _generate_content(self, prompt: str) -> str:
        """Single REST call to Gemini generateContent, timeout=120s."""
        return _call_gemini_rest(self.api_key, self.model_name, prompt, timeout=self.timeout)

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
        """
        if not self.is_configured():
            return base_feedback

        try:
            prompt = self._build_feedback_prompt(
                step_prompt, student_choice, is_correct, base_feedback, context
            )
            return self._generate_content(prompt)
        except Exception as e:
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

            return self._generate_content(prompt)
        except Exception as e:
            print(f"LLM API error: {e}")
            return "（迁移题目生成失败，请检查 API 配置）"

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> str:
        """
        General chat: 将 system + 用户消息拼成单条 prompt，一次 REST 调用。
        """
        if not self.is_configured():
            return "（API 未配置，请设置 GEMINI_API_KEY）"

        try:
            parts = []
            if self.system_prompt:
                parts.append(f"[System Instructions]\n{self.system_prompt}\n\n")
            for msg in messages:
                if msg.get("role") == "user":
                    parts.append(msg.get("content", ""))
            prompt = "\n".join(parts).strip()
            if not prompt:
                return ""
            return self._generate_content(prompt)
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
            text = self._generate_content(prompt)

            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "")
            elif text.startswith("```"):
                text = text.replace("```", "")

            try:
                result = json.loads(text)
                for field in ["evaluation", "standard_solution"]:
                    val = result.get(field)
                    if val is None:
                        result[field] = ""
                    elif not isinstance(val, str):
                        if isinstance(val, (dict, list)):
                            result[field] = json.dumps(val, indent=2, ensure_ascii=False)
                        else:
                            result[field] = str(val)
                return result
            except json.JSONDecodeError:
                return {
                    "evaluation": text,
                    "standard_solution": "（解析生成格式异常，请查看上方点评）"
                }

        except Exception as e:
            print(f"LLM API error (analyze): {e}")
            return {
                "evaluation": "（评价生成失败，请稍后重试）",
                "standard_solution": "（解析生成失败）"
            }


# Global LLM service instance
llm_service = LLMService()

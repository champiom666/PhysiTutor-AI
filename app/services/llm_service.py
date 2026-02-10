"""
PhysiTutor-AI Gemini API Service
调用方式与 scripts/test_gemini.py 一致：REST API（requests），超时 120s。
"""
import json
import requests
from requests.adapters import HTTPAdapter
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.schemas import Question
from urllib3.util.retry import Retry

from zhipuai import ZhipuAI

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


def _call_gemini_rest_with_image(
    api_key: str,
    model: str,
    prompt: str,
    image_base64: str,
    mime_type: str = "image/png",
    timeout: int = GEMINI_TIMEOUT,
) -> str:
    """REST 调用 Gemini generateContent，带图片（inline_data）。"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
    payload = {
        "contents": [
            {
                "parts": [
                    {"inlineData": {"mimeType": mime_type, "data": image_base64}},
                    {"text": prompt},
                ]
            }
        ]
    }

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
    parts = result["candidates"][0]["content"]["parts"]
    for p in parts:
        if "text" in p:
            return p["text"].strip()
    return ""


class LLMService:
    """Service for interacting with LLM APIs (Gemini or Zhipu)."""

    def __init__(self):
        """Initialize with API keys and settings."""
        self.provider = settings.llm_provider
        
        # Gemini setup
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model
        
        # Zhipu setup
        self.zhipu_api_key = settings.zhipu_api_key
        self.zhipu_model = settings.zhipu_model
        self.zhipu_vision_model = settings.zhipu_vision_model
        self.zhipu_client = None
        
        if self.zhipu_api_key:
            try:
                from zhipuai import ZhipuAI
                self.zhipu_client = ZhipuAI(api_key=self.zhipu_api_key)
            except Exception as e:
                print(f"Failed to initialize Zhipu client: {e}")
        
        self.system_prompt = get_system_prompt()
        self.timeout = GEMINI_TIMEOUT

    def is_configured(self) -> bool:
        """Check if the current provider is properly configured."""
        if self.provider == "zhipu":
            return bool(self.zhipu_api_key and self.zhipu_client)
        return bool(self.gemini_api_key and self.gemini_api_key.strip())

    def _extract_json(self, text: str) -> Dict:
        """Helper to extract JSON object from text (with regex fallback)."""
        import re
        try:
            # 尝试正则提取 JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            # 正则失败或无匹配，尝试全文解析
            return json.loads(text)
        except json.JSONDecodeError:
            # 再次尝试清理 markdown 后解析
            clean_text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)

    def _call_zhipu(self, prompt: str) -> str:
        """Call Zhipu AI GLM-4 model."""
        if not self.zhipu_client:
            raise ValueError("Zhipu client not initialized")
            
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self.zhipu_client.chat.completions.create(
            model=self.zhipu_model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    def _call_zhipu_with_image(
        self,
        prompt: str,
        image_base64: str,
        mime_type: str = "image/png"
    ) -> str:
        """Call Zhipu AI GLM-4V model."""
        if not self.zhipu_client:
            raise ValueError("Zhipu client not initialized")
            
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        
        # Zhipu vision format
        content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_base64}"
                }
            },
            {
                "type": "text",
                "text": prompt
            }
        ]
        
        messages.append({"role": "user", "content": content})
        
        response = self.zhipu_client.chat.completions.create(
            model=self.zhipu_vision_model,
            messages=messages,
            temperature=0.1,  # Low temperature for analysis
        )
        return response.choices[0].message.content.strip()

    def _generate_content(self, prompt: str) -> str:
        """Generate content using the configured provider."""
        if self.provider == "zhipu":
            return self._call_zhipu(prompt)
        return _call_gemini_rest(self.gemini_api_key, self.gemini_model, prompt, timeout=self.timeout)

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
        General chat: 统一接口，根据 provider 分发。
        """
        if not self.is_configured():
            return "（API 未配置）"

        try:
            # 构造 prompt
            if self.provider == "zhipu":
                # Zhipu 支持 list of messages
                msgs = []
                if self.system_prompt:
                    msgs.append({"role": "system", "content": self.system_prompt})
                # 转换 message role
                for msg in messages:
                    # zhipu 使用 'user', 'assistant', 'system'
                    msgs.append(msg)
                
                response = self.zhipu_client.chat.completions.create(
                    model=self.zhipu_model,
                    messages=msgs,
                    temperature=temperature,
                )
                return response.choices[0].message.content.strip()
            
            else:
                # Gemini REST (简单实现，拼接 prompt)
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
            # 如果学生上传了解题图片（目前还不支持把图片传给 reasoning endpoint，但为了扩展性保留接口）
            # 现在只处理文本 prompt
            text = self._generate_content(prompt)

            # 尝试清理 markdown
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "")
            elif text.startswith("```"):
                text = text.replace("```", "")
            
            text = text.strip()

            try:
                result = self._extract_json(text)

                for field in ["evaluation", "standard_solution"]:
                    val = result.get(field)
                    if val is None:
                        result[field] = ""
                    elif not isinstance(val, str):
                        if isinstance(val, dict):
                            lines = []
                            for k, v in val.items():
                                lines.append(f"{k}：{v}")
                            result[field] = "\n".join(lines)
                        elif isinstance(val, list):
                            result[field] = "\n".join([str(x) for x in val])
                        else:
                            result[field] = str(val)
                return result
            except json.JSONDecodeError as je:
                print(f"JSON Parse Error: {je}, Text: {text}")
                return {
                    "evaluation": f"（解析生成格式异常，原始内容：{text}）",
                    "standard_solution": "（解析生成失败）"
                }

        except Exception as e:
            print(f"LLM API error (analyze): {e}")
            import traceback
            traceback.print_exc()
            return {
                "evaluation": f"（评价生成失败，请稍后重试。错误信息：{str(e)}）",
                "standard_solution": "（解析生成失败）"
            }

    def generate_similar_question(
        self,
        question: "Question",
        image_base64: str,
        mime_type: str = "image/png",
    ) -> Optional[Dict]:
        """
        根据原题图片和题目信息，让 AI 出一道思路类似但情境/数值不同的题目。
        """
        if not self.is_configured():
            return None

        try:
            ctx = question.question_context
            prompt = f"""你是一位初中物理出题老师。请根据下面这张原题图片和题目信息，出一道「思路类似但情境或数值不完全一样」的新题，用于考察学生是否真正学会了解题思路。

【原题信息】
主题：{question.topic}
难度：{question.difficulty}
描述：{ctx.description}
问题：{chr(10).join(ctx.ask)}

【要求】
1. 新题考查的物理概念和解题逻辑与原题一致（如液体压强、固体压强、浮沉等）。
2. 改变具体情境或数值（如容器尺寸、质量、液体种类等），不要照抄原题。
3. 新题仍为多步引导式，包含若干「判断步骤」，每步有 prompt、选项 A/B/C/D、正确答案、正确/错误反馈。
4. 必须返回合法 JSON，不要包含 markdown 代码块标记，直接以 {{ 开头、}} 结尾。

【返回 JSON 格式】
{{
  "question_context": {{
    "description": "新题的题干描述（含情境与已知量）",
    "ask": ["① 第一问", "② 第二问", "③ 第三问"]
  }},
  "guided_steps": [
    {{
      "step_id": 1,
      "type": "concept_judgement",
      "prompt": "第一步的判断问题",
      "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
      "correct": "B",
      "feedback": {{
        "correct": "正确时的简短反馈",
        "incorrect": "错误时的简短引导"
      }}
    }}
  ]
}}

请只输出上述 JSON，不要其他说明。"""

            text = ""
            if self.provider == "zhipu" and image_base64:
                text = self._call_zhipu_with_image(prompt, image_base64, mime_type)
            elif self.provider == "gemini" and image_base64:
                text = _call_gemini_rest_with_image(
                    self.gemini_api_key, self.gemini_model, prompt, image_base64, mime_type, self.timeout
                )
            else:
                text = self._generate_content(prompt)

            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            qc = {}
            steps = []
            try:
                raw = self._extract_json(text)
                qc = raw.get("question_context") or {}
                steps = raw.get("guided_steps") or []
            except Exception:
                pass

            if not qc or not steps:
                return None

            return {
                "topic": question.topic,
                "difficulty": question.difficulty,
                "image": question.image,
                "question_context": {
                    "description": qc.get("description", ""),
                    "ask": qc.get("ask") or [],
                },
                "guided_steps": [
                    {
                        "step_id": s.get("step_id", i + 1),
                        "type": s.get("type", "concept_judgement"),
                        "prompt": s.get("prompt", ""),
                        "options": s.get("options") or [],
                        "correct": s.get("correct", "A"),
                        "feedback": {
                            "correct": (s.get("feedback") or {}).get("correct", ""),
                            "incorrect": (s.get("feedback") or {}).get("incorrect", ""),
                        },
                    }
                    for i, s in enumerate(steps)
                ],
                "next_similar_question_id": None,
            }
        except Exception as e:
            print(f"LLM API error (generate_similar_question): {e}")
            return None

    def analyze_physics_image(
        self,
        image_base64: str,
        mime_type: str = "image/png"
    ) -> Optional[Dict]:
        """
        分析物理题图片，识别题目内容并自动拆解为引导式步骤。
        """
        if not self.is_configured():
            return None
        
        try:
            prompt = """你是一位初中物理出题老师。请分析这张物理题图片，并按照以下要求处理：

【任务】
1. 识别题目的完整内容（包括文字描述、图形、已知条件、问题）
2. 确定题目的物理主题（如：压强、浮力、电路、运动等）
3. 将题目拆解为 3-5 个关键判断步骤，每步引导学生思考一个核心要点
4. 为每步设计 4 个选项（A/B/C/D），包含 1 个正确答案和合理的干扰项
5. 提供正确和错误时的简短反馈

【要求】
- 步骤设计要符合解题逻辑顺序（概念判断 → 模型选择 → 计算方向 → 结果验证）
- 干扰项要基于常见误解设计，不要随意编造
- 反馈要简洁（1-2句话），正确时肯定+解释，错误时提示但不直接给答案
- 必须返回合法 JSON，不要包含 markdown 代码块标记

【返回 JSON 格式】
{
  "topic": "题目的物理主题（如：液体压强与固体压强综合）",
  "difficulty": "中考",
  "question_context": {
    "description": "题目的完整描述（含已知条件、情境说明）",
    "ask": ["① 第一问...", "② 第二问...", "③ 第三问..."]
  },
  "guided_steps": [
    {
      "step_id": 1,
      "type": "concept_judgement",
      "prompt": "第一步的判断问题（引导学生思考某个核心概念）",
      "options": ["A. 选项A", "B. 选项B", "C. 选项C", "D. 选项D"],
      "correct": "B",
      "feedback": {
        "correct": "正确！简短肯定 + 原因说明",
        "incorrect": "这个选择有问题。提示性引导，不直接给答案"
      }
    }
  ]
}

请只输出 JSON，不要其他说明。"""

            text = ""
            if self.provider == "zhipu":
                text = self._call_zhipu_with_image(prompt, image_base64, mime_type)
            else:
                text = _call_gemini_rest_with_image(
                    self.gemini_api_key,
                    self.gemini_model,
                    prompt,
                    image_base64,
                    mime_type=mime_type,
                    timeout=self.timeout
                )
            
            # 清理可能的 markdown 标记
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()
            
            # 解析 JSON
            try:
                data = self._extract_json(text)
            except Exception as e:
                print(f"JSON Parse Error (analyze_physics_image): {e}")
                return None
            
            # 验证必要字段
            if not data.get("topic") or not data.get("question_context") or not data.get("guided_steps"):
                return None
            
            # 构造完整的 Question dict
            return {
                "topic": data.get("topic", "物理综合题"),
                "difficulty": data.get("difficulty", "中考"),
                "image": None,  # 上传的图片由调用者设置
                "question_context": {
                    "description": data["question_context"].get("description", ""),
                    "ask": data["question_context"].get("ask", [])
                },
                "guided_steps": [
                    {
                        "step_id": step.get("step_id", idx + 1),
                        "type": step.get("type", "concept_judgement"),
                        "prompt": step.get("prompt", ""),
                        "options": step.get("options", []),
                        "correct": step.get("correct", "A"),
                        "feedback": {
                            "correct": step.get("feedback", {}).get("correct", ""),
                            "incorrect": step.get("feedback", {}).get("incorrect", "")
                        }
                    }
                    for idx, step in enumerate(data.get("guided_steps", []))
                ],
                "next_similar_question_id": None
            }
            
        except Exception as e:
            print(f"LLM API error (analyze_physics_image): {e}")
            return None


# Global LLM service instance
llm_service = LLMService()


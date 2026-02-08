# PhysiTutor-AI

> AI-native 引导型物理导师 MVP

## 项目概述

验证假设：**仅通过 API + Prompt，将大模型设定为「引导型物理导师」，能否有效提升初中生的物理解题思路。**

### 核心机制

- 📋 把物理题拆成若干**关键判断步骤**
- ✋ 每一步**强制学生做选择**
- 💬 AI 只对"判断是否合理"做反馈
- 🎯 逐步引导学生形成解题路径

### 设计原则

- ❌ 不直接给答案
- ❌ 不一次讲多步
- ❌ 不炫技、不推公式
- ✅ 每次回复只围绕"当前判断是否合理"

---

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
venv\Scripts\activate

# 激活虚拟环境 (macOS/Linux)
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
copy .env.example .env

# 编辑 .env 文件，填入你的 Gemini API Key
# GEMINI_API_KEY=your_api_key_here
```

### 3. 启动服务

```bash
# 开发模式启动（仅本机可访问）
uvicorn app.main:app --reload --port 8000

# 允许外网/公网 IP 访问（部署到服务器时用）
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

### 4. 访问 API 文档

打开浏览器访问：http://localhost:8000/docs

---

## API 使用示例

### 完整对话流程

```bash
# 1. 查看可用题目
curl http://localhost:8000/session/

# 2. 开始新会话
curl -X POST http://localhost:8000/session/start \
  -H "Content-Type: application/json" \
  -d '{"question_id": "pressure_cylinder_complex_01"}'

# 响应示例:
# {
#   "session_id": "sess_abc12345",
#   "question_id": "pressure_cylinder_complex_01",
#   "current_step_id": 1,
#   "status": "active"
# }

# 3. 获取当前步骤
curl http://localhost:8000/dialogue/sess_abc12345/current

# 响应示例:
# {
#   "prompt": "在第①问中，容器 A 底部所受的压强主要由什么决定？",
#   "options": ["A. 水的质量", "B. 水的深度", "C. 容器底面积", "D. 水的体积"],
#   "context": "如图所示，两个完全相同的..."
# }

# 4. 提交选择
curl -X POST http://localhost:8000/dialogue/sess_abc12345/submit \
  -H "Content-Type: application/json" \
  -d '{"choice": "B"}'

# 响应示例 (正确):
# {
#   "is_correct": true,
#   "feedback": "很好，你抓住了关键：液体对底部的压强只与液体密度、深度和重力加速度有关。",
#   "next_step_available": true
# }

# 5. 继续下一步...重复步骤 3-4

# 6. 查看对话历史
curl http://localhost:8000/dialogue/sess_abc12345/history

# 7. 结束会话
curl -X POST http://localhost:8000/session/sess_abc12345/end
```

---

## 项目结构

```
PhysiTutor-AI/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── routes/
│   │   ├── session.py             # 会话管理 API
│   │   └── dialogue.py            # 对话交互 API
│   ├── services/
│   │   ├── llm_service.py         # Gemini API 封装
│   │   ├── dialogue_manager.py    # 对话流程控制
│   │   └── logger.py              # 日志记录模块
│   ├── models/
│   │   └── schemas.py             # Pydantic 数据模型
│   └── utils/
│       └── helpers.py             # 工具函数
├── config/
│   ├── settings.py                # 应用配置
│   └── prompts/
│       └── tutor_system.md        # AI 导师 System Prompt
├── data/
│   ├── questions/                 # 题目数据 (JSON)
│   └── logs/                      # 对话日志 (JSONL)
├── practice/                      # 原始题目资源
├── .env.example                   # 环境变量模板
├── requirements.txt               # Python 依赖
└── README.md                      # 项目文档
```

---

## 日志结构

每轮交互记录以下字段：

```json
{
  "timestamp": "2026-02-07T11:30:00+08:00",
  "session_id": "sess_abc123",
  "question_id": "pressure_cylinder_complex_01",
  "step_id": 1,
  "granularity": "concept_judgement",
  "student_choice": "B",
  "expected_choice": "B",
  "ai_feedback": "很好，你抓住了关键...",
  "is_correct": true,
  "prompt_version": "v1.0",
  "response_time_ms": 1234,
  "retry_attempt": 0
}
```

日志用途：
- 📊 分析学生常见错误模式
- 📈 验证引导策略有效性
- 🔧 优化问题拆解粒度

---

## 题目数据格式

```json
{
  "id": "pressure_cylinder_complex_01",
  "topic": "液体压强 + 固体压强 + 浮沉状态",
  "difficulty": "中考压轴",
  "question_context": {
    "description": "题目描述...",
    "ask": ["问题1", "问题2"]
  },
  "guided_steps": [
    {
      "step_id": 1,
      "type": "concept_judgement",
      "prompt": "判断问题...",
      "options": ["A. 选项1", "B. 选项2"],
      "correct": "B",
      "feedback": {
        "correct": "正确反馈",
        "incorrect": "错误反馈"
      }
    }
  ],
  "next_similar_question_id": "pressure_cylinder_complex_02"
}
```

---

## 后续扩展

### 短期 (1-2周)

1. **Prompt 调优**
   - 修改 `config/prompts/tutor_system.md`
   - 更新 `.env` 中的 `PROMPT_VERSION`

2. **添加题目**
   - 在 `data/questions/` 添加新 JSON 文件
   - 遵循相同的数据格式

3. **日志分析**
   - 访问 `GET /logs/recent` 查看最近日志
   - 分析 `data/logs/dialogue_logs.jsonl`

### 中期 (1个月)

1. **简单前端**
   - HTML + Fetch API 测试页面
   - 更友好的交互体验

2. **动态难度调整**
   - 根据正确率调整引导细粒度
   - 自动拆分困难步骤

3. **迁移验证优化**
   - AI 生成同结构题目
   - 减少引导程度验证学习效果

### 长期

1. 多题目类型支持
2. 学生画像分析
3. 自适应引导策略
4. 完整的用户系统

---

## 技术栈

- **后端**: Python 3.10+ / FastAPI
- **AI**: Google Gemini API
- **数据验证**: Pydantic
- **日志**: JSONL (便于流式分析)

---

## 注意事项

⚠️ **这是一个验证型 MVP 项目**

- 不考虑并发和规模化
- 单学生会话为主
- 重点在于验证教学效果
- 代码以"简单、清晰、可改 Prompt"为第一原则

---

## License

MIT

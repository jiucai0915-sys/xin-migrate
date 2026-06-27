# CLAUDE.md — 项目约定（两台机器的 Claude Code 都读这个，保证行为一致）

## 项目是什么
信迁 Agent（XinMigrate）：纯内网/端侧模型运行的「国产化迁移 Agent」。
核心闭环：扫描 → 规划 → 改写 → 验证 → 自修复 → 人工确认 → 产出报告。
目标场景：央国企信创迁移（Oracle SQL → 达梦/人大金仓），代码敏感不许上云，所以必须本地。

## 黄金法则
- 这是 48 小时黑客松项目：**优先能跑、能演示**，不追求工程完美。能砍则砍。
- **差异化命根子 = 「验证 + 自修复」循环**，任何时候优先保这一环稳定可复现。
- 全程离线可用：不引入任何需要外网的依赖或服务。

## 目录与分工（不要越界改对方目录）
- `agent/`、`tools/` —— A 负责（编排 + 工具）
- `kb/`、`data/`、`web/` —— B 负责（知识库 + 演示数据 + 前端）

## 技术栈
- Python 3.10+
- 端侧模型：Qwen2.5-Coder（7b/32b）经 Ollama 提供，OpenAI 兼容接口
- Agent：自研轻量 ReAct 循环，**不要引入 LangChain 等重框架**（2 人 48h 越简单越稳）
- 目标库验证：优先达梦/金仓社区版；装不上则用 PostgreSQL 模拟（语法接近），并在报告里注明

## 编码约定
- 工具函数统一注册到 `tools/registry.py`，签名风格保持一致（输入 dict，返回 dict）
- LLM 调用统一走 `agent/llm.py`，不要在别处直接 new 客户端
- 所有对外可配置项（模型名、OLLAMA_HOST、重试次数）走 `.env` + `agent/config.py`，不要硬编码
- 中文注释 OK，变量名用英文

## 提交规范
- commit message 用中文短句，前缀 feat/fix/docs/chore
- 高频提交，完成一小块就 push；push 被拒先 `git pull --rebase`

## 不要做的事
- ❌ 不要把模型文件 / .env / output 提交进 git（已在 .gitignore）
- ❌ 不要为了"更完整"去加演示用不到的功能
- ❌ 不要改对方负责的目录而不打招呼

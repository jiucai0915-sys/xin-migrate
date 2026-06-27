# 交接简报：信迁 Agent（XinMigrate）— 给负责前端/数据的开发者(B)

你正在参与一个 48 小时黑客松项目。请先完整读完本简报，再开始写代码。仓库根目录还有 `CLAUDE.md`，也请一并遵守。

## 一、项目是什么（背景）

**一句话**：一个【纯内网/端侧模型运行】的「国产化代码迁移 Agent」，把企业老代码（Oracle SQL）自动迁移到国产数据库（达梦/人大金仓）。

**为什么做这个**：
- 央国企正被强制做信创国产化替代（Oracle→国产库、x86→国产芯片），几十万行老代码要改，极痛、极贵、极缺人。
- 关键红线：**代码是敏感资产，不许上云**，所以 GitHub Copilot、通义灵码云版等云端 AI 工具法律上进不来。
- 我们的定位：**唯一能做这门生意的形态 = 纯内网 Agent**。模型跑在企业内网，断网可用。

**核心差异化（评分命根子，务必在演示里突出）**：
端侧开源模型（Qwen2.5-Coder）比 GPT-4 弱、会犯错。我们的工程价值在于**「验证→自修复」闭环**：模型生成迁移代码后，跑验证；失败就把报错喂回去让它自我修正，直到通过。**"让弱模型在内网干成活"才是护城河，不是套壳。**

## 二、Agent 的核心工作流（后端已实现骨架）

```
扫描 → 规划 → 改写 → 验证 → 自修复(失败重试) → 人工确认(高风险) → 产出代码+迁移报告
```

## 三、技术栈与架构

- Python 3.10+
- 端侧模型：Qwen2.5-Coder（7b/32b），经 **Ollama** 提供 OpenAI 兼容接口（全本地）
- Agent：**自研轻量 ReAct 循环**，禁止引入 LangChain 等重框架
- 目标库验证：优先达梦/金仓社区版；装不上用 PostgreSQL 模拟。已实现**离线降级**：没有数据库时用静态语法校验，保证断网也能演自修复。

## 四、仓库结构与分工

```
xin-migrate/
├── CLAUDE.md / README.md / TODO.md / HANDOFF_B.md
├── agent/   ← 队友A 负责（编排+LLM+prompt+主循环），你不要改
├── tools/   ← 队友A 负责（Agent 工具），你不要改
├── kb/oracle_to_dm.json   ← 【你(B)负责】迁移规则知识库
├── data/demo_project/     ← 【你(B)负责】演示用老代码
└── web/                   ← 【你(B)负责】演示界面（已有 app.py 起步骨架）
```

**协作铁律**：你只改 `kb/`、`data/`、`web/`，不要碰 `agent/` 和 `tools/`。
每次开工先 `git pull`，每完成一小块就 `git add . && git commit && git push`。

## 五、后端给你的接口（已就绪，界面直接调）

主循环已改造成**事件流生成器**，专门给你的界面实时渲染用：

```python
from agent.loop import run_events

for ev in run_events("把 data/demo_project 的 Oracle SQL 迁移到达梦"):
    # ev["type"] 取值：
    #   "think"        {step, content}        模型的思考/规划文字
    #   "tool_call"    {step, name, args, id} 调用了哪个工具
    #   "tool_result"  {step, name, result}   工具返回（含验证成败！）
    #   "done"         {content}              任务完成
    #   "max_steps"    {}                     超步数停止
    ...
```

**抓"自修复高光"的方法**：监听 `tool_result` 事件里 `name == "run_validation"` 的项——
`result["ok"] == False` 就是一次失败（带 `error`），紧接着的下一轮 `run_validation` 若 `ok==True`
就是修复成功。把这两步在界面上醒目对比展示，就是评委最看重的一幕。

方言扫描也可单独调用做演示：`from tools.dialect import grep_dialect; grep_dialect({"sql": "..."})`

## 六、你(B)的任务，按优先级

### 任务1（最高优先）：完善 web/ 可视化演示界面（已有 app.py 骨架）
现有 `web/app.py` 是个能跑的 Streamlit 起步版，已接好 `run_events`。你要把它打磨成演示级：
- 左侧：展示待迁移的原始 Oracle SQL（读 `data/demo_project/legacy_oracle.sql`）
- 中间：**实时滚动展示思考链**（think / tool_call / tool_result）
- **高光区**：把"验证失败→报错→重新改写→验证通过"做成醒目对比卡片
- 右侧/底部：最终迁移后 SQL + 迁移报告（每项：改了什么/为什么/风险等级）
- 顶部醒目标识："🔌 全程内网离线运行"
- 干净、有科技感，演示时长 5 分钟

### 任务2：丰富 kb/oracle_to_dm.json
现有 8 条规则。补充常见迁移点：`SUBSTR`、`INSTR`、`||`拼接、序列 `SEQ.NEXTVAL`、`MERGE INTO`、`ROWID` 等。保证 Demo 覆盖面够。

### 任务3：完善 data/demo_project/
可加 1-2 个文件让演示更丰富，但**每个不兼容点 kb 里都要有对应规则**，否则 Agent 改不动。

### 已知小问题（和A 沟通，别自己改 tools/）
`grep_dialect` 当前会误匹配 SQL 注释里的关键字。如影响演示，提醒队友A 加"先剥离注释"。

## 七、本地怎么跑起来

```bash
git clone https://gitee.com/bai-zhuokun/xin-migrate.git
cd xin-migrate
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install streamlit
cp .env.example .env

ollama pull qwen2.5-coder:7b          # 或 .env 里指向队友局域网模型

python -m agent.loop --task "把 data/demo_project 的 Oracle SQL 迁移到达梦"   # 命令行验证后端
streamlit run web/app.py              # 你的界面
```

## 八、硬约束

- ❌ 不引入需要外网的依赖/服务（主打内网离线）
- ❌ 不引入 LangChain 等重框架
- ❌ 不提交模型文件 / .env / output
- ❌ 不修改 agent/ 和 tools/
- ✅ 一切以"48 小时内能稳定演示"为最高目标

## 九、现在请你做的第一件事

先跑起来（第七节），确认命令行版能动；然后从**任务1**开始，把 `web/app.py` 打磨成能展示"原始SQL → 思考链 → 自修复高光 → 迁移结果"的演示级界面。

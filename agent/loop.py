"""ReAct 编排循环 —— Agent 的主心脏。

故意保持轻量（不引入 LangChain）：一个 while 循环，让模型 think→调用工具→看结果→继续，
直到模型认为任务完成。核心差异化「验证→自修复」体现在工具层（run_validation）+ 模型被
prompt 要求"失败就重试"。

提供两种用法：
- run_events(task)  ：生成器，逐步 yield 结构化事件，供 web 界面实时渲染（B 用这个）
- run(task)         ：命令行用，消费事件流并 print，返回最终结论（CLI / 联调用这个）

事件类型（run_events 产出）：
  {"type": "think",       "step": int, "content": str}
  {"type": "tool_call",   "step": int, "name": str, "args": dict, "id": str}
  {"type": "tool_result", "step": int, "name": str, "result": dict}
  {"type": "done",        "content": str}
  {"type": "max_steps"}

运行：python -m agent.loop --task "把 data/demo_project 的 Oracle SQL 迁移到达梦"
"""
import argparse
import json

from agent import llm
from agent.config import MAX_REPAIR_RETRIES  # noqa: F401  (留给后续步数控制)
from agent.prompts import SYSTEM_PROMPT
from tools.registry import TOOL_SCHEMAS, dispatch


def run_events(task: str, max_steps: int = 25):
    """核心循环，逐步 yield 结构化事件。界面/CLI 都消费它。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(max_steps):
        msg = llm.chat(messages, tools=TOOL_SCHEMAS)

        # 模型给了文字（思考/总结）
        if msg.content:
            yield {"type": "think", "step": step, "content": msg.content}

        # 没有工具调用 = 模型认为任务完成
        if not msg.tool_calls:
            yield {"type": "done", "content": msg.content or ""}
            return

        # 把 assistant 这一轮（含 tool_calls）加入历史
        messages.append(msg)

        # 逐个执行工具调用，把结果回填
        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            yield {"type": "tool_call", "step": step, "name": name, "args": args, "id": call.id}

            result = dispatch(name, args)

            yield {"type": "tool_result", "step": step, "name": name, "result": result}

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    yield {"type": "max_steps"}


def run(task: str, max_steps: int = 25):
    """命令行 / 联调用：消费事件流并 print，返回最终结论文本。"""
    final = None
    for ev in run_events(task, max_steps=max_steps):
        t = ev["type"]
        if t == "think":
            print(f"\n[第{ev['step']}步 · 思考]\n{ev['content']}")
        elif t == "tool_call":
            print(f"[第{ev['step']}步 · 调用工具] {ev['name']}({ev['args']})")
        elif t == "tool_result":
            print(f"[第{ev['step']}步 · 工具结果] {str(ev['result'])[:300]}")
        elif t == "done":
            print("\n✅ Agent 认为任务已完成。")
            final = ev["content"]
        elif t == "max_steps":
            print("\n⚠️ 达到最大步数上限，停止。")
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, help="迁移任务描述")
    args = parser.parse_args()
    run(args.task)

"""ReAct 编排循环 —— Agent 的主心脏。

故意保持轻量（不引入 LangChain）：一个 while 循环，让模型 think→调用工具→看结果→继续，
直到模型认为任务完成。核心差异化「验证→自修复」体现在工具层（run_validation）+ 模型被
prompt 要求"失败就重试"。

运行：python -m agent.loop --task "把 data/demo_project 的 Oracle SQL 迁移到达梦"
"""
import argparse
import json

from agent import llm
from agent.config import MAX_REPAIR_RETRIES  # noqa: F401  (留给后续步数控制)
from agent.prompts import SYSTEM_PROMPT
from tools.registry import TOOL_SCHEMAS, dispatch


def run(task: str, max_steps: int = 25):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(max_steps):
        msg = llm.chat(messages, tools=TOOL_SCHEMAS)

        # 模型给了文字（思考/总结）
        if msg.content:
            print(f"\n[第{step}步 · 思考]\n{msg.content}")

        # 没有工具调用 = 模型认为任务完成
        if not msg.tool_calls:
            print("\n✅ Agent 认为任务已完成。")
            return msg.content

        # 把 assistant 这一轮（含 tool_calls）加入历史
        messages.append(msg)

        # 逐个执行工具调用，把结果回填
        for call in msg.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            print(f"[第{step}步 · 调用工具] {name}({args})")

            result = dispatch(name, args)
            print(f"[第{step}步 · 工具结果] {str(result)[:300]}")

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    print("\n⚠️ 达到最大步数上限，停止。")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, help="迁移任务描述")
    args = parser.parse_args()
    run(args.task)

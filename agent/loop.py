"""ReAct 编排循环 —— Agent 的主心脏。

故意保持轻量（不引入 LangChain）。核心差异化「验证→自修复」体现在工具层 + 模型被
prompt 要求"失败就重试"。

★ 关键工程点：端侧弱模型（如 qwen2.5-coder:7b）在 Ollama 下常常**不走原生 tool_calls**，
而是把工具调用写成 JSON 文本。本循环**同时兼容两种方式**：优先用原生 tool_calls，
否则从文本里解析出 JSON 动作。这就是"强编排兜住弱模型"——项目的护城河所在。

提供两种用法：
- run_events(task)  ：生成器，逐步 yield 结构化事件，供 web 界面实时渲染
- run(task)         ：命令行用，消费事件流并 print

事件类型：think / tool_call / tool_result / done / max_steps
（结构见各 yield 处）

运行：python -m agent.loop --task "把 data/demo_project 的 Oracle SQL 迁移到达梦"
"""
import argparse
import json
import re

from agent import llm
from agent.prompts import SYSTEM_PROMPT
from tools.registry import TOOL_SCHEMAS, TOOLS, dispatch

_TOOL_NAMES = set(TOOLS.keys())


def _lenient_loads(s: str):
    """容错 JSON 解析：弱模型常在字符串值里塞未转义的换行/制表符，先严格解析，
    失败则把"字符串内部"的裸控制字符转义后再试。这是强编排兜底弱模型的一环。"""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    out, in_str, esc = [], False, False
    for ch in s:
        if esc:
            out.append(ch); esc = False; continue
        if ch == "\\":
            out.append(ch); esc = True; continue
        if ch == '"':
            in_str = not in_str; out.append(ch); continue
        if in_str and ch == "\n":
            out.append("\\n"); continue
        if in_str and ch == "\r":
            out.append("\\r"); continue
        if in_str and ch == "\t":
            out.append("\\t"); continue
        out.append(ch)
    try:
        return json.loads("".join(out))
    except json.JSONDecodeError:
        return None


def _extract_json_action(text: str):
    """从模型文本里解析出工具调用动作 {"name","arguments"}。兼容 ```json 围栏和裸 JSON。

    返回 (action_dict 或 None, leading_text)。leading_text 是动作前的说明文字（思考）。
    """
    if not text:
        return None, ""

    # 去掉 ```json ... ``` 围栏，但记住围栏前的文字当作思考
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates = []
    if fence:
        candidates.append(fence.group(1))
        leading = text[: fence.start()].strip()
    else:
        leading = ""

    # 再尝试裸 JSON：找第一个 { 起，做花括号配平
    for start in (m.start() for m in re.finditer(r"\{", text)):
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break
        if candidates:
            break

    for cand in candidates:
        obj = _lenient_loads(cand)
        if obj is None:
            continue
        if isinstance(obj, dict) and obj.get("name") in _TOOL_NAMES:
            args = obj.get("arguments") or obj.get("args") or {}
            if isinstance(args, str):
                args = _lenient_loads(args) or {}
            return {"name": obj["name"], "arguments": args}, leading

    return None, ""


def run_events(task: str, max_steps: int = 25):
    """核心循环，逐步 yield 结构化事件。界面/CLI 都消费它。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    last_sig = None
    repeat = 0
    val_fails = 0  # 连续验证失败计数（防弱模型在某点反复改不对而空转）

    for step in range(max_steps):
        msg = llm.chat(messages, tools=TOOL_SCHEMAS)
        content = msg.content or ""

        # ---- 路径一：原生 tool_calls ----
        if msg.tool_calls:
            messages.append(msg)
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
            continue

        # ---- 路径二：从文本解析 JSON 动作（弱模型回退）----
        action, leading = _extract_json_action(content)

        if action is None:
            # 没有动作 = 最终报告
            yield {"type": "done", "content": content}
            return

        if leading:
            yield {"type": "think", "step": step, "content": leading}

        name, args = action["name"], action["arguments"]

        # 防卡死：同一动作连续重复多次则停止
        sig = json.dumps(action, ensure_ascii=False, sort_keys=True)
        repeat = repeat + 1 if sig == last_sig else 0
        last_sig = sig
        if repeat >= 3:
            yield {"type": "done", "content": "（检测到重复动作，提前结束）\n" + content}
            return

        yield {"type": "tool_call", "step": step, "name": name, "args": args, "id": f"text-{step}"}
        result = dispatch(name, args)
        yield {"type": "tool_result", "step": step, "name": name, "result": result}

        # 验证失败计数：连续多次改不对则优雅收尾（输出已完成部分），不空转到上限
        if name == "run_validation":
            if result.get("ok") is False:
                val_fails += 1
            elif result.get("ok") is True:
                val_fails = 0
            if val_fails >= 5:
                yield {"type": "done",
                       "content": "部分迁移项端侧模型多次未能自动改对，已转人工处理队列。"
                                  "已完成项见上方迁移结果。"}
                return

        # 把这一轮对话 + 观测结果回填（文本模式用 user 角色喂观测）
        messages.append({"role": "assistant", "content": content})
        messages.append({
            "role": "user",
            "content": f"工具 {name} 返回：{json.dumps(result, ensure_ascii=False)}\n"
                       f"请继续下一步。全部迁移完成并验证通过后，用纯文本输出迁移报告（不要再输出 JSON）。",
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
            print("\n✅ Agent 认为任务已完成。\n" + (ev["content"] or ""))
            final = ev["content"]
        elif t == "max_steps":
            print("\n⚠️ 达到最大步数上限，停止。")
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, help="迁移任务描述")
    args = parser.parse_args()
    run(args.task)

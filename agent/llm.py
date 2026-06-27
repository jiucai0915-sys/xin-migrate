"""端侧模型客户端 —— 所有 LLM 调用统一走这里，别在别处 new 客户端。

用 Ollama 的 OpenAI 兼容接口，全程本地，断网可用。
"""
from openai import OpenAI

from agent import config

_client = OpenAI(base_url=config.OPENAI_BASE_URL, api_key=config.OPENAI_API_KEY)


def chat(messages, tools=None, temperature=0.1):
    """调用端侧模型。

    messages: [{"role": "system/user/assistant/tool", "content": ...}]
    tools: OpenAI function-calling 格式的工具 schema 列表（可选）
    返回: openai 的 message 对象（含 .content 和 .tool_calls）
    """
    kwargs = {
        "model": config.MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = _client.chat.completions.create(**kwargs)
    return resp.choices[0].message


if __name__ == "__main__":
    # 冒烟测试：python -m agent.llm
    msg = chat([{"role": "user", "content": "用一句话说你是谁"}])
    print("模型回复:", msg.content)

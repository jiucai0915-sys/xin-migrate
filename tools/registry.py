"""工具注册中心 —— 所有工具在这里登记，loop.py 通过 dispatch() 调用。

新增工具步骤：
1. 在对应模块写函数，签名 def xxx(args: dict) -> dict
2. 在 TOOLS 里登记函数
3. 在 TOOL_SCHEMAS 里加 OpenAI function-calling 格式的 schema
"""
from tools import file_ops, dialect, kb, validate, semantic_check

# name -> 函数
TOOLS = {
    "list_files": file_ops.list_files,
    "read_file": file_ops.read_file,
    "write_file": file_ops.write_file,
    "grep_dialect": dialect.grep_dialect,
    "query_migration_kb": kb.query_migration_kb,
    "run_validation": validate.run_validation,
    "run_semantic_test": semantic_check.run_semantic_test,
    "request_human_review": validate.request_human_review,
}


def dispatch(name: str, args: dict) -> dict:
    fn = TOOLS.get(name)
    if not fn:
        return {"error": f"未知工具: {name}"}
    try:
        return fn(args)
    except Exception as e:  # 工具出错也返回结构化结果，别让循环崩
        return {"error": f"{name} 执行异常: {e}"}


# 给模型看的工具说明（OpenAI function-calling 格式）
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出目录下的文件，用于扫描待迁移代码",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取一个文件的内容",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "把迁移后的代码写入文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_dialect",
            "description": "在 SQL 文本中找出 Oracle/SQLServer 特有的、需要迁移的语法点",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "SQL 文本"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_migration_kb",
            "description": "查询迁移规则知识库，得到某个语法点应该怎么改写",
            "parameters": {
                "type": "object",
                "properties": {"feature": {"type": "string", "description": "语法点关键字，如 NVL/ROWNUM/SYSDATE"}},
                "required": ["feature"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_validation",
            "description": "在目标数据库上执行改写后的 SQL，验证语法是否正确。失败会返回报错信息供自修复。",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "迁移后的 SQL"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_semantic_test",
            "description": "在样本数据上真实执行迁移后的 SELECT，与标准答案逐行比对，验证语义正确性（不只是语法）。语法对但结果错会被抓出。",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "迁移后的 SELECT 语句"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_human_review",
            "description": "遇到高风险项时暂停，请人工确认",
            "parameters": {
                "type": "object",
                "properties": {
                    "item": {"type": "string", "description": "需要确认的迁移项"},
                    "reason": {"type": "string", "description": "为什么需要人工确认"},
                },
                "required": ["item", "reason"],
            },
        },
    },
]

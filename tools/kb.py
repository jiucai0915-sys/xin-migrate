"""迁移知识库查询工具。

规则数据由 B 维护在 kb/oracle_to_dm.json，这里只负责查。
知识库是项目护城河的一部分（沉淀垂直迁移 know-how）。
"""
import json
import os

_KB_PATH = os.path.join(os.path.dirname(__file__), "..", "kb", "oracle_to_dm.json")
_kb_cache = None


def _load_kb():
    global _kb_cache
    if _kb_cache is None:
        with open(_KB_PATH, "r", encoding="utf-8") as f:
            _kb_cache = json.load(f)
    return _kb_cache


def query_migration_kb(args: dict) -> dict:
    feature = args.get("feature", "").upper()
    kb = _load_kb()
    rule = kb.get(feature)
    if not rule:
        return {"found": False, "feature": feature, "hint": "知识库无此规则，请凭通用 SQL 标准改写并务必验证"}
    return {"found": True, "feature": feature, **rule}

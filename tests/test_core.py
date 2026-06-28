"""信迁 Agent 最小测试集 —— 守住核心不变量，跑 `pytest -q` 即可。

覆盖：方言扫描、kb/工具一致性、验证(兼容/残留/降级)、语义验证、写文件保护、
弱模型 JSON 动作解析、回放数据完整性。
"""
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------- 方言扫描 ----------------
def test_dialect_scan_finds_features():
    from tools.dialect import grep_dialect
    sql = open(os.path.join(ROOT, "data/demo_project/legacy_oracle.sql"), encoding="utf-8").read()
    feats = {h["feature"] for h in grep_dialect({"sql": sql})["hits"]}
    # 基础场景应覆盖这些不兼容点
    for f in ("NVL", "DECODE", "SYSDATE", "OUTER_JOIN_+", "ROWNUM", "DUAL"):
        assert f in feats


def test_dialect_ignores_comments():
    from tools.dialect import grep_dialect
    # 关键字只出现在注释里，不应被扫到
    r = grep_dialect({"sql": "-- 这里提到 NVL 和 ROWNUM\nSELECT 1;"})
    assert r["count"] == 0


def test_dialect_kb_consistency():
    from tools.dialect import DIALECT_PATTERNS
    kb = json.load(open(os.path.join(ROOT, "kb/oracle_to_dm.json"), encoding="utf-8"))
    missing = [k for k in DIALECT_PATTERNS if k not in kb]
    assert missing == [], f"这些语法点扫得到却无迁移规则: {missing}"


# ---------------- 工具注册一致性 ----------------
def test_tool_schema_consistency():
    from tools.registry import TOOLS, TOOL_SCHEMAS
    names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert names == set(TOOLS.keys())


# ---------------- 验证逻辑 ----------------
def test_validation_compatible_pipe_ok():
    from tools.validate import run_validation
    # || 在目标库合法，不应被判失败
    assert run_validation({"sql": "SELECT COALESCE(a,'')||b FROM t LIMIT 5"})["ok"] is True


def test_validation_leftover_rownum_fails():
    from tools.validate import run_validation
    r = run_validation({"sql": "SELECT * FROM t WHERE ROWNUM <= 5"})
    assert r["ok"] is False and "ROWNUM" in r["error"]


def test_validation_offline_degrade():
    from tools.validate import run_validation
    # 目标库没起时应降级到静态校验，而不是返回连接错误
    r = run_validation({"sql": "SELECT 1"})
    assert r["ok"] is True and r.get("engine") == "static"


# ---------------- 语义验证 ----------------
def test_semantic_correct_passes():
    from tools.semantic_check import run_semantic_test
    assert run_semantic_test({})["ok"] is True


def test_semantic_catches_wrong_join():
    from tools.semantic_check import run_semantic_test
    wrong = ("SELECT c.cust_id, COALESCE(c.cust_name,'未知客户'), "
             "CASE o.status WHEN 1 THEN '已支付' WHEN 0 THEN '待支付' ELSE '其他' END "
             "FROM customers c INNER JOIN orders o ON c.cust_id=o.cust_id ORDER BY c.cust_id LIMIT 100")
    assert run_semantic_test({"sql": wrong})["ok"] is False


# ---------------- 写文件保护 ----------------
def test_write_file_protects_source():
    from tools.file_ops import write_file
    r = write_file({"path": "data/demo_project/legacy_oracle.sql", "content": "x"})
    assert "error" in r  # 禁止覆盖演示源文件


def test_write_file_allows_output(tmp_path):
    from tools.file_ops import write_file
    p = os.path.join(ROOT, "output", "_pytest_tmp_migrated.sql")
    r = write_file({"path": p, "content": "ok"})
    assert r.get("ok") is True
    os.remove(p)


# ---------------- 弱模型 JSON 动作解析 ----------------
def test_extract_json_action_with_raw_newline():
    from agent.loop import _extract_json_action
    bad = '{"name": "write_file", "arguments": {"path": "a.sql", "content": "line1\nline2"}}'
    action, _ = _extract_json_action(bad)
    assert action and action["name"] == "write_file"
    assert "line1" in action["arguments"]["content"]


def test_extract_json_action_fenced():
    from agent.loop import _extract_json_action
    text = '我来调用工具：\n```json\n{"name":"read_file","arguments":{"path":"x"}}\n```'
    action, leading = _extract_json_action(text)
    assert action["name"] == "read_file"


def test_extract_json_action_none_for_plain_text():
    from agent.loop import _extract_json_action
    action, _ = _extract_json_action("迁移完成，报告如下：……")
    assert action is None


# ---------------- 回放数据完整性 ----------------
@pytest.mark.parametrize("name", ["basic", "advanced"])
def test_replay_data_integrity(name):
    path = os.path.join(ROOT, "data/demo_replay", f"{name}.json")
    events = json.load(open(path, encoding="utf-8"))
    valid_types = {"think", "tool_call", "tool_result", "done", "max_steps"}
    assert all(e.get("type") in valid_types for e in events)
    assert sum(1 for e in events if e.get("type") == "done") == 1
    # 必含一次"验证失败→通过"的自修复闭环
    val = [e["result"].get("ok") for e in events
           if e.get("type") == "tool_result" and e.get("name") == "run_validation"]
    assert False in val and True in val

"""离线回放演示模式 —— 演示保险（不依赖 Ollama / 不依赖网络）。

现场风险：端侧模型慢、抽风、或临时连不上，导致"失败→自修复"那一幕演砸。
本模块提供一段**确定性脚本化**的事件流，产出的事件结构与 agent.loop.run_events 完全一致，
界面无需改动即可切换播放。脚本完整复现核心闭环，且**必然包含一次"验证失败→自修复成功"**。

用法（界面里切到"演示模式"即可，或单独测试）：
    from agent.demo_replay import replay_events
    for ev in replay_events(delay=0.8):
        print(ev)
"""
import time

# 最终迁移后的正确 SQL（达梦/PG 兼容），供 done 事件展示
_FINAL_SQL = """-- 迁移后（达梦/人大金仓兼容）
SELECT
    c.cust_id,
    COALESCE(c.cust_name, '未知客户')                                          AS cust_name,
    CASE o.status WHEN 1 THEN '已支付' WHEN 0 THEN '待支付' ELSE '其他' END      AS status_text,
    CURRENT_TIMESTAMP                                                          AS query_time
FROM customers c
LEFT JOIN orders o ON c.cust_id = o.cust_id
LIMIT 100;

SELECT CURRENT_TIMESTAMP;"""

# 迁移报告（每项：改了什么 / 为什么 / 风险）
_REPORT = """### 迁移报告
| 原语法 | 迁移为 | 风险 | 说明 |
|---|---|---|---|
| NVL(...) | COALESCE(...) | 低 | 标准空值函数 |
| DECODE(...) | CASE WHEN | 中 | 条件表达式改写 |
| SYSDATE | CURRENT_TIMESTAMP | 低 | 当前时间函数 |
| (+) 外连接 | LEFT JOIN | 高 | 已人工确认 |
| ROWNUM <= 100 | LIMIT 100 | 中 | 分页语义 |
| FROM DUAL | （省略） | 低 | 国产库无需伪表 |

✅ 全部 7 项迁移完成，验证通过。其中高风险项 1 处已人工确认。"""

# 脚本化事件序列：(类型, 负载)
_SCRIPT = [
    {"type": "think", "step": 0,
     "content": "开始迁移任务。先扫描 data/demo_project/legacy_oracle.sql，识别 Oracle 特有语法。"},
    {"type": "tool_call", "step": 0, "name": "grep_dialect",
     "args": {"sql": "<legacy_oracle.sql 内容>"}, "id": "c1"},
    {"type": "tool_result", "step": 0, "name": "grep_dialect",
     "result": {"count": 7, "hits": [
         {"feature": "NVL", "risk": "低"}, {"feature": "DECODE", "risk": "中"},
         {"feature": "SYSDATE", "risk": "低"}, {"feature": "OUTER_JOIN_+", "risk": "高"},
         {"feature": "ROWNUM", "risk": "中"}, {"feature": "DUAL", "risk": "低"},
     ]}},

    {"type": "think", "step": 1,
     "content": "扫描到 7 个不兼容点。按风险排序，先处理低风险（NVL/SYSDATE/DUAL），"
                "高风险的 (+) 外连接稍后单独处理并请人确认。逐项查知识库改写。"},
    {"type": "tool_call", "step": 1, "name": "query_migration_kb", "args": {"feature": "NVL"}, "id": "c2"},
    {"type": "tool_result", "step": 1, "name": "query_migration_kb",
     "result": {"found": True, "title": "NVL → COALESCE", "risk": "低"}},

    # ★★★ 高光开始：先改 (+) 外连接，第一次改错，验证失败 ★★★
    {"type": "think", "step": 2,
     "content": "处理高风险项：Oracle 的 (+) 外连接。先尝试改写为 LEFT JOIN。"},
    {"type": "tool_call", "step": 2, "name": "run_validation",
     "args": {"sql": "SELECT ... FROM customers c, orders o WHERE c.cust_id = o.cust_id(+) ..."}, "id": "c3"},
    {"type": "tool_result", "step": 2, "name": "run_validation",
     "result": {"ok": False, "engine": "static",
                "error": "迁移后仍残留 Oracle 特有语法: OUTER_JOIN_+，目标库不支持 (+) 外连接，请改为标准 LEFT JOIN"}},

    {"type": "think", "step": 3,
     "content": "验证失败：(+) 没改干净，目标库不支持。根据报错，把 `a, b WHERE a.id=b.aid(+)` "
                "改写为标准 `a LEFT JOIN b ON a.id=b.aid`，重新验证。"},
    {"type": "tool_call", "step": 3, "name": "run_validation",
     "args": {"sql": "SELECT ... FROM customers c LEFT JOIN orders o ON c.cust_id = o.cust_id ..."}, "id": "c4"},
    {"type": "tool_result", "step": 3, "name": "run_validation",
     "result": {"ok": True, "engine": "static", "msg": "静态语法校验通过，无残留 Oracle 语法"}},
    # ★★★ 高光结束：自修复成功 ★★★

    {"type": "think", "step": 4,
     "content": "(+) 外连接属高风险（影响连接语义），按规则请人工确认。"},
    {"type": "tool_call", "step": 4, "name": "request_human_review",
     "args": {"item": "(+) 外连接 → LEFT JOIN", "reason": "外连接方向影响结果集，需人工确认语义一致"}, "id": "c5"},
    {"type": "tool_result", "step": 4, "name": "request_human_review",
     "result": {"approved": True, "note": "人工确认：语义一致，通过"}},

    {"type": "tool_call", "step": 5, "name": "write_file",
     "args": {"path": "output/migrated.sql", "content": "<迁移后 SQL>"}, "id": "c6"},
    {"type": "tool_result", "step": 5, "name": "write_file",
     "result": {"ok": True, "path": "output/migrated.sql"}},

    {"type": "done", "content": _FINAL_SQL + "\n\n" + _REPORT},
]


def replay_events(task: str = None, delay: float = 0.8):
    """回放脚本化事件流，结构与 run_events 完全一致。delay 控制每步停顿（秒），便于演示节奏。"""
    for ev in _SCRIPT:
        if delay:
            time.sleep(delay)
        yield ev


# 暴露给界面：最终 SQL 和报告，便于直接展示
FINAL_SQL = _FINAL_SQL
REPORT = _REPORT


if __name__ == "__main__":
    for e in replay_events(delay=0):
        print(e["type"], "-", str(e)[:80])

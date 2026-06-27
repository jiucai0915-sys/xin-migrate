"""生成离线回放脚本数据(basic.json / advanced.json）。

为什么用脚本生成：回放里有大段含中文、含换行的 SQL，手写 JSON 容易转义出错；
这里用 Python 三引号字符串拼好，再 json.dump 出去，保证 100% 合法 JSON。

事件结构与 agent.loop.run_events 完全一致（界面 web/app.py 直接消费）：
  {"type":"think",       "step":int, "content":str}
  {"type":"tool_call",   "step":int, "name":str, "args":dict, "id":str}
  {"type":"tool_result", "step":int, "name":str, "result":dict}
  {"type":"done",        "content":str}

改完 SQL 想重新生成：
  python data/demo_replay/build.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))  # 仓库根，便于 import tools
DEMO_DIR = os.path.join(HERE, "..", "demo_project")

from tools.dialect import grep_dialect  # noqa: E402  用真实工具产扫描结果，保证回放数字不穿帮
from tools.semantic_check import run_semantic_test  # noqa: E402  第二道关：数据级语义验证


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return "（演示 SQL 文件未找到）"


# ======================================================================
# 基础场景：legacy_oracle.sql —— NVL / DECODE / SYSDATE / (+)外连接 / ROWNUM / DUAL
# 高光：(+) 外连接第一次没改干净 → 验证失败 → 自修复为 LEFT JOIN → 通过
# ======================================================================

BASIC_SRC = _read(os.path.join(DEMO_DIR, "legacy_oracle.sql"))
BASIC_GREP = grep_dialect({"sql": BASIC_SRC})   # 真实扫描结果（count/hits 与实时工具一致）

# 第一次改写（错误）：低/中风险都改了，但最难的 (+) 外连接没改干净 → 验证失败
BASIC_ATTEMPT_BAD = """SELECT
    c.cust_id,
    COALESCE(c.cust_name, '未知客户') AS cust_name,
    CASE o.status WHEN 1 THEN '已支付' WHEN 0 THEN '待支付' ELSE '其他' END AS status_text,
    CURRENT_TIMESTAMP AS query_time
FROM customers c, orders o
WHERE c.cust_id = o.cust_id(+)
LIMIT 100;

SELECT CURRENT_TIMESTAMP;"""

# 自修复后（正确）：(+) → 标准 LEFT JOIN，验证通过
BASIC_ATTEMPT_OK = """SELECT
    c.cust_id,
    COALESCE(c.cust_name, '未知客户') AS cust_name,
    CASE o.status WHEN 1 THEN '已支付' WHEN 0 THEN '待支付' ELSE '其他' END AS status_text,
    CURRENT_TIMESTAMP AS query_time
FROM customers c
LEFT JOIN orders o ON c.cust_id = o.cust_id
LIMIT 100;

SELECT CURRENT_TIMESTAMP;"""

# 语义验证用的迁移后查询（单条 SELECT，喂给 run_semantic_test 在样本数据上真跑、比对标准答案）
BASIC_SEM_SQL = """SELECT
    c.cust_id,
    COALESCE(c.cust_name, '未知客户') AS cust_name,
    CASE o.status WHEN 1 THEN '已支付' WHEN 0 THEN '待支付' ELSE '其他' END AS status_text
FROM customers c
LEFT JOIN orders o ON c.cust_id = o.cust_id
ORDER BY c.cust_id;"""
BASIC_SEM = run_semantic_test({"sql": BASIC_SEM_SQL})   # 真实跑一遍，结果与标准答案逐行比对
assert BASIC_SEM.get("ok"), f"语义验证基线应通过，实际: {BASIC_SEM}"

BASIC_REPORT = """#### ✅ 迁移后 SQL（达梦 / 人大金仓兼容）
```sql
""" + BASIC_ATTEMPT_OK + """
```

### 📋 迁移报告
| 原 Oracle 语法 | 迁移为 | 风险 | 处理方式 |
|---|---|---|---|
| `NVL(...)` | `COALESCE(...)` | 🟢 低 | 知识库直接改写 |
| `DECODE(...)` | `CASE WHEN` | 🟡 中 | 条件表达式改写 |
| `SYSDATE` | `CURRENT_TIMESTAMP` | 🟢 低 | 知识库直接改写 |
| `(+)` 外连接 | `LEFT JOIN` | 🔴 高 | **验证失败 → 自修复 → 人工确认** |
| `ROWNUM <= 100` | `LIMIT 100` | 🟡 中 | 分页语义改写 |
| `FROM DUAL` | （省略） | 🟢 低 | 国产库无需伪表 |

**7 处不兼容点（6 类语法）全部迁移完成并通过验证**；其中 1 项高风险经「验证失败 → 读报错 → 自修复 → 人工确认」闭环处理。
全程代码未出内网。"""

BASIC = [
    {"type": "think", "step": 0,
     "content": "收到迁移任务。第一步：读取并扫描 data/demo_project/legacy_oracle.sql，找出 Oracle 特有、目标库不支持的语法点。"},
    {"type": "tool_call", "step": 0, "name": "read_file",
     "args": {"path": "data/demo_project/legacy_oracle.sql"}, "id": "b0"},
    {"type": "tool_result", "step": 0, "name": "read_file",
     "result": {"ok": True, "path": "data/demo_project/legacy_oracle.sql", "chars": len(BASIC_SRC)}},

    {"type": "tool_call", "step": 0, "name": "grep_dialect",
     "args": {"sql": BASIC_SRC}, "id": "b1"},
    {"type": "tool_result", "step": 0, "name": "grep_dialect", "result": BASIC_GREP},

    {"type": "think", "step": 1,
     "content": f"扫描到 {BASIC_GREP['count']} 处不兼容语法（6 类）。策略：按风险从低到高处理，先改确定性高的低/中风险项（NVL、SYSDATE、DUAL、DECODE、ROWNUM），"
                "把最棘手的高风险项 (+) 外连接留到最后单独攻坚，并在改完后请人工确认。先查知识库拿到改写规则。"},
    {"type": "tool_call", "step": 1, "name": "query_migration_kb", "args": {"feature": "NVL"}, "id": "b2"},
    {"type": "tool_result", "step": 1, "name": "query_migration_kb",
     "result": {"found": True, "feature": "NVL", "title": "NVL → COALESCE", "risk": "低"}},
    {"type": "tool_call", "step": 1, "name": "query_migration_kb", "args": {"feature": "DECODE"}, "id": "b3"},
    {"type": "tool_result", "step": 1, "name": "query_migration_kb",
     "result": {"found": True, "feature": "DECODE", "title": "DECODE → CASE WHEN", "risk": "中"}},

    {"type": "think", "step": 2,
     "content": "低/中风险项已按知识库改写：NVL→COALESCE、DECODE→CASE WHEN、SYSDATE→CURRENT_TIMESTAMP、ROWNUM→LIMIT、省略 DUAL。"
                "现在攻最难的高风险项：Oracle 的 (+) 外连接。先尝试改写，然后立即跑验证。"},
    # ★★★ 高光开始：第一次改写，(+) 没改干净 → 验证失败 ★★★
    {"type": "tool_call", "step": 2, "name": "run_validation",
     "args": {"sql": BASIC_ATTEMPT_BAD}, "id": "b4"},
    {"type": "tool_result", "step": 2, "name": "run_validation",
     "result": {"ok": False, "engine": "static",
                "error": "迁移后仍残留 Oracle 特有语法: OUTER_JOIN_+，目标库不支持 (+) 外连接，请改为标准 LEFT JOIN"}},

    {"type": "think", "step": 3,
     "content": "验证失败，报错说 (+) 外连接没改干净。我读懂了：要把逗号连接 `FROM a, b WHERE a.id = b.aid(+)` "
                "改写为标准 `FROM a LEFT JOIN b ON a.id = b.aid`。（(+) 在右表侧 = 左外连接。）修正后重新验证。"},
    {"type": "tool_call", "step": 3, "name": "run_validation",
     "args": {"sql": BASIC_ATTEMPT_OK}, "id": "b5"},
    {"type": "tool_result", "step": 3, "name": "run_validation",
     "result": {"ok": True, "engine": "static", "msg": "静态语法校验通过，无残留 Oracle 语法"}},
    # ★★★ 高光结束：自修复成功 ★★★

    # 第二道关：数据级语义验证（语法对≠语义对）——把"验证"从静态语法推进到数据结果
    {"type": "think", "step": 4,
     "content": "语法过关了，但“能跑通”不等于“迁移对”。再用 run_semantic_test 在样本数据上真实执行迁移后的查询，"
                "把结果与标准答案逐行比对——结果一致，才算真的迁对（比如 LEFT JOIN 误写成 INNER JOIN，语法没错但会丢掉无订单的客户）。"},
    {"type": "tool_call", "step": 4, "name": "run_semantic_test", "args": {"sql": BASIC_SEM_SQL}, "id": "b_sem"},
    {"type": "tool_result", "step": 4, "name": "run_semantic_test", "result": BASIC_SEM},

    {"type": "think", "step": 5,
     "content": "(+) 外连接属高风险——连接方向会影响结果集语义，不能擅自定论。按规则暂停，请人工确认。"},
    {"type": "tool_call", "step": 5, "name": "request_human_review",
     "args": {"item": "(+) 外连接 → LEFT JOIN", "reason": "外连接方向影响结果集，需人工确认语义一致"}, "id": "b6"},
    {"type": "tool_result", "step": 5, "name": "request_human_review",
     "result": {"approved": True, "note": "人工确认：语义一致，通过"}},

    {"type": "tool_call", "step": 6, "name": "write_file",
     "args": {"path": "output/migrated_basic.sql", "content": BASIC_ATTEMPT_OK}, "id": "b7"},
    {"type": "tool_result", "step": 6, "name": "write_file",
     "result": {"ok": True, "path": "output/migrated_basic.sql"}},

    {"type": "done", "content": BASIC_REPORT},
]


# ======================================================================
# 进阶场景：legacy_oracle_advanced.sql —— CONNECT BY / 序列 / MERGE / ROWID / INSTR
# 高光：层级查询 CONNECT BY 第一次漏了 RECURSIVE 没拆解 → 验证失败 → 自修复为递归 CTE → 通过
# ======================================================================

ADV_SRC = _read(os.path.join(DEMO_DIR, "legacy_oracle_advanced.sql"))
ADV_GREP = grep_dialect({"sql": ADV_SRC})   # 真实扫描结果

# 第一次改写（错误）：套了个 CTE 壳，但里面还留着 START WITH ... CONNECT BY，没真正拆解 → 验证失败
ADV_ATTEMPT_BAD = """WITH org AS (
    SELECT emp_id, mgr_id, emp_name
    FROM employees
    START WITH mgr_id IS NULL
    CONNECT BY PRIOR emp_id = mgr_id
)
SELECT * FROM org;"""

# 自修复后（正确）：标准 WITH RECURSIVE 递归 CTE（锚点 + UNION ALL + 递归 JOIN）
ADV_ATTEMPT_OK = """WITH RECURSIVE org AS (
    SELECT emp_id, mgr_id, emp_name, 1 AS depth
    FROM employees
    WHERE mgr_id IS NULL
    UNION ALL
    SELECT e.emp_id, e.mgr_id, e.emp_name, o.depth + 1
    FROM employees e
    JOIN org o ON e.mgr_id = o.emp_id
)
SELECT emp_id, mgr_id, emp_name, depth FROM org;"""

ADV_FINAL = """-- 1) 组织架构层级查询：CONNECT BY → WITH RECURSIVE 递归 CTE
WITH RECURSIVE org AS (
    SELECT emp_id, mgr_id, emp_name, 1 AS depth
    FROM employees
    WHERE mgr_id IS NULL
    UNION ALL
    SELECT e.emp_id, e.mgr_id, e.emp_name, o.depth + 1
    FROM employees e
    JOIN org o ON e.mgr_id = o.emp_id
)
SELECT emp_id, mgr_id, emp_name, depth FROM org;

-- 2) 取序列：seq.NEXTVAL FROM DUAL → NEXTVAL('seq')，省略伪表
SELECT NEXTVAL('order_seq');

-- 3) 库存合并更新：MERGE INTO → INSERT ... ON CONFLICT DO UPDATE（UPSERT）
INSERT INTO inventory (sku, qty)
SELECT sku, qty FROM staging
ON CONFLICT (sku) DO UPDATE SET qty = inventory.qty + EXCLUDED.qty;

-- 4) 按重复去重：ROWID → 业务主键 + 窗口函数（不再依赖物理行地址）
DELETE FROM logs
WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (PARTITION BY biz_key ORDER BY id) AS rn
        FROM logs
    ) t WHERE t.rn > 1
);

-- 5) 字符串处理：INSTR/SUBSTR/NVL → POSITION/SUBSTR/COALESCE
SELECT
    COALESCE(SUBSTR(phone, POSITION('-' IN phone) + 1), '无') AS ext_no
FROM contacts;"""

ADV_REPORT = """#### ✅ 迁移后 SQL（达梦 / 人大金仓兼容）
```sql
""" + ADV_FINAL + """
```

### 📋 迁移报告
| 原 Oracle 语法 | 迁移为 | 风险 | 处理方式 |
|---|---|---|---|
| `CONNECT BY` 层级查询 | `WITH RECURSIVE` 递归 CTE | 🔴 高 | **验证失败 → 自修复 → 人工确认** |
| `seq.NEXTVAL` | `NEXTVAL('order_seq')` | 🟡 中 | 序列语法改写 |
| `FROM DUAL` | （省略） | 🟢 低 | 国产库无需伪表 |
| `MERGE INTO` | `INSERT ... ON CONFLICT` | 🔴 高 | UPSERT 改写 + 人工确认 |
| `ROWID` 物理行删除 | 业务主键 + 窗口函数 | 🔴 高 | 涉及业务语义 + 人工确认 |
| `INSTR`/`SUBSTR`/`NVL` | `POSITION`/`SUBSTR`/`COALESCE` | 🟡 中 | 字符串与空值处理 |

**进阶场景的高风险点（层级查询 / 合并 / 物理行）全部走「自修复 + 人工确认」闭环**，没有一项黑盒放过。
全程代码未出内网。"""

ADVANCED = [
    {"type": "think", "step": 0,
     "content": "收到进阶迁移任务。这是更复杂的老脚本，先读取并扫描 legacy_oracle_advanced.sql。"},
    {"type": "tool_call", "step": 0, "name": "read_file",
     "args": {"path": "data/demo_project/legacy_oracle_advanced.sql"}, "id": "a0"},
    {"type": "tool_result", "step": 0, "name": "read_file",
     "result": {"ok": True, "path": "data/demo_project/legacy_oracle_advanced.sql", "chars": len(ADV_SRC)}},

    {"type": "tool_call", "step": 0, "name": "grep_dialect", "args": {"sql": ADV_SRC}, "id": "a1"},
    {"type": "tool_result", "step": 0, "name": "grep_dialect", "result": ADV_GREP},

    {"type": "think", "step": 1,
     "content": f"扫描到 {ADV_GREP['count']} 处不兼容语法。进阶场景高风险扎堆：层级查询(CONNECT BY)、合并(MERGE)、物理行删除(ROWID) 都是迁移里最难啃的。"
                "策略：低/中风险按知识库直接改；3 个高风险项逐一改写 + 验证，且全部请人工确认。先查最难的 CONNECT BY。"},
    {"type": "tool_call", "step": 1, "name": "query_migration_kb", "args": {"feature": "CONNECT_BY"}, "id": "a2"},
    {"type": "tool_result", "step": 1, "name": "query_migration_kb",
     "result": {"found": True, "feature": "CONNECT_BY", "title": "CONNECT BY → 递归 CTE", "risk": "高"}},

    {"type": "think", "step": 2,
     "content": "先攻层级查询。尝试把 START WITH ... CONNECT BY 改写为递归 CTE，然后跑验证。"},
    # ★★★ 高光开始：第一次只套了 CTE 壳，没拆解 CONNECT BY → 验证失败 ★★★
    {"type": "tool_call", "step": 2, "name": "run_validation", "args": {"sql": ADV_ATTEMPT_BAD}, "id": "a3"},
    {"type": "tool_result", "step": 2, "name": "run_validation",
     "result": {"ok": False, "engine": "static",
                "error": "迁移后仍残留 Oracle 特有语法: CONNECT_BY，目标库不支持层级查询语法，请改写为标准 WITH RECURSIVE 递归 CTE"}},

    {"type": "think", "step": 3,
     "content": "验证失败：我只套了个 CTE 外壳，里面 START WITH / CONNECT BY 根本没拆。读懂报错后重写为标准递归 CTE："
                "锚点成员(mgr_id IS NULL) + UNION ALL + 递归成员(子节点 JOIN 上一层)，并用 depth 还原 LEVEL。重新验证。"},
    {"type": "tool_call", "step": 3, "name": "run_validation", "args": {"sql": ADV_ATTEMPT_OK}, "id": "a4"},
    {"type": "tool_result", "step": 3, "name": "run_validation",
     "result": {"ok": True, "engine": "static", "msg": "静态语法校验通过，无残留 Oracle 语法"}},
    # ★★★ 高光结束：自修复成功 ★★★

    {"type": "think", "step": 4,
     "content": "层级查询改写涉及递归语义，高风险，请人工确认。"},
    {"type": "tool_call", "step": 4, "name": "request_human_review",
     "args": {"item": "CONNECT BY → WITH RECURSIVE 递归 CTE", "reason": "递归层级语义复杂，需人工确认结果与原层级一致"}, "id": "a5"},
    {"type": "tool_result", "step": 4, "name": "request_human_review",
     "result": {"approved": True, "note": "人工确认：递归结果与原层级一致，通过"}},

    {"type": "think", "step": 5,
     "content": "其余项：序列 seq.NEXTVAL→NEXTVAL('order_seq')、省略 DUAL、INSTR→POSITION、SUBSTR/NVL→SUBSTR/COALESCE 已按知识库改写。"
                "剩下两个高风险项 MERGE 合并与 ROWID 物理行删除，改写为 UPSERT 与「主键+窗口函数」后，一并请人工确认。"},
    {"type": "tool_call", "step": 5, "name": "request_human_review",
     "args": {"item": "MERGE INTO → ON CONFLICT UPSERT；ROWID 去重 → 主键+ROW_NUMBER()",
              "reason": "合并语义与去重依据从物理行改为业务主键，影响数据结果，需人工确认"}, "id": "a6"},
    {"type": "tool_result", "step": 5, "name": "request_human_review",
     "result": {"approved": True, "note": "人工确认：UPSERT 与主键去重逻辑等价，通过"}},

    {"type": "tool_call", "step": 6, "name": "write_file",
     "args": {"path": "output/migrated_advanced.sql", "content": ADV_FINAL}, "id": "a7"},
    {"type": "tool_result", "step": 6, "name": "write_file",
     "result": {"ok": True, "path": "output/migrated_advanced.sql"}},

    {"type": "done", "content": ADV_REPORT},
]


def main():
    targets = {"basic.json": BASIC, "advanced.json": ADVANCED}
    for fname, events in targets.items():
        path = os.path.join(HERE, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        print(f"写出 {fname}: {len(events)} 个事件")


if __name__ == "__main__":
    main()

"""数据级语义验证原型 —— 从"语法对"升级到"结果对"。

迁移最难、最值钱的不是语法转换，而是证明**迁移后跑出来的结果和原来一致**。
本模块用内置 SQLite（零依赖、离线）搭一套样本数据，真实执行迁移后的 SQL，
把结果和"标准答案(golden)"逐行比对——能跑通 ≠ 迁移对，结果一致才算对。

这是把验证从「静态语法」推进到「数据级语义」的最小可用原型（当前覆盖演示查询）。

用法：
- 作为 Agent 工具：run_semantic_test({"sql": "<迁移后的SELECT>"})
- 单独演示：python -m tools.semantic_check
"""
import sqlite3

# 样本库：故意覆盖 LEFT JOIN(有无订单)、COALESCE(NULL名)、CASE(各种状态) 三种语义
_SCHEMA_AND_DATA = """
CREATE TABLE customers (cust_id INTEGER, cust_name TEXT);
CREATE TABLE orders    (cust_id INTEGER, status  INTEGER);
INSERT INTO customers VALUES (1, '张三'), (2, NULL), (3, '李四');
-- 客户1 有两笔已支付订单；客户2 一笔待支付；客户3 无订单(测 LEFT JOIN + 状态为空)
INSERT INTO orders VALUES (1, 1), (1, 1), (2, 0);
"""

# 针对"客户订单概览"这条迁移查询的标准答案（按 cust_id 排序，去掉不确定的时间列）
_GOLDEN = [
    (1, "张三", "已支付"),
    (1, "张三", "已支付"),
    (2, "未知客户", "待支付"),   # NULL 名字 → COALESCE 兜底
    (3, "李四", "其他"),          # 无订单 → status 为 NULL → CASE ELSE '其他'
]

# 默认被测 SQL = 迁移后的正确版本（用于自检/演示）
_DEFAULT_MIGRATED_SQL = """
SELECT c.cust_id,
       COALESCE(c.cust_name, '未知客户') AS cust_name,
       CASE o.status WHEN 1 THEN '已支付' WHEN 0 THEN '待支付' ELSE '其他' END AS status_text
FROM customers c LEFT JOIN orders o ON c.cust_id = o.cust_id
ORDER BY c.cust_id
LIMIT 100;
"""


def run_semantic_test(args: dict) -> dict:
    """在样本数据上真实执行迁移后的 SQL，与标准答案逐行比对。

    args: {"sql": "<迁移后的 SELECT>"}（缺省用内置正确版本）
    返回: {ok, rows, expected, diff/error}
    """
    sql = (args or {}).get("sql") or _DEFAULT_MIGRATED_SQL

    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(_SCHEMA_AND_DATA)
        try:
            cur = conn.execute(sql)
        except sqlite3.Error as e:
            return {"ok": False, "error": f"执行失败（语法/语义错误）: {e}"}
        rows = [tuple(r) for r in cur.fetchall()]
    finally:
        conn.close()

    if rows == _GOLDEN:
        return {"ok": True, "msg": f"数据级语义验证通过：{len(rows)} 行结果与标准答案完全一致",
                "rows": rows}
    return {
        "ok": False,
        "error": "结果与标准答案不一致（语法可能没问题，但语义错了）",
        "rows": rows,
        "expected": _GOLDEN,
    }


if __name__ == "__main__":
    print("=== ① 正确迁移版本（应通过）===")
    r = run_semantic_test({"sql": _DEFAULT_MIGRATED_SQL})
    print(r["msg"] if r["ok"] else r["error"])
    for row in r.get("rows", []):
        print("   ", row)

    print("\n=== ② 语法对但语义错的版本：误用 INNER JOIN（应被抓出）===")
    wrong = _DEFAULT_MIGRATED_SQL.replace("LEFT JOIN", "INNER JOIN")
    r2 = run_semantic_test({"sql": wrong})
    if r2["ok"]:
        print("（未抓出，异常）")
    else:
        print("✅ 已抓出语义错误：", r2["error"])
        print("   迁移后结果:", r2["rows"])
        print("   标准答案  :", r2["expected"])
        print("   → INNER JOIN 把'无订单的客户3'丢了，这正是语法检查发现不了、数据级验证才能抓的坑")

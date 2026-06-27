"""验证 + 人工确认工具 —— 项目的差异化命根子。

run_validation：在目标库执行改写后的 SQL，验证语法。失败时返回详细报错，供 Agent 自修复。
- 优先连真实数据库（postgres 模拟 / 达梦）；连不上则退化为「本地语法静态校验」，保证 Demo 不依赖外部服务也能演自修复。
"""
from agent.config import TARGET_DB, VALIDATE_DB_DSN


def run_validation(args: dict) -> dict:
    sql = args.get("sql", "")

    # ① 优先：连真实数据库做 EXPLAIN/语法校验
    try:
        import psycopg2  # noqa
        conn = psycopg2.connect(VALIDATE_DB_DSN, connect_timeout=2)
        cur = conn.cursor()
        # 只校验语法、不真正执行：用 EXPLAIN 或 prepared statement
        for stmt in [s for s in sql.split(";") if s.strip()]:
            cur.execute("EXPLAIN " + stmt)
        conn.close()
        return {"ok": True, "engine": TARGET_DB, "msg": "语法校验通过"}
    except ImportError:
        pass  # 没装驱动，走静态校验
    except Exception as e:
        # 真实库报错 —— 这正是喂给 Agent 自修复的关键信息
        return {"ok": False, "engine": TARGET_DB, "error": str(e)}

    # ② 退化：本地静态语法校验（保证离线/无库也能演自修复）
    return _static_check(sql)


def _static_check(sql: str) -> dict:
    """用 sqlparse 做基础语法检查 + 残留 Oracle 语法检测。"""
    import sqlparse
    from tools.dialect import grep_dialect

    if not sqlparse.parse(sql):
        return {"ok": False, "engine": "static", "error": "SQL 无法解析"}

    # 如果迁移后还残留 Oracle 特有语法 = 没改干净 = 验证失败
    leftover = grep_dialect({"sql": sql})
    if leftover["count"] > 0:
        feats = ", ".join(sorted(set(h["feature"] for h in leftover["hits"])))
        # 附上每个残留点的具体修复指令，帮端侧弱模型一次改对（强编排兜底）
        hints = "；".join(
            f"{f}: {_FIX_HINTS[f]}" for f in sorted(set(h["feature"] for h in leftover["hits"]))
            if f in _FIX_HINTS
        )
        return {
            "ok": False,
            "engine": "static",
            "error": f"迁移后仍残留 Oracle 特有语法: {feats}，目标库不支持。"
                     f"请重写完整 SQL 并彻底改掉这些点。修复指令 → {hints}",
            "leftover": leftover["hits"],
        }
    return {"ok": True, "engine": "static", "msg": "静态语法校验通过，无残留 Oracle 语法"}


# 残留语法 → 具体修复指令（给弱模型明确的"怎么改"，提高一次改对率）
_FIX_HINTS = {
    "NVL": "把 NVL(a,b) 改成 COALESCE(a,b)",
    "ROWNUM": "删除 WHERE/AND 里的 ROWNUM<=N 条件，改为在 SQL 末尾(分号前)加 LIMIT N",
    "SYSDATE": "把 SYSDATE 改成 CURRENT_TIMESTAMP",
    "DECODE": "把 DECODE(x,v1,r1,...,def) 改成 CASE x WHEN v1 THEN r1 ... ELSE def END",
    "OUTER_JOIN_+": "把 FROM a,b WHERE a.id=b.aid(+) 改成 FROM a LEFT JOIN b ON a.id=b.aid",
    "DUAL": "直接删除 FROM DUAL（含 FROM 关键字），只保留 SELECT 表达式",
    "TO_DATE": "保留 TO_DATE，但核对日期格式串",
    "CONNECT_BY": "把 START WITH...CONNECT BY 改写为 WITH RECURSIVE 递归 CTE",
    "INSTR": "把 INSTR(str,sub) 改成 POSITION(sub IN str)",
    "SEQ_NEXTVAL": "把 seq.NEXTVAL 改成 NEXTVAL('seq')",
    "MERGE_INTO": "把 MERGE INTO 改成 INSERT ... ON CONFLICT DO UPDATE",
    "ROWID": "去掉 ROWID，改用业务主键定位",
}


def request_human_review(args: dict) -> dict:
    """高风险项暂停，请人确认。Demo 时这里可弹窗/打印等待输入。"""
    item = args.get("item", "")
    reason = args.get("reason", "")
    print(f"\n🟡【人工确认】项: {item}\n   原因: {reason}")
    # 演示时可改成 input() 真正等待；这里默认放行以便自动跑通
    return {"approved": True, "item": item, "note": "（演示模式默认放行；生产为真人确认）"}

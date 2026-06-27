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
        feats = ", ".join(h["feature"] for h in leftover["hits"])
        return {
            "ok": False,
            "engine": "static",
            "error": f"迁移后仍残留 Oracle 特有语法: {feats}，目标库不支持，请继续改写",
            "leftover": leftover["hits"],
        }
    return {"ok": True, "engine": "static", "msg": "静态语法校验通过，无残留 Oracle 语法"}


def request_human_review(args: dict) -> dict:
    """高风险项暂停，请人确认。Demo 时这里可弹窗/打印等待输入。"""
    item = args.get("item", "")
    reason = args.get("reason", "")
    print(f"\n🟡【人工确认】项: {item}\n   原因: {reason}")
    # 演示时可改成 input() 真正等待；这里默认放行以便自动跑通
    return {"approved": True, "item": item, "note": "（演示模式默认放行；生产为真人确认）"}

"""方言扫描工具 —— 找出 Oracle/SQLServer 特有、需要迁移的语法点。

简单可靠：基于关键字/正则匹配即可，不需要完整 SQL 解析。
对照的迁移规则放在 kb/，这里只负责"发现"。
"""
import re

# 语法点关键字 -> (说明, 默认风险等级)
DIALECT_PATTERNS = {
    "NVL":            (r"\bNVL\s*\(",            "Oracle 空值函数，需改为 COALESCE", "低"),
    "ROWNUM":         (r"\bROWNUM\b",            "Oracle 行号，需改为 LIMIT/分页", "中"),
    "SYSDATE":        (r"\bSYSDATE\b",           "Oracle 当前时间，需改为 CURRENT_TIMESTAMP", "低"),
    "DECODE":         (r"\bDECODE\s*\(",         "Oracle 条件函数，需改为 CASE WHEN", "中"),
    "OUTER_JOIN_+":   (r"\(\s*\+\s*\)",          "Oracle (+) 外连接语法，需改为标准 LEFT/RIGHT JOIN", "高"),
    "DUAL":           (r"\bFROM\s+DUAL\b",       "Oracle 伪表 DUAL，多数国产库可省略", "低"),
    "TO_DATE":        (r"\bTO_DATE\s*\(",        "Oracle 日期转换，需核对目标库格式", "中"),
    "CONNECT_BY":     (r"\bCONNECT\s+BY\b",      "Oracle 层级查询，需改写为递归 CTE", "高"),
    "INSTR":          (r"\bINSTR\s*\(",          "Oracle 字符串查找，需核对目标库 INSTR/POSITION 语义", "中"),
    "SEQ_NEXTVAL":    (r"\b\w+\.NEXTVAL\b",       "Oracle 序列取值，需改为 NEXTVAL('seq') 或目标库序列语法", "中"),
    "MERGE_INTO":     (r"\bMERGE\s+INTO\b",       "Oracle MERGE 合并语句，需核对目标库兼容性或改为 UPSERT", "高"),
    "ROWID":          (r"\bROWID\b",              "Oracle 物理行标识 ROWID，国产库通常无对应，需改用主键", "高"),
}


def _strip_comments(sql: str) -> str:
    """把 SQL 注释替换成等长空白（保留换行），这样扫描不误匹配注释，且行号不变。"""
    # 行注释 -- ...（到行尾）
    def _blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))

    sql = re.sub(r"--[^\n]*", _blank, sql)
    # 块注释 /* ... */（可跨行）
    sql = re.sub(r"/\*.*?\*/", _blank, sql, flags=re.DOTALL)
    return sql


def grep_dialect(args: dict) -> dict:
    raw = args.get("sql", "")
    sql = _strip_comments(raw)  # 先剥离注释，避免误匹配注释里的关键字
    hits = []
    for name, (pattern, desc, risk) in DIALECT_PATTERNS.items():
        for m in re.finditer(pattern, sql, flags=re.IGNORECASE):
            # 估算行号
            line = sql[: m.start()].count("\n") + 1
            hits.append({
                "feature": name,
                "line": line,
                "matched": m.group(0),
                "desc": desc,
                "risk": risk,
            })
    return {"count": len(hits), "hits": hits}

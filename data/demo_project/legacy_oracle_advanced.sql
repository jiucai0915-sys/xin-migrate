-- 进阶演示：更复杂的 Oracle 老系统脚本，覆盖高风险迁移点
-- 适合在评委追问"能处理复杂场景吗"时展示
-- 迁移目标：达梦 / 人大金仓（演示用 PostgreSQL 模拟）

-- 1) 组织架构层级查询（CONNECT BY —— 高风险，需改写为递归 CTE）
SELECT emp_id, mgr_id, emp_name, LEVEL AS depth
FROM employees
START WITH mgr_id IS NULL
CONNECT BY PRIOR emp_id = mgr_id;

-- 2) 订单号取序列 + DUAL（SEQ.NEXTVAL）
SELECT order_seq.NEXTVAL FROM DUAL;

-- 3) 库存合并更新（MERGE INTO —— 高风险，需改为 UPSERT）
MERGE INTO inventory t
USING staging s ON (t.sku = s.sku)
WHEN MATCHED THEN UPDATE SET t.qty = t.qty + s.qty
WHEN NOT MATCHED THEN INSERT (sku, qty) VALUES (s.sku, s.qty);

-- 4) 按物理行删除重复（ROWID —— 高风险，需改用主键）
DELETE FROM logs a
WHERE a.ROWID > (
    SELECT MIN(b.ROWID) FROM logs b WHERE a.biz_key = b.biz_key
);

-- 5) 字符串处理 + 空值（INSTR + NVL）
SELECT
    NVL(SUBSTR(phone, INSTR(phone, '-') + 1), '无')  AS ext_no
FROM contacts;

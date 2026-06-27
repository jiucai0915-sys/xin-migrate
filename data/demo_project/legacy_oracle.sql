-- 演示用：一段典型的 Oracle 老系统查询，故意埋了多个不兼容点
-- 迁移目标：达梦 / 人大金仓（演示用 PostgreSQL 模拟）
-- 埋的坑：NVL、ROWNUM、SYSDATE、DECODE、(+) 外连接、DUAL —— 覆盖低/中/高风险

-- 1) 客户订单概览：NVL + DECODE + SYSDATE + (+) 外连接
SELECT
    c.cust_id,
    NVL(c.cust_name, '未知客户')                     AS cust_name,
    DECODE(o.status, 1, '已支付', 0, '待支付', '其他') AS status_text,
    SYSDATE                                           AS query_time
FROM customers c, orders o
WHERE c.cust_id = o.cust_id(+)
  AND ROWNUM <= 100;

-- 2) 系统时间探测（DUAL 伪表）
SELECT SYSDATE FROM DUAL;

"""信迁 Agent —— 演示界面（演示级）。

接后端事件流：默认「离线回放」保证现场稳定复现，可切「实时端侧模型」联调。
重点呈现三件事：① 全程断网  ② Agent 实时思考链  ③ 验证失败→自修复 高光对比。

运行：streamlit run web/app.py
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.loop import run_events  # noqa: E402
from agent.demo_replay import replay_events  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_SQL_PATH = os.path.join(ROOT, "data", "demo_project", "legacy_oracle.sql")

st.set_page_config(page_title="信迁 Agent", page_icon="🔌", layout="wide")

# ---------- 顶部标题 + 断网徽标 ----------
top_l, top_r = st.columns([4, 1])
with top_l:
    st.title("信迁 Agent · 国产化迁移")
    st.caption("代码不出域，迁移自动化 —— 央国企信创场景专用")
with top_r:
    st.markdown(
        "<div style='text-align:right;margin-top:18px;'>"
        "<span style='background:#0a7d32;color:#fff;padding:6px 14px;border-radius:20px;"
        "font-weight:700;font-size:14px;'>🔌 内网离线运行</span></div>",
        unsafe_allow_html=True,
    )

# ---------- 侧边栏：模式 ----------
with st.sidebar:
    st.header("⚙️ 运行模式")
    mode = st.radio("选择", ["离线回放（演示推荐·稳定）", "实时端侧模型（需 Ollama）"], index=0)
    replay_delay = st.slider("回放每步停顿(秒)", 0.0, 2.0, 0.9, 0.1)
    st.divider()
    st.markdown("**为什么是我们**")
    st.markdown(
        "- 代码敏感不许上云 → 云端 AI 法律进不来\n"
        "- 端侧模型会犯错 → **验证+自修复**让它干对活\n"
        "- 这是护城河，不是套壳"
    )

# ---------- 主体左右栏 ----------
left, right = st.columns([1, 1.2])

with left:
    st.subheader("① 待迁移的 Oracle 老代码")
    sql_text = ""
    if os.path.exists(DEMO_SQL_PATH):
        with open(DEMO_SQL_PATH, "r", encoding="utf-8") as f:
            sql_text = f.read()
    st.markdown("**📄 原始 SQL**")
    with st.container(height=480):              # 与右侧思考链等高，对齐 + 可滚动
        st.code(sql_text or "（未找到演示 SQL）", language="sql")
    task = st.text_input("迁移任务", value="把 data/demo_project 的 Oracle SQL 迁移到达梦")
    start = st.button("🚀 开始迁移", type="primary", use_container_width=True)

with right:
    st.subheader("② Agent 实时工作过程")
    highlight_box = st.container()             # 自修复高光区（置顶醒目，不滚动）
    st.markdown("**🧠 思考链**")
    timeline_box = st.container(height=480)     # 思考链时间线：固定高度+自动滚动，容纳更多信息

# 结果区（底部）
st.divider()
result_box = st.container()


def render():
    events = (
        replay_events(task, delay=replay_delay)
        if mode.startswith("离线回放")
        else run_events(task)
    )

    last_attempt_sql = None   # 最近一次提交验证的 SQL
    failed_snapshot = None    # 暂存失败的 (sql, error)
    final_content = None

    with timeline_box:
        for ev in events:
            t = ev["type"]

            if t == "think":
                st.markdown(f"🤔 **思考** · 第 {ev['step']} 步")
                st.info(ev["content"])

            elif t == "tool_call":
                if ev["name"] == "run_validation":
                    last_attempt_sql = ev["args"].get("sql", "")
                st.markdown(f"🔧 调用工具 `{ev['name']}`")
                with st.expander("查看参数", expanded=False):
                    st.json(ev["args"])

            elif t == "tool_result":
                result = ev["result"]
                if ev["name"] == "run_validation":
                    if result.get("ok") is False:
                        failed_snapshot = (last_attempt_sql, result.get("error", ""))
                        st.error(f"❌ 验证失败：{result.get('error', '')}")
                    elif result.get("ok") is True:
                        if failed_snapshot:
                            # ★ 高光：失败→自修复 左右对比 ★
                            with highlight_box:
                                st.markdown("### ⭐ 核心时刻：模型犯错 → 自我修复")
                                c1, c2 = st.columns(2)
                                with c1:
                                    st.markdown("**❌ 第一次（错误）**")
                                    st.code(failed_snapshot[0] or "", language="sql")
                                    st.caption(f"报错：{failed_snapshot[1]}")
                                with c2:
                                    st.markdown("**✅ 自修复后（通过）**")
                                    st.code(last_attempt_sql or "", language="sql")
                                    st.caption("模型读懂报错，自己改对了")
                                st.success("弱模型靠强编排干成活 —— 这正是端侧 Agent 的工程价值")
                            failed_snapshot = None
                        else:
                            st.success("✅ 验证通过")
                elif ev["name"] == "request_human_review":
                    st.warning(f"🟡 高风险项已请人工确认：{result.get('note', '')}")
                elif ev["name"] == "run_semantic_test":
                    if result.get("ok"):
                        st.success(f"🧪 数据级语义验证通过：{result.get('msg', '')}")
                        if result.get("rows"):
                            st.caption("样本数据上真实执行的结果（语法对≠语义对，这步保证结果也对）：")
                            st.table(result["rows"])
                    else:
                        st.error(f"🧪 语义验证失败：{result.get('error', '')}")
                else:
                    st.markdown(f"📄 `{ev['name']}` 返回")
                    with st.expander("查看结果", expanded=False):
                        st.json(result)

            elif t == "done":
                final_content = ev["content"]

            elif t == "max_steps":
                st.warning("达到最大步数上限，停止。")

    # ---------- 结果区 ----------
    with result_box:
        st.subheader("③ 迁移产物")
        if final_content:
            st.markdown(final_content)
        else:
            st.caption("（实时模型模式下，最终产物由模型总结输出）")


if start:
    render()

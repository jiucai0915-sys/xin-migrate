"""信迁 Agent —— 演示界面（Streamlit 起步骨架）。

这是给 B 的起点：已接好后端事件流 run_events，能实时展示 Agent 干活。
B 在此基础上打磨成演示级（见 HANDOFF_B.md 任务1）。

运行：streamlit run web/app.py
"""
import os
import sys

import streamlit as st

# 让 web/ 能 import 到项目根的 agent / tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.loop import run_events  # noqa: E402

st.set_page_config(page_title="信迁 Agent", layout="wide")

st.title("信迁 Agent · 国产化迁移")
st.caption("🔌 全程内网离线运行 —— 代码不出域，迁移自动化")

DEMO_SQL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "demo_project", "legacy_oracle.sql",
)

left, right = st.columns(2)

with left:
    st.subheader("① 待迁移的 Oracle 老代码")
    sql_text = ""
    if os.path.exists(DEMO_SQL_PATH):
        with open(DEMO_SQL_PATH, "r", encoding="utf-8") as f:
            sql_text = f.read()
    st.code(sql_text or "（未找到演示 SQL）", language="sql")
    task = st.text_input(
        "迁移任务",
        value="把 data/demo_project 的 Oracle SQL 迁移到达梦",
    )
    start = st.button("🚀 开始迁移", type="primary")

with right:
    st.subheader("② Agent 实时工作过程")
    log_area = st.container()

if start:
    repair_failed = None  # 暂存上一次验证失败，用于高亮"失败→修复"
    with right:
        for ev in run_events(task):
            t = ev["type"]

            if t == "think":
                with log_area:
                    st.markdown(f"🤔 **思考**（第{ev['step']}步）")
                    st.write(ev["content"])

            elif t == "tool_call":
                with log_area:
                    st.markdown(f"🔧 调用工具 `{ev['name']}`")
                    st.json(ev["args"])

            elif t == "tool_result":
                result = ev["result"]
                # 高光：验证失败 / 自修复成功
                if ev["name"] == "run_validation":
                    if result.get("ok") is False:
                        repair_failed = result
                        with log_area:
                            st.error(f"❌ 验证失败：{result.get('error', '')}")
                    elif result.get("ok") is True:
                        with log_area:
                            if repair_failed:
                                st.success("✅ 自修复成功！模型根据报错改对了 —— 这就是弱模型靠强编排干成活")
                                repair_failed = None
                            else:
                                st.success("✅ 验证通过")
                else:
                    with log_area:
                        st.markdown(f"📄 `{ev['name']}` 返回：")
                        st.json(result)

            elif t == "done":
                with log_area:
                    st.balloons()
                    st.success("🎉 迁移完成")
                    if ev["content"]:
                        st.markdown(ev["content"])

            elif t == "max_steps":
                with log_area:
                    st.warning("达到最大步数上限，停止。")

# TODO(B):
#  - 把"失败→修复"做成左右对比卡片，更醒目
#  - 底部汇总最终迁移后 SQL + 迁移报告（改了什么/为什么/风险等级）
#  - 思考链做成可滚动的时间线，加动效
#  - 顶部加"已断网"状态徽标

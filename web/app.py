"""信迁 Agent —— 演示界面（演示级）。

设计目标：5 分钟现场演示，突出三件事
  ① 全程内网离线  ② Agent 实时思考链  ③ 验证失败→自修复 高光对比（全场重点）

两种事件源（结构完全一致，界面无需区分细节）：
  - 离线回放（默认，演示推荐）：读 data/demo_replay/*.json，确定性脚本，100% 稳定复现
  - 实时端侧模型：调 agent.loop.run_events（需本地 Ollama；连不上会友好兜底，不崩）

回放数据由 B 维护在 data/demo_replay/（basic.json / advanced.json），改完跑
`python data/demo_replay/build.py` 重新生成。本文件不依赖 agent/demo_replay。

运行：streamlit run web/app.py
"""
import difflib
import html
import json
import os
import sys
import time

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.loop import run_events  # noqa: E402  （仅实时模式用）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(ROOT, "data", "demo_project")
REPLAY_DIR = os.path.join(ROOT, "data", "demo_replay")

# 演示场景：基础 / 进阶。每个绑定「原始 SQL 文件 + 回放脚本 + 实时任务描述」
SCENARIOS = {
    "基础场景": {
        "tag": "NVL · DECODE · (+)外连接 · ROWNUM · DUAL",
        "sql": os.path.join(DEMO_DIR, "legacy_oracle.sql"),
        "replay": os.path.join(REPLAY_DIR, "basic.json"),
        "task": "把 data/demo_project/legacy_oracle.sql 的 Oracle SQL 迁移到达梦",
    },
    "进阶场景": {
        "tag": "CONNECT BY · 序列 · MERGE · ROWID · INSTR",
        "sql": os.path.join(DEMO_DIR, "legacy_oracle_advanced.sql"),
        "replay": os.path.join(REPLAY_DIR, "advanced.json"),
        "task": "把 data/demo_project/legacy_oracle_advanced.sql 的 Oracle SQL 迁移到达梦",
    },
}

st.set_page_config(page_title="信迁 Agent", page_icon="🔌", layout="wide")


# ====================== 开场闪屏（Lightfall 进场动画，全屏无边框，每次刷新都播） ======================
def splash_screen():
    """全屏播放 assets/intro.html（盖住整个视口含顶栏），点「进入系统」进主界面。"""
    import streamlit.components.v1 as components
    intro_path = os.path.join(ROOT, "assets", "intro.html")
    if not os.path.exists(intro_path):
        return  # 没有动画文件就跳过，不影响主流程

    # 把承载动画的 iframe 强制拉成全屏固定层，盖住 Streamlit 顶栏/边距；按钮浮在最上层
    st.markdown(
        """
        <style>
          header, #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"]{
              display:none !important;}
          .stApp{background:#060A0E;}
          .block-container{padding:0 !important; max-width:100% !important;}
          /* 动画 iframe 铺满整个视口 */
          .stApp iframe{
              position:fixed !important; top:0; left:0;
              width:100vw !important; height:100vh !important;
              border:none !important; z-index:99990 !important;}
          /* 「进入系统」按钮浮在动画之上、底部居中 */
          div.stButton{position:fixed; left:50%; bottom:6vh; transform:translateX(-50%); z-index:99999;}
          div.stButton > button{padding:12px 46px; font-size:17px; font-weight:700; border-radius:30px;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    with open(intro_path, "r", encoding="utf-8") as f:
        components.html(f.read(), height=1000, scrolling=False)
    if st.button("进入系统 →", type="primary"):
        st.session_state["entered"] = True
        st.rerun()
    st.stop()


if not st.session_state.get("entered"):
    splash_screen()


# ====================== 样式：深色安全运维大屏科技风 ======================
def inject_css():
    st.markdown(
        """
        <style>
        :root { --xm-accent:#00E0A4; --xm-fail:#ff5c5c; --xm-ok:#52c41a; --xm-warn:#f0a020; }
        .block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }
        .xm-mono { font-family: "SFMono-Regular", Consolas, "Courier New", monospace; }

        /* 顶部断网徽标：呼吸式辉光 */
        .xm-net {
            display:inline-flex; align-items:center; gap:8px;
            background:#0c3a22; color:#7CF2B8;
            border:1px solid rgba(0,224,164,.55); border-radius:999px;
            padding:7px 16px; font-weight:700; font-size:14px;
            box-shadow:0 0 0 rgba(0,224,164,.6); animation:xmpulse 2.2s infinite;
        }
        .xm-net .dot{width:9px;height:9px;border-radius:50%;background:var(--xm-accent);
            box-shadow:0 0 8px var(--xm-accent);}
        @keyframes xmpulse{0%{box-shadow:0 0 0 0 rgba(0,224,164,.45)}
            70%{box-shadow:0 0 0 12px rgba(0,224,164,0)}100%{box-shadow:0 0 0 0 rgba(0,224,164,0)}}

        /* 区块小标题 */
        .xm-sec{font-size:15px;font-weight:700;color:#cfe9df;margin:2px 0 8px;
            padding-left:10px;border-left:3px solid var(--xm-accent);letter-spacing:.5px;}

        /* 思考链条目 */
        .xm-think{background:#11171f;border:1px solid #1f2a36;border-radius:8px;
            padding:9px 12px;margin:6px 0;color:#cdd9e5;line-height:1.6;font-size:14px;}
        .xm-think b{color:var(--xm-accent);}
        .xm-tool{display:inline-block;background:#0e2230;border:1px solid #1c3b4a;
            color:#7fd6ff;border-radius:6px;padding:4px 10px;margin:5px 0;font-size:13px;}
        .xm-res-ok{background:#10220e;border:1px solid rgba(82,196,26,.55);
            color:#bdf09a;border-radius:8px;padding:8px 12px;margin:6px 0;font-size:14px;}
        .xm-res-fail{background:#260f10;border:1px solid rgba(255,92,92,.6);
            color:#ffc2c2;border-radius:8px;padding:8px 12px;margin:6px 0;font-size:14px;}
        .xm-res-review{background:#241b09;border:1px solid rgba(240,160,32,.6);
            color:#ffdf9e;border-radius:8px;padding:8px 12px;margin:6px 0;font-size:14px;}

        /* 自修复高光卡 */
        .xm-card{border:1.5px solid rgba(0,224,164,.5);border-radius:12px;padding:14px 16px;
            margin:6px 0 14px;background:#0e1a16;
            box-shadow:0 0 24px rgba(0,224,164,.18);}
        .xm-card-h{font-size:17px;font-weight:800;color:#eafff7;margin-bottom:10px;}
        .xm-col-h{font-weight:700;font-size:13px;margin-bottom:6px;color:#e6edf3;}
        .xm-codebox{font-family:"SFMono-Regular",Consolas,"Courier New",monospace;font-size:12.5px;
            background:#0a0e13;border:1px solid #1c2733;border-radius:8px;padding:8px 0;overflow-x:auto;}
        .xm-codebox .ln{padding:1px 12px;white-space:pre;border-left:3px solid transparent;}
        .xm-codebox .del{background:rgba(255,92,92,.16);border-left:3px solid var(--xm-fail);}
        .xm-codebox .add{background:rgba(82,196,26,.16);border-left:3px solid var(--xm-ok);}
        .xm-punch{margin-top:10px;color:#eafff7;font-weight:700;font-size:14px;
            background:#10241d;border:1px solid rgba(0,224,164,.35);border-radius:8px;padding:8px 12px;}
        .xm-errline{color:#ffb3b3;font-size:12.5px;margin-top:6px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ====================== diff：逐行高亮 失败 vs 修复 ======================
def _diff_tag_lines(before: str, after: str):
    bl, al = before.splitlines(), after.splitlines()
    sm = difflib.SequenceMatcher(a=bl, b=al)
    btag = ["eq"] * len(bl)
    atag = ["eq"] * len(al)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("replace", "delete"):
            for i in range(i1, i2):
                btag[i] = "del"
        if op in ("replace", "insert"):
            for j in range(j1, j2):
                atag[j] = "add"
    return list(zip(bl, btag)), list(zip(al, atag))


def _code_html(lines_tags):
    rows = []
    for line, tag in lines_tags:
        cls = "ln" + ("" if tag == "eq" else " " + tag)
        rows.append(f"<div class='{cls}'>{html.escape(line) or '&nbsp;'}</div>")
    return "<div class='xm-codebox'>" + "".join(rows) + "</div>"


def _rows_to_table(rows):
    """结果行列表 → 便于 st.table 展示的结构；3 列时套用业务表头（客户ID/客户名/订单状态）。"""
    rows = [list(r) for r in rows]
    if rows and len(rows[0]) == 3:
        return [{"客户ID": r[0], "客户名": r[1], "订单状态": r[2]} for r in rows]
    return rows


def render_repair_highlight(box, failed_sql: str, error: str, fixed_sql: str):
    btags, atags = _diff_tag_lines(failed_sql or "", fixed_sql or "")
    with box:
        st.markdown(
            "<div class='xm-card'><div class='xm-card-h'>⭐ 核心时刻：端侧模型改错了 → 自己读报错 → 自我修复</div>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='xm-col-h' style='color:#ff8c8c'>❌ 第一次改写（验证失败）</div>",
                        unsafe_allow_html=True)
            st.markdown(_code_html(btags), unsafe_allow_html=True)
            st.markdown(f"<div class='xm-errline'>🔴 报错：{html.escape(error)}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown("<div class='xm-col-h' style='color:#95de64'>✅ 自修复后（验证通过）</div>",
                        unsafe_allow_html=True)
            st.markdown(_code_html(atags), unsafe_allow_html=True)
            st.markdown("<div class='xm-errline' style='color:#95de64'>🟢 读懂报错，自己把红色行改对了</div>",
                        unsafe_allow_html=True)
        st.markdown(
            "<div class='xm-punch'>💡 端侧模型比 GPT-4 弱、会犯错——让它犯错后还能自己改对，"
            "正是「验证+自修复」闭环的工程价值。云端套壳谁都会，难的是让弱模型在内网把活干对。</div></div>",
            unsafe_allow_html=True,
        )


# ====================== 事件源 ======================
def replay_events(replay_path: str, delay: float):
    """读本地回放脚本（data/demo_replay/*.json），逐条 yield，结构与 run_events 一致。"""
    with open(replay_path, "r", encoding="utf-8") as f:
        events = json.load(f)
    for ev in events:
        if delay:
            time.sleep(delay)
        yield ev


# ====================== 顶部 ======================
inject_css()
top_l, top_r = st.columns([4, 1.1])
with top_l:
    st.title("信迁 Agent · 国产化迁移")
    st.caption("代码不出域，迁移自动化 —— 央国企信创场景专用（Oracle → 达梦 / 人大金仓）")
with top_r:
    st.markdown(
        "<div style='text-align:right;margin-top:20px;'>"
        "<span class='xm-net'><span class='dot'></span>🔌 全程内网离线运行</span></div>",
        unsafe_allow_html=True,
    )

# ====================== 侧边栏 ======================
with st.sidebar:
    st.header("⚙️ 运行模式")
    mode = st.radio("事件源", ["离线回放（演示推荐·稳定）", "实时端侧模型（需 Ollama）"], index=0)
    replay_delay = st.slider("回放每步停顿(秒)", 0.0, 2.0, 0.9, 0.1,
                             help="演示节奏：太快看不清，太慢拖时间，0.9 左右最佳")
    st.divider()
    st.markdown("**为什么是我们**")
    st.markdown(
        "- 代码敏感不许上云 → 云端 AI 法律进不来\n"
        "- 端侧模型会犯错 → **验证+自修复**让它干对活\n"
        "- 这是护城河，不是套壳"
    )

# ====================== 主体 ======================
left, right = st.columns([1, 1.25])

with left:
    st.markdown("<div class='xm-sec'>① 待迁移的 Oracle 老代码</div>", unsafe_allow_html=True)
    scenario_name = st.radio(
        "演示场景", list(SCENARIOS.keys()), horizontal=True,
        captions=[SCENARIOS[k]["tag"] for k in SCENARIOS],
        help="评委追问“能处理复杂场景吗”，切到「进阶场景」一键演示",
    )
    scenario = SCENARIOS[scenario_name]

    sql_text = ""
    if os.path.exists(scenario["sql"]):
        with open(scenario["sql"], "r", encoding="utf-8") as f:
            sql_text = f.read()
    st.markdown("**📄 原始 SQL**")
    with st.container(height=480):   # 与右侧思考链等高、对齐+可滚动（合入 A 的改进）
        st.code(sql_text or "（未找到演示 SQL）", language="sql")

    # key 绑定场景名：切换场景时任务描述自动刷新为该场景默认值（否则 Streamlit 会粘住旧值）
    task = st.text_input("迁移任务", value=scenario["task"], key=f"task_{scenario_name}")
    start = st.button("🚀 开始迁移", type="primary", use_container_width=True)

with right:
    st.markdown("<div class='xm-sec'>② Agent 实时工作过程</div>", unsafe_allow_html=True)
    highlight_box = st.container()   # 自修复高光区（置顶醒目，不滚动）
    st.markdown("**🧠 思考链**")
    timeline_box = st.container(height=480)   # 固定高度+自动滚动，单屏容纳更多（合入 A 的改进）

st.divider()
result_box = st.container()


# ====================== 渲染一次完整运行 ======================
def render():
    is_replay = mode.startswith("离线回放")
    if is_replay:
        events = replay_events(scenario["replay"], delay=replay_delay)
    else:
        events = run_events(task)

    last_attempt_sql = None   # 最近一次提交验证的 SQL
    failed_snapshot = None    # 暂存失败的 (sql, error)
    final_content = None

    with timeline_box:
        try:
            for ev in events:
                t = ev.get("type")

                if t == "think":
                    st.markdown(
                        f"<div class='xm-think'>🤔 <b>思考 · 第 {ev.get('step', '·')} 步</b><br>"
                        f"{html.escape(ev.get('content', ''))}</div>",
                        unsafe_allow_html=True,
                    )

                elif t == "tool_call":
                    name = ev.get("name", "")
                    if name == "run_validation":
                        last_attempt_sql = ev.get("args", {}).get("sql", "")
                    st.markdown(f"<div class='xm-tool xm-mono'>🔧 调用工具 {html.escape(name)}()</div>",
                                unsafe_allow_html=True)
                    with st.expander("查看参数", expanded=False):
                        st.json(ev.get("args", {}))

                elif t == "tool_result":
                    name = ev.get("name", "")
                    result = ev.get("result", {}) or {}
                    if name == "run_validation":
                        if result.get("ok") is False:
                            failed_snapshot = (last_attempt_sql, result.get("error", ""))
                            st.markdown(
                                f"<div class='xm-res-fail'>❌ 验证失败：{html.escape(result.get('error',''))}</div>",
                                unsafe_allow_html=True)
                        elif result.get("ok") is True:
                            if failed_snapshot:
                                render_repair_highlight(
                                    highlight_box, failed_snapshot[0], failed_snapshot[1], last_attempt_sql)
                                st.markdown(
                                    "<div class='xm-res-ok'>✅ 自修复后验证通过（详见上方高光对比）</div>",
                                    unsafe_allow_html=True)
                                failed_snapshot = None
                            else:
                                st.markdown("<div class='xm-res-ok'>✅ 验证通过</div>", unsafe_allow_html=True)
                    elif name == "request_human_review":
                        st.markdown(
                            f"<div class='xm-res-review'>🟡 高风险项已请人工确认："
                            f"{html.escape(str(result.get('note','')))}</div>",
                            unsafe_allow_html=True)
                    elif name == "run_semantic_test":
                        # 第二道关：数据级语义验证——展示在样本数据上真跑出来的结果表
                        if result.get("ok"):
                            st.markdown(
                                f"<div class='xm-res-ok'>🧪 数据级语义验证通过："
                                f"{html.escape(str(result.get('msg', '')))}</div>",
                                unsafe_allow_html=True)
                        else:
                            st.markdown(
                                f"<div class='xm-res-fail'>🧪 语义验证失败（语法可能没问题，但结果不对）："
                                f"{html.escape(str(result.get('error', '')))}</div>",
                                unsafe_allow_html=True)
                        if result.get("rows"):
                            st.caption("迁移后查询在样本数据上的真实结果：")
                            st.table(_rows_to_table(result["rows"]))
                        if not result.get("ok") and result.get("expected"):
                            st.caption("标准答案（期望结果）：")
                            st.table(_rows_to_table(result["expected"]))
                    else:
                        st.markdown(f"<div class='xm-tool xm-mono'>📄 {html.escape(name)} 返回</div>",
                                    unsafe_allow_html=True)
                        with st.expander("查看结果", expanded=False):
                            st.json(result)

                elif t == "done":
                    final_content = ev.get("content", "")

                elif t == "max_steps":
                    st.warning("达到最大步数上限，停止。")

        except Exception as e:  # 实时模式兜底：Ollama 没起/网络异常等，友好提示不崩
            st.markdown(
                "<div class='xm-res-fail'>⚠️ <b>实时端侧模型调用失败</b><br>"
                "无法连接到本地模型服务（Ollama）。请确认：<br>"
                "&nbsp;&nbsp;1) 已启动 <code>ollama serve</code> 且已 <code>ollama pull</code> 模型；<br>"
                "&nbsp;&nbsp;2) <code>.env</code> 里 OLLAMA_HOST 指向正确地址。<br>"
                "👉 现场演示建议切到侧边栏「<b>离线回放</b>」模式，稳定复现核心闭环。<br>"
                f"<span class='xm-errline'>技术细节：{html.escape(str(e))}</span></div>",
                unsafe_allow_html=True,
            )

    with result_box:
        st.markdown("<div class='xm-sec'>③ 迁移产物（迁移后 SQL + 迁移报告）</div>", unsafe_allow_html=True)
        if final_content:
            st.markdown(final_content)
        elif not mode.startswith("离线回放"):
            st.caption("（实时模型模式下，最终产物由模型总结输出；上面是它的真实推理过程。）")


if start:
    render()
else:
    with timeline_box:
        st.caption("👈 选择场景后点「开始迁移」，这里实时滚动 Agent 的思考链与工具调用。")
